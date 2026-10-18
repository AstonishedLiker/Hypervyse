"""LLDB commands for the QEMU development session; PE/log parsing is standalone."""
import json
import re
import shlex
import struct
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'out/qemu/symbols.json'
READY = re.compile(r'HYV_DEBUG_READY ImageBase=0x([0-9a-fA-F]+) Wait=0x([0-9a-fA-F]+)\r?\n')
LOAD = re.compile(r'Loading driver at 0x\s*([0-9a-fA-F]+)\s+EntryPoint=0x\s*[0-9a-fA-F]+\s+([^\r\n ]+\.efi)', re.IGNORECASE)
_loaded = {}

def pe_sections(path):
    data = Path(path).read_bytes()
    if data[:2] != b'MZ' or len(data) < 64:
        raise ValueError(f'Not a PE image: {path}')

    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if data[pe:pe + 4] != b'PE\0\0':
        raise ValueError(f'Invalid PE signature: {path}')

    count = struct.unpack_from('<H', data, pe + 6)[0]
    optional_size = struct.unpack_from('<H', data, pe + 20)[0]
    table = pe + 24 + optional_size
    if table + 40 * count > len(data):
        raise ValueError(f'Truncated PE section table: {path}')

    sections = {}
    for i in range(count):
        offset = table + i * 40
        name = data[offset:offset + 8].split(b'\0')[0].decode('ascii')
        size, rva = struct.unpack_from('<II', data, offset + 8)
        sections[name] = {'rva': rva, 'size': size}

    return sections

def log_images(text):
    # Later loads supersede earlier addresses for the same image name.
    return {name.lower(): int(base, 16) for base, name in LOAD.findall(text)}

def check(error):
    if error.Fail():
        raise RuntimeError(str(error))

def load_module(target, process, record, base, required=False):
    import lldb
    key = record['symbols']
    if _loaded.get(key) == base:
        return False

    error = lldb.SBError()
    if process.ReadMemory(base, 2, error) != b'MZ' or error.Fail():
        if required:
            raise RuntimeError(f'Cannot read the application PE header at {base:#x}.')
        return False  # Early firmware images may already have been discarded.

    # Reuse a module already present in this target, if any.
    module = target.FindModule(lldb.SBFileSpec(key))
    if not module.IsValid():
        module = target.AddModule(key, None, None)

    if not module.IsValid():
        raise RuntimeError(f'LLDB cannot load symbols: {key}')

    sections = record['sections']
    text = module.FindSection('.text')

    if '.text' not in sections or not text.IsValid():
        raise RuntimeError(f'Missing .text section: {key}')

    slide = base + sections['.text']['rva'] - text.GetFileAddress()
    if slide < 0:
        raise RuntimeError(f'Unsupported negative image slide: {key}')

    check(target.SetModuleLoadAddress(module, slide))

    # set matching sections explicitly, ELF and PE section layouts can differ
    for name, section_info in sections.items():
        section = module.FindSection(name)
        if section.IsValid() and section.GetByteSize():
            check(target.SetSectionLoadAddress(section, base + section_info['rva']))

    _loaded[key] = base
    return True

def sync_modules(debugger, data, log, app_base=None):
    target = debugger.GetSelectedTarget()
    process = target.GetProcess()
    images = log_images(log)
    if app_base is not None:
        images[data['application']] = app_base

    loaded = 0
    for name, base in images.items():
        record = data['modules'].get(name)
        if record:
            try:
                loaded += load_module(target, process, record, base, name == data['application'])
            except RuntimeError:
                if name == data['application']:
                    raise
                # Other firmware images are best effort, not the rendezvous target.
    return loaded

def sync(debugger, command, result, internal_dict):
    try:
        data = json.loads(MANIFEST.read_text())
        count = sync_modules(debugger, data, Path(data['log']).read_text(errors='replace'))
        if count:
            result.AppendMessage(f'Loaded/updated {count} EFI symbol modules.')
    except (OSError, ValueError, RuntimeError) as error:
        result.SetError(str(error))

def bootstrap(debugger, command, result, internal_dict):
    import lldb
    previous_async = debugger.GetAsync()
    process = debugger.GetSelectedTarget().GetProcess()

    try:
        _loaded.clear()
        data = json.loads(MANIFEST.read_text())
        debugger.SetAsync(True)
        check(process.Continue())
        deadline = time.monotonic() + 180
        text = ''
        with Path(data['log']).open(errors='replace') as log:
            while True:
                text += log.read()
                ready = READY.search(text)
                if ready:
                    break
                if process.GetState() in (lldb.eStateExited, lldb.eStateDetached, lldb.eStateCrashed):
                    raise RuntimeError('QEMU disconnected or failed before the application rendezvous.')
                if time.monotonic() > deadline:
                    raise RuntimeError('Application rendezvous timed out. Inspect out/qemu/firmware.log for firmware assertions or boot failures.')
                time.sleep(0.1)

        check(process.Stop())
        deadline = time.monotonic() + 10
        while process.GetState() != lldb.eStateStopped:
            if time.monotonic() > deadline:
                raise RuntimeError('QEMU did not stop for symbol loading.')
            time.sleep(0.05)

        base, wait = (int(value, 16) for value in ready.groups())
        app = data['modules'][data['application']]

        # yhe write must target a byte in this exact application's writable data
        pe_data = app['sections'].get('.data')
        if not pe_data or not base + pe_data['rva'] <= wait < base + pe_data['rva'] + pe_data['size']:
            raise RuntimeError('Debugger wait address lies outside the application .data section.')

        count = sync_modules(debugger, data, text, base)
        target = debugger.GetSelectedTarget()

        if shlex.split(command) != ['--run']:
            breakpoint = target.BreakpointCreateByName(data['entry'], Path(app['symbols']).name)
            breakpoint.SetOneShot(True)
            if breakpoint.GetNumLocations() == 0:
                raise RuntimeError(f'Cannot resolve application entry point {data["entry"]}.')

        error = lldb.SBError()
        current = process.ReadMemory(wait, 1, error)

        check(error)
        if current != b'\x01':
            raise RuntimeError('Application rendezvous byte is not in its expected waiting state.')

        written = process.WriteMemory(wait, b'\x00', error)
        check(error)

        if written != 1:
            raise RuntimeError('Could not release application rendezvous.')

        result.AppendMessage(f'Hypervyse loaded at {base:#x}; loaded {count} symbol modules.')
        # The DAP postRunCommands continuation happens after this command returns
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        if process.IsValid() and process.GetState() == lldb.eStateRunning:
            process.Stop()
        result.SetError(str(error))
    finally:
        debugger.SetAsync(previous_async)

def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand(f'command script add -f {__name__}.bootstrap hyv-bootstrap')
    debugger.HandleCommand(f'command script add -f {__name__}.sync hyv-sync')
