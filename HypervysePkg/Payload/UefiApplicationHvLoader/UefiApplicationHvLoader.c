/** @file
  UefiApplicationHvLoader.c

  Loads Hypervyse through a UEFI application.

  Copyright (c) 2026 Alexis Lecam <alexis.lecam@hexaliker.fr>
  Copyright (c) 2026 Evann Borde <evann.borde@spxnso.fr>

  SPDX-License-Identifier: MIT
**/

#include <Hypervyse/SiliconVendor.h>

#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>
#include <Library/DebugLib.h>
#include <Library/UefiLib.h>
#include <Library/PcdLib.h>

#include <Uefi.h>

EFI_STATUS
EFIAPI
UefiApplicationHvLoaderMain (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  DEBUG ((DEBUG_INFO, "%a: Loaded (ImageHandle: %p)", __func__, ImageHandle));

  return EFI_SUCCESS;
}
