/** @file
  QemuDebugLib.c

  Rendezvous with the QEMU debugger before the application entry point.
  cf. docs/qemu-debugging.md

  Copyright (c) 2026 Alexis Lecam <alexis.lecam@hexaliker.fr>
  Copyright (c) 2026 Evann Borde <evann.borde@spxnso.fr>

  SPDX-License-Identifier: MIT
**/

#include <Library/BaseLib.h>
#include <Library/DebugLib.h>
#include <Library/UefiBootServicesTableLib.h>

#include <Protocol/LoadedImage.h>

#include <Uefi.h>

STATIC volatile UINT8  mHyvQemuDebuggerWait = 1;

EFI_STATUS
EFIAPI
HyvQemuDebugConstructor (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_STATUS                 Status;
  EFI_LOADED_IMAGE_PROTOCOL  *Image;

  Status = gBS->HandleProtocol (
                  ImageHandle,
                  &gEfiLoadedImageProtocolGuid,
                  (VOID **)&Image
                  );

  ASSERT_EFI_ERROR (Status);
  if (EFI_ERROR (Status)) {
    CpuDeadLoop ();
  }

  //
  // `DEBUG_ERROR` is to make the message show regardless of debug level.
  //
  DEBUG ((
    DEBUG_ERROR,
    "%a: HYV_DEBUG_READY ImageBase=0x%p Wait=0x%p\n",
    __func__,
    Image->ImageBase,
    (VOID *)&mHyvQemuDebuggerWait
    ));

  while (mHyvQemuDebuggerWait != 0) {
    CpuPause ();
  }

  DEBUG ((DEBUG_INFO, "%a: HYV Constructor exiting...\n", __func__));
  return EFI_SUCCESS;
}
