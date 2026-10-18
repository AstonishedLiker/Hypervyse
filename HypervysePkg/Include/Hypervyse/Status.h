/** @file
  Status.h

  Hypervyse status codes.

  Copyright (c) 2026 Alexis Lecam <alexis.lecam@hexaliker.fr>
  Copyright (c) 2026 Evann Borde <evann.borde@spxnso.fr>

  SPDX-License-Identifier: MIT
**/

#pragma once

typedef enum {
  HyvStatusSuccess = 0,
  HyvStatusInvalidParameter,
  HyvStatusUnsupported,
  HyvStatusOutOfResources,
  HyvStatusInvalidState,
  HyvStatusHardwareError
} HYV_STATUS;
