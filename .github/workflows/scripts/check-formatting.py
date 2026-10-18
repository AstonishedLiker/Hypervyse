#!/usr/bin/env -S uv run --group dev
# noqa: EXE001
"""Check all Git-tracked C sources and headers without changing files."""
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[3]
    settings = json.loads((root / "out/formatter.json").read_text())
    executable = Path(settings["executable"])
    config = Path(settings["config"])

    if not executable.is_file() or not config.is_file():
        sys.exit("Formatter executable or configuration is missing.")

    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    files = sorted(
        os.fsdecode(name) for name in tracked.split(b"\0")
        if name and Path(os.fsdecode(name)).suffix.lower() in {".c", ".h"}
    )
    failed = []

    for name in files:
        path = root / name
        if path.is_symlink() or not path.is_file():
            print(f"FAIL {name!r}: not a regular source file", flush=True)
            failed.append(name)
            continue

        result = subprocess.run(
            [
                str(executable), "-c", str(config),
                "--check", "-l", "C", "-f", str(path),
            ],
            cwd=root,
            check=False
        )

        if result.returncode:
            failed.append(name)
            print(f"FAIL {name!r}", flush=True)

    print(f"Checked {len(files)} C/header files; {len(failed)} failed.")
    if failed:
        print("Files requiring attention:")
        for name in failed:
            print(f"  {name!r}")

    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
