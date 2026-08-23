#pragma once
#include <cstdint>

namespace wifiaim {
#pragma pack(push, 1)
struct WireApReport {
    uint8_t magic[4]{'W','A','I','M'};
    uint8_t version{3};
    uint8_t channel{0};
    int16_t packet_db_x10{-1200};
    uint8_t bssid[6]{};
    uint8_t ssid_len{0};
    char ssid[32]{};
    uint8_t flags{0}; // bit0 hidden, bit7 diagnostic-only (no AP payload)
    uint8_t phy_rate_mbps{0};
    uint16_t capture_total{0};
    uint16_t decode_total{0};
};
#pragma pack(pop)
static_assert(sizeof(WireApReport) <= 64, "WiFiAim report must remain small");
}
