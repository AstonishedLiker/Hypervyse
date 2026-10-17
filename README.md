# Hypervyse

<div>
  <img alt="Hit Counter Badge" src="https://hitscounter.dev/api/hit?url=https%3A%2F%2Fgithub.com%2FAstonishedLiker%2FHypervyse&label=views+%28day+%2F+all+time%29&icon=eye-fill&color=%232362a0&message=&style=for-the-badge&tz=UTC">
  <img alt="C Formatting Badge" src="https://img.shields.io/github/actions/workflow/status/AstonishedLiker/Hypervyse/edkii-package-ci.yml?style=for-the-badge&label=C%20formatting">
  <br/>
  <br/>
</div>

Hypervyse is a modular hypervisor framework targetting UEFI firmware that allows advanced instrumentation and remote administration by sideloading a tiny Linux VM using [buildroot](https://buildroot.org/).

Co-developed by [Alexis LECAM](https://github.com/AstonishedLiker) and [Evann BORDE](https://github.com/spxnso)

## Get started

To get started, do the following:

0. Install Linux (Windows is not supported), [`uv`](https://docs.astral.sh/uv/), [Git](https://git-scm.com/), [iASL](https://www.intel.com/content/www/us/en/content-details/772895/iasl-acpi-source-language-optimizing-compiler-disassembler-user-guide-doc.html), [GNU Make](https://www.gnu.org/software/make/), [NASM](https://www.nasm.us/) and [GCC](https://gcc.gnu.org/). Follow the appropriate steps for your Linux distribution

1. Clone the repository

   ```sh
   git clone https://github.com/AstonishedLiker/Hypervyse
   ```

2. Run the setup script from the repository root, and input the appropriate EDK II source tree path (of tag `edk2-stable202608`), or press enter otherwise, as indicated by the prompt.

   ```sh
   uv run --group dev scripts/setup.py
   ```

3. Read the [`docs`](./docs/) for definitions and guides (like auto-format with TianoCore Uncrustify)

4. Enjoy!

## License

This project uses a dual-license approach:

### Original Code (MIT License)

The Snake game application code written for this project is licensed under the **MIT License**.

See [the `LICENSE` file](./LICENSE) for the full MIT License text.

### EDK-II Components (BSD-2-Clause-Patent License)

This project builds upon and uses components from the EDK-II project, which is licensed under the **BSD-2-Clause-Patent License**. This includes:

- EDK2 libraries
- Build system and tooling

See [the `LICENSE.edk2` file](./LICENSE.edk2) for the full BSD-2-Clause-Patent License text.

## Acknowledgments

- [TianoCore EDK-II](https://github.com/tianocore/edk2) - The UEFI development framework
- [UEFI Forum](https://uefi.org/) - UEFI specifications
