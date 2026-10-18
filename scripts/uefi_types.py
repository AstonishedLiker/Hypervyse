"""UEFI type summaries for LLDB and VS Code's lldb-dap.

Adapted from EDK II EmulatorPkg/Unix/lldbefi.py:
https://github.com/tianocore/edk2/blob/master/EmulatorPkg/Unix/lldbefi.py
Copyright 2014 Apple Inc. All rights reserved.
SPDX-License-Identifier: BSD-2-Clause-Patent
See LICENSE.edk2 for the license text.
"""

import json

import lldb

MAX_STRING_UNITS = 1024
CATEGORY = "HypervyseUEFI"

def unsigned(value):
    error = lldb.SBError()
    result = value.GetValueAsUnsigned(error, 0)
    if not value.IsValid() or error.Fail():
        raise ValueError("unavailable")

    return result

def string_summary(value, width):
    """Read code units via SBData, which handles target byte order."""
    kind = value.GetType()
    pointer = kind.IsPointerType()
    array = kind.IsArrayType()
    try:
        if pointer and unsigned(value) == 0:
            return "NULL"

        limit = min((kind.GetByteSize() // width), MAX_STRING_UNITS) if array else MAX_STRING_UNITS
        if not pointer and not array:
            limit = 1

        units = []
        suffix = ""

        for index in range(limit):
            error = lldb.SBError()
            data = (value.GetPointeeData(index, 1) if pointer else
                    value.GetChildAtIndex(index).GetData() if array else value.GetData())
            unit = (data.GetUnsignedInt16(error, 0) if width == 2 else
                    data.GetUnsignedInt8(error, 0))
            if error.Fail():
                suffix = " <unreadable>"
                break

            if unit == 0 and (pointer or array):
                break

            units.append(unit)
        else:
            if pointer or (array and (kind.GetByteSize() // width) > limit):
                suffix = " <truncated>"

        # Packing the decoded units also combines UTF-16 surrogate pairs correctly.
        if width == 2:
            text = b"".join(unit.to_bytes(2, "little") for unit in units).decode("utf-16-le", "replace")
        else:
            # UEFI CHAR8 strings are ASCII; escape non-ASCII bytes without guessing UTF-8.
            text = bytes(units).decode("latin-1")

        quoted = json.dumps(text, ensure_ascii=(width == 1))
        return ("L" if width == 2 else "") + quoted + suffix
    except (ValueError, OverflowError):
        return "<unavailable>"

def char16_summary(value, internal_dict):
    return string_summary(value, 2)

def char8_summary(value, internal_dict):
    return string_summary(value, 1)

def guid_summary(value, internal_dict):
    try:
        a, b, c = [unsigned(value.GetChildMemberWithName(name)) for name in ("Data1", "Data2", "Data3")]
        tail = value.GetChildMemberWithName("Data4")
        d = [unsigned(tail.GetChildAtIndex(i)) for i in range(8)]
        return f"{a:08X}-{b:04X}-{c:04X}-{d[0]:02X}{d[1]:02X}-" + "".join(f"{v:02X}" for v in d[2:])
    except ValueError:
        return "<unavailable GUID>"

ERRORS = dict(enumerate((
    "LOAD_ERROR", "INVALID_PARAMETER", "UNSUPPORTED", "BAD_BUFFER_SIZE",
    "BUFFER_TOO_SMALL", "NOT_READY", "DEVICE_ERROR", "WRITE_PROTECTED",
    "OUT_OF_RESOURCES", "VOLUME_CORRUPTED", "VOLUME_FULL", "NO_MEDIA",
    "MEDIA_CHANGED", "NOT_FOUND", "ACCESS_DENIED", "NO_RESPONSE", "NO_MAPPING",
    "TIMEOUT", "NOT_STARTED", "ALREADY_STARTED", "ABORTED", "ICMP_ERROR",
    "TFTP_ERROR", "PROTOCOL_ERROR", "INCOMPATIBLE_VERSION", "SECURITY_VIOLATION",
    "CRC_ERROR", "END_OF_MEDIA",
), 1))
ERRORS.update({31: "END_OF_FILE", 32: "INVALID_LANGUAGE", 33: "COMPROMISED_DATA",
               34: "IP_ADDRESS_CONFLICT", 35: "HTTP_ERROR"})
WARNINGS = dict(enumerate(("UNKNOWN_GLYPH", "DELETE_FAILURE", "WRITE_FAILURE",
                           "BUFFER_TOO_SMALL", "STALE_DATA", "FILE_SYSTEM", "RESET_REQUIRED"), 1))

def status_summary(value, internal_dict):
    try:
        raw = unsigned(value)
        bits = value.GetType().GetByteSize() * 8
        if bits not in (32, 64):
            return None

        if raw == 0:
            return "EFI_SUCCESS"

        error = bool(raw & (1 << (bits - 1)))
        code = raw & ((1 << (bits - 1)) - 1)
        name = (ERRORS if error else WARNINGS).get(code)
        return ("EFI_" if error else "EFI_WARN_") + name if name else f"{'Error' if error else 'Warning'} ({raw:#x})"
    except ValueError:
        return "<unavailable status>"

def tpl_summary(value, internal_dict):
    try:
        tpl = unsigned(value)
        return {4: "TPL_APPLICATION", 8: "TPL_CALLBACK", 16: "TPL_NOTIFY",
                31: "TPL_HIGH_LEVEL"}.get(tpl, f"TPL {tpl}")
    except ValueError:
        return "<unavailable TPL>"

DEVICE_PATH_NAMES = {(1, 1): 'PCI_DEVICE_PATH', (1, 2): 'PCCARD_DEVICE_PATH', (1, 3): 'MEMMAP_DEVICE_PATH', (1, 4): 'VENDOR_DEVICE_PATH', (1, 5): 'CONTROLLER_DEVICE_PATH', (2, 1): 'ACPI_HID_DEVICE_PATH', (2, 2): 'ACPI_EXTENDED_HID_DEVICE_PATH', (2, 3): 'ACPI_ADR_DEVICE_PATH', (3, 1): 'ATAPI_DEVICE_PATH', (3, 18): 'SATA_DEVICE_PATH', (3, 2): 'SCSI_DEVICE_PATH', (3, 3): 'FIBRECHANNEL_DEVICE_PATH', (3, 4): 'F1394_DEVICE_PATH', (3, 5): 'USB_DEVICE_PATH', (3, 15): 'USB_CLASS_DEVICE_PATH', (3, 16): 'FW_SBP2_UNIT_LUN_DEVICE_PATH', (3, 17): 'DEVICE_LOGICAL_UNIT_DEVICE_PATH', (3, 6): 'I2O_DEVICE_PATH', (3, 11): 'MAC_ADDR_DEVICE_PATH', (3, 12): 'IPv4_DEVICE_PATH', (3, 9): 'INFINIBAND_DEVICE_PATH', (3, 14): 'UART_DEVICE_PATH', (3, 10): 'VENDOR_DEVICE_PATH', (3, 19): 'ISCSI_DEVICE_PATH', (4, 1): 'HARDDRIVE_DEVICE_PATH', (4, 2): 'CDROM_DEVICE_PATH', (4, 3): 'VENDOR_DEVICE_PATH', (4, 4): 'FILEPATH_DEVICE_PATH', (4, 5): 'MEDIA_PROTOCOL_DEVICE_PATH', (5, 1): 'BBS_BBS_DEVICE_PATH', (127, 255): 'EFI_DEVICE_PATH_PROTOCOL', (255, 255): 'EFI_DEVICE_PATH_PROTOCOL'}

def device_path_summary(value, internal_dict):
    try:
        kind = unsigned(value.GetChildMemberWithName("Type"))
        subtype = unsigned(value.GetChildMemberWithName("SubType"))
        length = value.GetChildMemberWithName("Length")
        size = unsigned(length.GetChildAtIndex(0)) | (unsigned(length.GetChildAtIndex(1)) << 8)
        name = DEVICE_PATH_NAMES.get((kind, subtype), f"Type={kind:#x}, SubType={subtype:#x}")

        return f"{name}, Length={size}" + (" <invalid length>" if size < 4 else "")
    except ValueError:
        return "<unavailable device path>"

def __lldb_init_module(debugger, internal_dict):
    # reloads replace only this module's category, leaving other formatters alone
    debugger.DeleteCategory(CATEGORY)
    category = debugger.CreateCategory(CATEGORY)
    options = lldb.eTypeOptionCascade | lldb.eTypeOptionSkipPointers | lldb.eTypeOptionSkipReferences
    for name in ("UINT8", "UINT16", "UINT32", "UINT64", "UINTN", "EFI_STATUS",
                 "EFI_PHYSICAL_ADDRESS", "EFI_VIRTUAL_ADDRESS", "EFI_LBA"):
        category.AddTypeFormat(lldb.SBTypeNameSpecifier(name), lldb.SBTypeFormat(lldb.eFormatHex, options))

    category.AddTypeFormat(lldb.SBTypeNameSpecifier("BOOLEAN"), lldb.SBTypeFormat(lldb.eFormatBoolean, options))
    for name, callback in (("EFI_GUID", "guid_summary"), ("EFI_STATUS", "status_summary"),
                           ("EFI_TPL", "tpl_summary"), ("EFI_DEVICE_PATH_PROTOCOL", "device_path_summary")):
        summary = lldb.SBTypeSummary.CreateWithFunctionName(f"{__name__}.{callback}", options)
        category.AddTypeSummary(lldb.SBTypeNameSpecifier(name), summary)

    for name, callback in (("CHAR16", "char16_summary"), ("CHAR8", "char8_summary")):
        summary = lldb.SBTypeSummary.CreateWithFunctionName(f"{__name__}.{callback}", options)
        # Match only these typedefs, not unrelated UINT16 buffers or CHAR16 **.
        pattern = rf"^(const |volatile |const volatile )?{name}( const| volatile)?( ?\*( const| volatile)?| ?\[[0-9]+\])?$"
        category.AddTypeSummary(lldb.SBTypeNameSpecifier(pattern, True), summary)

    category.SetEnabled(True)
