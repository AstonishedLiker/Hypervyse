#!/usr/bin/env -S uv run --group dev --script
# noqa: EXE001
"""Set up the EDK II-matched formatter and Git pre-commit hook, or format HypervysePkg.

Usage:
    uv run scripts/setup.py
    uv run scripts/setup.py format
"""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import yaml

TAG = "edk2-stable202608"
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "out/formatter.json"
TOOLS = ROOT / "out/tools/uncrustify"
PLUGIN = Path(".pytool/Plugin/UncrustifyCheck")

HOOK_MARKER = "# Hypervyse managed formatter hook"

HOOK_SCRIPT = r'''#!/usr/bin/env -S uv run --group dev --script
# Hypervyse managed formatter hook
"""Check staged C/header files with the configured EDK II Uncrustify."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

def main():
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    root = Path(result.stdout.strip())

    state = root / "out/formatter.json"
    if not state.is_file():
        print("Formatter not configured. Run: uv run scripts/setup.py", file=sys.stderr)
        return 1

    settings = json.loads(state.read_text(encoding="utf-8"))
    executable = Path(settings["executable"])
    config = Path(settings["config"])

    if not executable.is_file() or not config.is_file():
        print("Formatter or configuration missing. Rerun setup.", file=sys.stderr)
        return 1

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )

    files = [
        name for name in result.stdout.split(b"\0")
        if name and Path(os.fsdecode(name)).suffix.lower() in {".c", ".h"}
    ]

    if not files:
        return 0

    print(f"Checking formatting of {len(files)} staged C/header files...", flush=True)

    failed = []

    with tempfile.TemporaryDirectory(prefix="hypervyse-format-check-") as temp:
        for index, filename in enumerate(files):
            name = os.fsdecode(filename)

            staged = subprocess.run(
                ["git", "show", ":" + name],
                cwd=root,
                check=True,
                capture_output=True,
            )

            temporary_file = Path(temp) / (str(index) + Path(name).suffix)
            temporary_file.write_bytes(staged.stdout)

            result = subprocess.run(
                [
                    str(executable),
                    "-c", str(config),
                    "--check",
                    "-l", "C",
                    "-f", str(temporary_file),
                ],
                cwd=root,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                failed.append(name)
                print(f"  FAIL {name}", file=sys.stderr)
                if result.stderr.strip():
                    print(result.stderr.strip(), file=sys.stderr)
            else:
                print(f"  OK   {name}")

    if failed:
        print(
            "\nCommit rejected: formatting violations detected.\n"
            "Run: uv run scripts/setup.py format\n"
            "Then stage the corrected files and commit again.",
            file=sys.stderr,
        )
        return 1

    print("All staged C/header files passed formatting checks.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Pre-commit check failed: {error}", file=sys.stderr)
        sys.exit(1)
'''

def run(*args, cwd=ROOT, capture=False):
    result = subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else None

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def resolve_edk2():
    if shutil.which("git") is None:
        raise RuntimeError("Git is required. Install git, then rerun setup.")

    answer = input("Existing EDK II path (Enter to clone beside Hypervyse): ").strip()
    edk2 = Path(answer).expanduser().resolve() if answer else ROOT.parent / f"edk2-{TAG}"

    if not edk2.exists():
        if answer:
            raise FileNotFoundError(f"EDK II directory does not exist: {edk2}")
        run(
            "git", "clone", "--depth", "1", "--branch", TAG, "--single-branch",
            "https://github.com/tianocore/edk2.git", edk2,
        )

    if not edk2.is_dir():
        raise ValueError(f"Not an EDK II directory: {edk2}")

    try:
        top_level = run("git", "rev-parse", "--show-toplevel", cwd=edk2, capture=True)
    except subprocess.CalledProcessError as error:
        raise ValueError(f"Not an EDK II Git checkout: {edk2}") from error

    if Path(top_level).resolve() != edk2.resolve():
        raise ValueError(f"Path is not a Git checkout root: {edk2}")

    head = run("git", "rev-parse", "HEAD", cwd=edk2, capture=True)

    try:
        expected = run(
            "git", "rev-parse", "--verify", f"refs/tags/{TAG}^{{commit}}",
            cwd=edk2, capture=True,
        )
    except subprocess.CalledProcessError as error:
        raise ValueError(f"Tag {TAG} is missing from {edk2}; fetch the tag first.") from error

    if head != expected:
        raise ValueError(f"The EDK II checkout must point to {TAG}; it was not changed.")

    if run("git", "status", "--porcelain", "--untracked-files=no", cwd=edk2, capture=True):
        raise ValueError("EDK II has tracked changes; the checkout was not changed.")

    return edk2

def read_release(edk2):
    dependency = edk2 / PLUGIN / "uncrustify_ext_dep.yaml"
    config = edk2 / PLUGIN / "uncrustify.cfg"

    if not dependency.is_file() or not config.is_file():
        raise FileNotFoundError(f"Missing Uncrustify metadata or config under {edk2 / PLUGIN}")

    with dependency.open("r", encoding="utf-8") as file:
        metadata = yaml.safe_load(file)

    if not isinstance(metadata, dict):
        raise TypeError(f"Invalid Uncrustify YAML metadata: {dependency}")

    url = metadata.get("source", "")
    digest = metadata.get("sha256", "")
    version = metadata.get("version", "")

    if (
        metadata.get("type") != "web"
        or metadata.get("compression_type") != "zip"
        or not isinstance(url, str)
        or not url.startswith("https://")
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(ch not in "0123456789abcdefABCDEF" for ch in digest)
        or not isinstance(version, str)
        or not version
    ):
        raise ValueError(f"Unsupported Uncrustify release metadata: {dependency}")

    return url, digest.lower(), version, config

def install_formatter(url, expected_sha, version):
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("This setup currently supports Linux x86-64 only.")

    destination = TOOLS / version / "uncrustify"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if STATE.is_file() and destination.is_file():
        previous = json.loads(STATE.read_text(encoding="utf-8"))

        if (
            previous.get("release_sha256") == expected_sha
            and previous.get("executable") == str(destination)
            and previous.get("binary_sha256") == sha256(destination)
        ):
            return destination

    print(f"Downloading Uncrustify {version} from the EDK II-pinned release...")

    with tempfile.TemporaryDirectory(prefix="hypervyse-uncrustify-", dir=destination.parent) as temporary:
        archive = Path(temporary) / "uncrustify.zip"

        with urllib.request.urlopen(url, timeout=90) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)

        if sha256(archive) != expected_sha:
            raise ValueError("Uncrustify archive checksum mismatch; refusing to install.")

        with zipfile.ZipFile(archive) as package:
            candidates = [
                entry for entry in package.infolist()
                if not entry.is_dir()
                and Path(entry.filename).name == "uncrustify"
                and Path(entry.filename).parent.name.lower()
                in {"linux-x86", "linux-x64", "linux-x86_64", "linux-amd64"}
            ]

            if len(candidates) != 1:
                raise ValueError(
                    f"Expected one Linux x86-64 Uncrustify executable, found {len(candidates)}."
                )

            staged = Path(temporary) / "uncrustify"

            with package.open(candidates[0]) as source, staged.open("wb") as output:
                shutil.copyfileobj(source, output)

            staged.chmod(0o755)
            os.replace(staged, destination)

    return destination

def install_hook():
    try:
        top_level = run("git", "rev-parse", "--show-toplevel", capture=True)
    except subprocess.CalledProcessError:
        print("Warning: No Git repository found; pre-commit hook not installed.")
        return

    if Path(top_level).resolve() != ROOT.resolve():
        print("Warning: Repository root mismatch; pre-commit hook not installed.")
        return

    configured = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False
    )

    if configured.returncode == 0 and configured.stdout.strip():
        hooks_dir = Path(configured.stdout.strip()).expanduser()
        if not hooks_dir.is_absolute():
            hooks_dir = ROOT / hooks_dir
        hook = hooks_dir / "pre-commit"
    else:
        hook = Path(run("git", "rev-parse", "--git-path", "hooks/pre-commit", capture=True))
        if not hook.is_absolute():
            hook = ROOT / hook

    hook = hook.resolve()
    hook.parent.mkdir(parents=True, exist_ok=True)

    if hook.exists():
        existing = hook.read_text(encoding="utf-8", errors="replace")

        if HOOK_MARKER not in existing:
            print(f"Warning: Existing pre-commit hook preserved: {hook}")
            print("Integrate the Hypervyse formatter check manually.")
            return

        if existing == HOOK_SCRIPT and os.access(hook, os.X_OK):
            print(f"Pre-commit hook already installed: {hook}")
            return

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=hook.parent,
        prefix=".pre-commit-",
        delete=False,
    ) as stream:
        stream.write(HOOK_SCRIPT)
        temporary = Path(stream.name)

    try:
        temporary.chmod(0o755)
        os.replace(temporary, hook)
    finally:
        temporary.unlink(missing_ok=True)

    print(f"Installed Git pre-commit hook: {hook}")
    print("Commits will now check staged .c and .h files using EDK II Uncrustify.")

def configure_qemu(edk2):
    config = ROOT / ".vscode/qemu.local.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    try:
        with config.open("x", encoding="utf-8") as stream:
            json.dump({"edk2": str(edk2), "toolchain": "GCC"}, stream, indent=2)
            stream.write("\n")
    except FileExistsError:
        print(f"Existing QEMU configuration preserved: {config}")
    else:
        print(f"Created QEMU configuration: {config}")

def setup():
    edk2 = resolve_edk2()
    url, archive_sha, version, config = read_release(edk2)
    executable = install_formatter(url, archive_sha, version)

    run(executable, "--version")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(
        json.dumps(
            {
                "edk2": str(edk2),
                "executable": str(executable),
                "config": str(config),
                "version": version,
                "release_sha256": archive_sha,
                "binary_sha256": sha256(executable),
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print(f"\nExecutable: {executable}\nConfiguration: {config}")

    configure_qemu(edk2)
    install_hook()

    print("\nReady. Format with: uv run scripts/setup.py format")

def format_package():
    if not STATE.is_file():
        raise FileNotFoundError("Formatter not configured. Run: uv run scripts/setup.py")

    settings = json.loads(STATE.read_text(encoding="utf-8"))
    executable = Path(settings["executable"])
    config = Path(settings["config"])

    if not executable.is_file() or not config.is_file():
        raise FileNotFoundError("Formatter or configuration is missing. Rerun setup.")

    package = (ROOT / "HypervysePkg").resolve()

    files = sorted(
        path for path in package.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.suffix in {".c", ".h"}
        and package in path.resolve().parents
    )

    for start in range(0, len(files), 100):
        run(
            executable,
            "-c", config,
            "--replace",
            "--no-backup",
            "--if-changed",
            *files[start:start + 100],
        )

    print(f"Formatted {len(files)} C/header files in HypervysePkg.")

def main():
    if not (ROOT / "HypervysePkg").is_dir():
        raise ValueError("Place this script in Hypervyse/scripts/.")

    if sys.argv[1:] == ["format"]:
        format_package()
    elif not sys.argv[1:]:
        setup()
    else:
        raise ValueError("Usage: uv run scripts/setup.py [format]")

if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        RuntimeError,
        subprocess.CalledProcessError,
        KeyboardInterrupt,
        zipfile.BadZipFile,
        yaml.YAMLError,
    ) as error:
        sys.exit(f"Stopped: {error}")
