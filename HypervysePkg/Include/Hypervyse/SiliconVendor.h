/** @file
  SiliconVendor.h

  Supported silicon vendors.

  Copyright (c) 2026 Alexis Lecam <alexis.lecam@hexaliker.fr>
  Copyright (c) 2026 Evann Borde <evann.borde@spxnso.fr>

  SPDX-License-Identifier: MIT
**/

#pragma once

// Supported silicon vendors
typedef enum {
  Intel,
  Amd
} HYV_SILICON_VENDOR;

#define HYV_BUILD_SILICON_VENDOR  ((HYV_SILICON_VENDOR)FixedPcdGet8 (PcdSiliconVendor))
