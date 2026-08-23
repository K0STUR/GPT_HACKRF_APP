# Fix7b CI intent

Fix7b preserves the Fix7 M4 receive improvements (2048-sample pre-trigger history, safe BasebandThread/RSSIThread initialization order, lower energy threshold, 1000 ms/channel scan dwell) while removing the new M0 HunterTrigger MessageHandlerRegistration that coincided with the +4-byte core-rodata drift in Fix7.

C/D/M telemetry is transported through the existing FSKPacket path already used by Fix6. WireApReport v3 adds 14-bit-compatible capture/decode totals and bit7 marks diagnostic-only reports.

Acceptance gate remains strict: stock n_260808 version/tag/checksum, zero shared-core symbol drift, zero rebasing patches, zero unresolved/ambiguous imports, stock/mod operator new at 0x7ee24, no retained to_string_mac_address dependency.
