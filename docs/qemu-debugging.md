# Hypervyse in QEMU with LLDB DAP

Select **Hypervyse: debug application** in VS Code's Run and Debug dropdown and press **F5**. The task rebuilds OVMF and Hypervyse, starts QEMU, loads relocated symbols, and stops at `UefiApplicationHvLoaderMain`. Source breakpoints, stepping, variables and registers are then available without entering image addresses manually.

**Hypervyse: launch QEMU** performs the same preparation and continues execution. For a standalone run, use **Tasks: Run Task > Hypervyse: launch QEMU**, or `uv run scripts/qemu.py`.

## Requirements

Use Linux x86-64 with QEMU's x86 system emulator, a graphical display backend, accessible `/dev/kvm`, and nested virtualization enabled.

For Intel, inspect `/sys/module/kvm_intel/parameters/nested`; for AMD, inspect `/sys/module/kvm_amd/parameters/nested`. The launcher checks the host vendor and builds with `SILICON_VENDOR=INTEL` or `AMD`, and `PAYLOAD=APPLICATION`. It uses KVM with the corresponding VMX or SVM CPU feature exposed.

Install the `llvm-vs-code-extensions.lldb-dap` extension. In personal User Settings, point it to the installed adapter, for example:

```json
{
  "lldb-dap.executable-path": "/usr/bin/lldb-dap-19"
}
```

## Local configuration

Running `uv run --group dev scripts/setup.py` creates `.vscode/qemu.local.json` with the selected EDK II checkout and the `GCC` toolchain tag. An existing file is preserved. Edit it to change either setting. You can also create it manually from `.vscode/qemu.local.example.json`:

```json
{
  "edk2": "../edk2",
  "toolchain": "GCC"
}
```

## Fresh firmware builds

Every launch removes and recreates the dedicated `out/qemu/workspace/` build workspace, then builds `OvmfPkg/OvmfPkgX64.dsc` from the configured EDK II checkout. This rebuilds OVMF modules and firmware volumes from scratch.

Both OVMF and the application use `NOOPT`, which retains debugging support without the usual optimization settings. The launcher enables:

- Every numeric debug-message level defined by the checkout's `DebugLib.h`, including `DEBUG_LOAD`, `DEBUG_INFO` and `DEBUG_VERBOSE`.
- Both dynamic and fixed debug-print masks.
- Assertions, debug printing, `DEBUG_CODE`, freed-memory clearing, and assertion breakpoints through `PcdDebugPropertyMask=0x1F`.
- OVMF debug-port logging, including image load addresses.

The separate EDK II serial source-debug agent remains disabled: QEMU's debugger stub supplies the connection. Memory-buffer logging is also left disabled so messages go directly to the debug port.

The launcher builds `HypervysePkg/HypervysePkg.dsc` directly with `-D DEBUG_LEVEL=<mask>`. This DSC macro sets both debug-print masks and selects OVMF's debug-port `DebugLib` when nonzero. Its default is zero, which selects the null instance. The DSC supports `NOOPT` directly. Builds remain isolated under `out/qemu/workspace/Build/HypervysePkg/`.

The launcher also passes `-D QEMU_DEBUG_WAIT=TRUE` for debugger launches, linking the rendezvous constructor. Standalone launches pass `FALSE`. It builds `HypervysePkg/Payload/UefiApplicationHvLoader/UefiApplicationHvLoader.inf`; the image name and entry point are read from that INF.

## Automatic symbol loading

Symbols are loaded into LLDB, which controls QEMU through its debugger connection.

The debugger build links `QemuDebugLib`, a small library constructor that runs before the application entry point. It emits the application's actual image base and the address of a one-byte wait flag to `firmware.log`, then waits. This prevents a short application from returning before LLDB has attached its symbols. Normal standalone runs do not link this constructor.

The LLDB helper starts the paused VM, waits for that marker, stops the CPU, and loads the matching `.debug` artifact. Runtime section addresses come from the built PE image's section RVAs and actual load base. It sets matching section addresses explicitly rather than assuming ImageBase is always the ELF relocation slide. It then releases the wait flag and sets a one-shot breakpoint at the application's entry point for the debug configuration.

The helper also loads matching firmware DXE modules listed in OVMF's image-load log when their PE headers remain readable. A stop hook checks for additional logged loads whenever execution stops. Firmware symbol discovery is best effort. Reloaded images with an unchanged name are tracked at their latest logged base. A separately relocated Hypervyse core needs its own image-load notification and symbols.

If firmware asserts or the application is not reached, inspect `firmware.log`. The helper has a three-minute rendezvous timeout.

## Files and misc

| Path | Contents |
| --- | --- |
| `out/qemu/workspace/Build/OvmfX64/NOOPT_<tag>/FV/` | Fresh OVMF CODE and VARS images |
| `out/qemu/workspace/Build/HypervyseQemu/NOOPT_<tag>/` | Application and symbols |
| `out/qemu/esp/EFI/BOOT/BOOTX64.EFI` | Application staged for firmware boot |
| `out/qemu/OVMF_VARS.fd` | Disposable writable variable store, reset each launch |
| `out/qemu/firmware.log` | OVMF and application debug-port output |
| `out/qemu/serial.log` | Serial output |
| `out/qemu/symbols.json` | Symbol artifacts and PE section metadata for this build |

QEMU uses one vCPU, 2 GiB RAM, no network and a read-only directory-backed FAT boot disk. No normal OS disk is attached. If Hypervyse returns, firmware decides what happens next.

Close QEMU's window or terminate its task before launching again. Stopping LLDB alone can leave QEMU running. Do not keep persistent data in the generated workspace or variable store.

## UEFI values in Variables and Watch

Both launch configurations import `scripts/uefi_types.py` automatically.

The dedicated `HypervyseUEFI` category provides:

- `CHAR16` and `CHAR8` scalar, pointer, and array summaries, including const-qualified types.
- GUID strings, named EFI status codes, and TPL names.
- Boolean values and hexadecimal unsigned integers, statuses, and addresses.
- Device-path node names and lengths, with the original fields still expandable.

String reads stop at a terminator, the array boundary, or 1,024 code units. Null pointers display `NULL`; inaccessible memory and truncated strings are marked explicitly. UTF-16 pairs are decoded together. Typedef information must be present in the debug symbols for matching to work.

To temporarily disable these summaries, enter the following in the Debug Console, including the leading backtick:

```text
`type category disable HypervyseUEFI
```

Use `type category enable HypervyseUEFI` with the same prefix to re-enable them.

This module adapts the type-formatting portion of [EDK II's `EmulatorPkg/Unix/lldbefi.py`](https://github.com/tianocore/edk2/blob/master/EmulatorPkg/Unix/lldbefi.py) for Python 3. It retains the upstream copyright and BSD-2-Clause-Patent license (`LICENSE.edk2`).

Emulator-specific symbol-loading hooks are not imported; `uefi_symbols.py` continues to manage QEMU symbol relocation. The adaptation fixes the device-path length calculation and displays numeric GUIDs even without a GUID-name database.