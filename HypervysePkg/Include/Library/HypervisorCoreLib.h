/** @file
  HypervisorCoreLib.h

  Common hypervisor interface across silicon vendors.

  Copyright (c) 2026 Alexis Lecam <alexis.lecam@hexaliker.fr>
  Copyright (c) 2026 Evann Borde <evann.borde@spxnso.fr>

  SPDX-License-Identifier: MIT
**/

#ifndef __HYPERVISORCORELIB_H__
#define __HYPERVISORCORELIB_H__

#include <Hypervyse/Status.h>

HYV_STATUS
EFIAPI
HyvBackendInitialize (
  VOID
  );

#endif
