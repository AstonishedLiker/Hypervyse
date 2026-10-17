/** @file
  UefiApplicationHvLoader.c

  Loads Hypervyse through a UEFI application.

  Copyright (c) 2026 Alexis Lecam <alexis.lecam@hexaliker.fr>
  Copyright (c) 2026 Evann Borde <evann.borde@spxnso.fr>

  SPDX-License-Identifier: MIT
**/

#include <Hypervyse/SiliconVendor.h>

#include <Library/UefiLib.h>
#include <Library/PcdLib.h>

#include <Uefi.h>

EFI_STATUS
EFIAPI
UefiMain (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  Print (
    L"Hi from UefiApplicationHvLoader.efi! HYV_BUILD_SILICON_VENDOR: '%s'\n",
    HYV_BUILD_SILICON_VENDOR == 0x0 ? L"Intel" : L"AMD"
    );

  return EFI_SUCCESS;
}
