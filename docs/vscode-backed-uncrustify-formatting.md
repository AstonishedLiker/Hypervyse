# VS Code formatting

This guide will provide you with instructions on how to set up automatic source code formatting with Uncrustify.

# Steps

1. Run:

   ```bash
   uv run --group dev scripts/setup.py
   ```

   Setup requires Linux, Git and uv. It uses `edk2-stable202608` and downloads dependencies through Stuart, which may also acquire other EDK II tools.

2. Download the [Uncrustify VS Code extension](https://marketplace.visualstudio.com/items?itemName=zachflower.uncrustify).

3. Open `Hypervyse` as a VS Code folder. Create or merge these settings into `Hypervyse/.vscode/settings.json`. Replace the two paths with the executable and configuration paths printed by setup (or read the appropriate sections of `Hypervyse/out/formatter.json`):

   ```jsonc
   {
     "uncrustify.executablePath.linux": "/home/alexis/Documents/Programming/Firmware/Hypervyse/out/tools/uncrustify/73.0.11/uncrustify", // paste the value of `executable` in `Hypervyse/out/formatter.json`
     "uncrustify.configPath.linux": "/home/alexis/Documents/Programming/Firmware/edk2/.pytool/Plugin/UncrustifyCheck/uncrustify.cfg", // paste the value of `config` in `Hypervyse/out/formatter.json`
     "files.associations": {
      "*.h": "c"
     },
     "[c]": {
       "editor.defaultFormatter": "zachflower.uncrustify",
       "editor.formatOnSave": true
     }
   }
   ```

4. Open a C file and select **Format Document**, or save it.

To format all `.c` and `.h` files from the repository root:

```bash
uv run --group dev scripts/setup.py format
```

This rewrites files in place. Review changes with `git diff -- HypervysePkg`.
