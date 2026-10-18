## @file
#  HypervysePkg.dsc
#
#  Hypervyse Platform.
#
#  Copyright (c) 2026 Alexis Lecam <alexis.lecam@hexaliker.fr>
#  Copyright (c) 2026 Evann Borde <evann.borde@spxnso.fr>
#
#  SPDX-License-Identifier: MIT
##

[Defines]
  PLATFORM_NAME                  = HypervysePkg
  PLATFORM_GUID                  = 7D5614E2-75C3-491B-858D-63FBF49811D6
  PLATFORM_VERSION               = 1.0
  DSC_SPECIFICATION              = 0x00010005
  OUTPUT_DIRECTORY               = Build/HypervysePkg
  SUPPORTED_ARCHITECTURES        = X64
  BUILD_TARGETS                  = DEBUG|NOOPT|RELEASE
  SKUID_IDENTIFIER               = DEFAULT

  DEFINE SILICON_VENDOR          = INTEL
  DEFINE PAYLOAD                 = APPLICATION
  DEFINE DEBUG_LEVEL             = 0x00000000
  DEFINE QEMU_DEBUG_WAIT         = FALSE

[LibraryClasses]
  UefiApplicationEntryPoint|MdePkg/Library/UefiApplicationEntryPoint/UefiApplicationEntryPoint.inf
  UefiLib|MdePkg/Library/UefiLib/UefiLib.inf
  UefiBootServicesTableLib|MdePkg/Library/UefiBootServicesTableLib/UefiBootServicesTableLib.inf
  MemoryAllocationLib|MdePkg/Library/UefiMemoryAllocationLib/UefiMemoryAllocationLib.inf
  BaseMemoryLib|MdePkg/Library/BaseMemoryLibRepStr/BaseMemoryLibRepStr.inf
!if $(DEBUG_LEVEL) != 0
  DebugLib|OvmfPkg/Library/PlatformDebugLibIoPort/PlatformDebugLibIoPort.inf
  IoLib|MdePkg/Library/BaseIoLibIntrinsic/BaseIoLibIntrinsic.inf
  DebugPrintErrorLevelLib|MdePkg/Library/BaseDebugPrintErrorLevelLib/BaseDebugPrintErrorLevelLib.inf
  MemDebugLogLib|OvmfPkg/Library/MemDebugLogLib/MemDebugLogLibNull.inf
!else
  DebugLib|MdePkg/Library/BaseDebugLibNull/BaseDebugLibNull.inf
!endif
!if $(QEMU_DEBUG_WAIT) == TRUE
  NULL|HypervysePkg/Library/QemuDebugLib/QemuDebugLib.inf
!endif
  BaseLib|MdePkg/Library/BaseLib/BaseLib.inf
  PcdLib|MdePkg/Library/BasePcdLibNull/BasePcdLibNull.inf
  RegisterFilterLib|MdePkg/Library/RegisterFilterLibNull/RegisterFilterLibNull.inf
  PrintLib|MdePkg/Library/BasePrintLib/BasePrintLib.inf
  DevicePathLib|MdePkg/Library/UefiDevicePathLib/UefiDevicePathLib.inf
  UefiRuntimeServicesTableLib|MdePkg/Library/UefiRuntimeServicesTableLib/UefiRuntimeServicesTableLib.inf
  StackCheckLib|MdePkg/Library/StackCheckLibNull/StackCheckLibNull.inf

[PcdsFixedAtBuild]
  gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|$(DEBUG_LEVEL)
  gEfiMdePkgTokenSpaceGuid.PcdFixedDebugPrintErrorLevel|$(DEBUG_LEVEL)
!if $(DEBUG_LEVEL) != 0
  gEfiMdePkgTokenSpaceGuid.PcdDebugPropertyMask|0x1F
  gUefiOvmfPkgTokenSpaceGuid.PcdDebugIoPort|0x402
!else
  gEfiMdePkgTokenSpaceGuid.PcdDebugPropertyMask|0x00
!endif
!if $(QEMU_DEBUG_WAIT) == TRUE
!if $(DEBUG_LEVEL) == 0
  !error QEMU_DEBUG_WAIT requires a nonzero DEBUG_LEVEL
!endif
!endif

!if $(SILICON_VENDOR) == INTEL
  gHypervyseTokenSpaceGuid.PcdSiliconVendor|0x00
!elseif $(SILICON_VENDOR) == AMD
  gHypervyseTokenSpaceGuid.PcdSiliconVendor|0x01
!else
  !error Unsupported SILICON_VENDOR
!endif

[Components]
!if $(PAYLOAD) == APPLICATION
  HypervysePkg/Payload/UefiApplicationHvLoader/UefiApplicationHvLoader.inf
!else
  !error Unsupported PAYLOAD
!endif
