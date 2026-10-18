#!/usr/bin/env -S uv run --group dev --script
# noqa: EXE001
"""Build the application payload and run it under OVMF/KVM on Linux.

uv run scripts/qemu.py
Optional machine-local settings: .vscode/qemu.local.json
"""

import fcntl
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DSC = Path("HypervysePkg/HypervysePkg.dsc")
INF = Path("HypervysePkg/Payload/UefiApplicationHvLoader/UefiApplicationHvLoader.inf")
OUT = ROOT / "out/qemu"
PORT = 1234
BUILD_WORKSPACE = OUT / "workspace"

def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True, **kwargs)

def resolve(value):
    path = Path(value).expanduser()
    return (ROOT / path).resolve()

def host_vendor(cpuinfo):
    vendors = set(re.findall(r"^vendor_id\s*:\s*(\S+)", cpuinfo, re.MULTILINE))
    if vendors == {"GenuineIntel"}:
        return "INTEL", "vmx", "kvm_intel"
    if vendors == {"AuthenticAMD"}:
        return "AMD", "svm", "kvm_amd"
    raise ValueError(f"Unsupported CPU vendor(s): {vendors}")

def build_environment(edk2):
    env = os.environ.copy()
    env.update(
        WORKSPACE=str(BUILD_WORKSPACE),
        PACKAGES_PATH=os.pathsep.join([str(ROOT), str(edk2)]),
        EDK_TOOLS_PATH=str(edk2 / "BaseTools"),
        PYTHON_COMMAND=sys.executable,
    )
    env.pop("EDK_TOOLS_BIN", None)
    return env

def all_debug_levels(edk2):
    text = (edk2 / "MdePkg/Include/Library/DebugLib.h").read_text()
    mask = 0
    for name, value in re.findall(r"^#define\s+(DEBUG_\w+)\s+(0x[0-9A-Fa-f]+)", text, re.MULTILINE):
        if not name.startswith("DEBUG_PROPERTY_"):
            mask |= int(value, 16)
    if not mask & 4:
        raise ValueError("Cannot determine EDK II's DEBUG_LOAD mask.")
    return mask

def build_platform(edk2, toolchain, dsc, *defines):
    mask = f"0x{all_debug_levels(edk2):08X}"
    if Path(dsc) == DSC:
        debug_options = ["-D", f"DEBUG_LEVEL={mask}"]
    else:
        debug_options = [
            "--pcd", f"gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel={mask}",
            "--pcd", f"gEfiMdePkgTokenSpaceGuid.PcdFixedDebugPrintErrorLevel={mask}",
            "--pcd", "gEfiMdePkgTokenSpaceGuid.PcdDebugPropertyMask=0x1F",
        ]
    run(
        "bash", "-c",
        'source "$1/edksetup.sh" BaseTools || exit $?\nshift\nbuild "$@"',
        "hypervyse-build", edk2,
        "-p", dsc, "-a", "X64", "-b", "NOOPT", "-t", toolchain,
        "-n", str(os.cpu_count() or 1),
        *debug_options, *defines, env=build_environment(edk2),
    )

def symbol_index(builds):
    from uefi_symbols import pe_sections
    entries = {}
    for build in builds:
        # Use the authoritative top-level X64 outputs, not duplicate/stale intermediates.
        for image in sorted((build / "X64").glob("*.efi")):
            symbols = image.with_suffix(".debug")
            if symbols.is_file():
                entries[image.name.lower()] = {
                    "image": str(image), "symbols": str(symbols),
                    "sections": pe_sections(image),
                }
    return entries

def main():
    if sys.argv[1:]:
        raise ValueError("Usage: uv run scripts/qemu.py")
    debug = os.environ.get("HYV_VSCODE_DEBUG") == "1"
    print("Preparing Hypervyse QEMU...", flush=True)

    if sys.platform != "linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise ValueError("This launcher requires Linux x86-64 with KVM.")

    if not (ROOT / DSC).is_file():
        raise ValueError(
            f"Missing {ROOT / DSC}; place this script in Hypervyse/scripts/."
        )

    OUT.mkdir(parents=True, exist_ok=True)

    # prevent concurrent launches from modifying the same build/staging files
    with (OUT / "run.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(
                "Another Hypervyse QEMU task is already running."
            ) from None
        launch(debug)

def launch(debug):
    config_path = ROOT / ".vscode/qemu.local.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    edk2 = resolve(config.get("edk2", "../edk2"))

    if not (edk2 / "edksetup.sh").is_file():
        raise ValueError("EDK II not found. Set edk2 in .vscode/qemu.local.json.")

    if not os.access(edk2 / "BaseTools/Source/C/bin/GenFw", os.X_OK):
        raise ValueError(f'Build BaseTools first: make -C "{edk2 / "BaseTools"}"')

    if not shutil.which("qemu-system-x86_64"):
        raise ValueError("Install qemu-system-x86_64 and a graphical display backend.")

    if not os.access("/dev/kvm", os.R_OK | os.W_OK):
        raise ValueError(
            "/dev/kvm is not accessible. Enable KVM and grant your user access."
        )

    cpuinfo = Path("/proc/cpuinfo").read_text()
    vendor, feature, module = host_vendor(cpuinfo)
    flags = re.findall(r"^flags\s*:\s*(.*)$", cpuinfo, re.MULTILINE)
    if not flags or any(feature not in line.split() for line in flags):
        raise ValueError(f"The host does not expose {feature} on every processor.")

    nested = Path(f"/sys/module/{module}/parameters/nested")
    if nested.exists() and nested.read_text().strip().lower() not in {"y", "1"}:
        raise ValueError(f"Nested virtualization is disabled: {nested}")

    if debug:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", PORT))

    toolchain = config.get("toolchain", "GCC")
    if not re.fullmatch(r"[A-Za-z0-9_]+", toolchain):
        raise ValueError("Invalid toolchain tag.")

    # This dedicated workspace contains only reproducible launcher build products.
    if BUILD_WORKSPACE.is_symlink():
        raise ValueError("Refusing to clean a symlinked build workspace.")
    if BUILD_WORKSPACE.exists():
        shutil.rmtree(BUILD_WORKSPACE)

    BUILD_WORKSPACE.mkdir()
    print(f"Rebuilding OVMF from scratch: {edk2} / NOOPT / {toolchain}", flush=True)
    build_platform(edk2, toolchain, "OvmfPkg/OvmfPkgX64.dsc",
                   "-D", "SOURCE_DEBUG_ENABLE=FALSE", "-D", "DEBUG_TO_MEM=FALSE")

    ovmf = BUILD_WORKSPACE / "Build/OvmfX64" / f"NOOPT_{toolchain}"
    code, variables = ovmf / "FV/OVMF_CODE.fd", ovmf / "FV/OVMF_VARS.fd"
    if not code.is_file() or not variables.is_file():
        raise ValueError(f"OVMF did not produce the expected CODE/VARS pair in {ovmf / 'FV'}.")

    print(f"Building {DSC}: NOOPT / {toolchain} / {vendor} / APPLICATION", flush=True)
    build_platform(
        edk2,
        toolchain,
        DSC,
        "-D", f"QEMU_DEBUG_WAIT={str(debug).upper()}",
        "-D", f"SILICON_VENDOR={vendor}", "-D", "PAYLOAD=APPLICATION"
    )

    match = re.search(r"^\s*BASE_NAME\s*=\s*(\S+)", (ROOT / INF).read_text(), re.MULTILINE)
    if not match:
        raise ValueError(f"No BASE_NAME found in {INF}.")

    name = match[1]
    application = BUILD_WORKSPACE / "Build/HypervysePkg" / f"NOOPT_{toolchain}"
    build = application / "X64"
    image = build / f"{name}.efi"
    if not image.is_file():
        raise ValueError(f"Expected built image not found: {image}")

    boot = OUT / "esp/EFI/BOOT"
    boot.mkdir(parents=True, exist_ok=True)
    shutil.copy2(image, boot / "BOOTX64.EFI")

    if debug:
        entries = symbol_index([ovmf, application])
        if image.name.lower() not in entries:
            raise ValueError(f"Missing matching .debug file for {image.name}.")
        entry = re.search(r"^\s*ENTRY_POINT\s*=\s*(\S+)", (ROOT / INF).read_text(), re.MULTILINE)
        if not entry:
            raise ValueError(f"No ENTRY_POINT in {INF}.")
        (OUT / "symbols.json").write_text(json.dumps({
            "application": image.name.lower(), "entry": entry[1],
            "log": str(OUT / "firmware.log"), "modules": entries,
        }, indent=2) + "\n")

    # Reset only our disposable NVRAM copy on every run
    nvram = OUT / "OVMF_VARS.fd"
    shutil.copy2(variables, nvram)

    for path in (code, nvram, OUT):
        if "," in str(path):
            raise ValueError(
                "QEMU drive paths containing commas are not supported by this launcher."
            )

    command = [
        "qemu-system-x86_64",
        "-name", "Hypervyse",
        "-machine", "q35",
        "-accel", "kvm",
        "-cpu", f"host,{feature}=on",
        "-smp", "1",
        "-m", "2048",
        "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
        "-drive", f"if=pflash,format=raw,unit=1,file={nvram}",
        "-drive", f"format=raw,file=fat:rw:{OUT / 'esp'}",
        "-net", "none",
        "-serial", f"file:{OUT / 'serial.log'}",
        "-debugcon", f"file:{OUT / 'firmware.log'}",
        "-global",
        "isa-debugcon.iobase=0x402",
        "-no-reboot"
    ]

    if debug:
        command += ["-S", "-gdb", f"tcp:127.0.0.1:{PORT}"]

    print(f"Starting QEMU with {vendor}; close its window to stop.", flush=True)

    with subprocess.Popen(command, cwd=ROOT) as process:
        try:
            if debug:
                # Observe LISTEN without making a connection to the debugger stub.
                deadline = time.monotonic() + 15
                while True:
                    if process.poll() is not None:
                        raise ValueError(
                            f"QEMU exited before debugger readiness: {process.returncode}"
                        )

                    listeners = Path("/proc/net/tcp").read_text().splitlines()[1:]
                    if any(
                        line.split()[1] == f"0100007F:{PORT:04X}"
                        and line.split()[3] == "0A"
                        for line in listeners
                    ):
                        break

                    if time.monotonic() >= deadline:
                        raise ValueError(
                            "Timed out waiting for the QEMU debugger port."
                        )
                    time.sleep(0.1)
                print("QEMU debug server ready", flush=True)

            result = process.wait()
            if result:
                raise ValueError(f"QEMU exited with status {result}.")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f"Stopped: {error}")
