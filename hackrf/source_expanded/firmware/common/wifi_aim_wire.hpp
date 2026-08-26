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

// Fix8v-DIAG profiler pages reuse diagnostic-only WireApReport payload bytes.
// No stock message ABI or WireApReport layout changes. Counters 0..2 occupy
// bssid[0..5], counters 3..14 occupy ssid[0..23].
enum ProfilerCounter : uint8_t {
    PROFILE_ENERGY = 0,
    PROFILE_SHADOW_256,
    PROFILE_SHADOW_128,
    PROFILE_STF,
    PROFILE_LTF,
    PROFILE_SIGNAL_VITERBI,
    PROFILE_SIGNAL_PARITY,
    PROFILE_RATE_LENGTH,
    PROFILE_DATA_VITERBI,
    PROFILE_SERVICE,
    PROFILE_PROTOCOL,
    PROFILE_MANAGEMENT,
    PROFILE_BEACON_PROBE,
    PROFILE_SSID,
    PROFILE_FINAL_AP,
    PROFILE_COUNTER_COUNT
};

#pragma pack(push, 1)
struct ProfilerStatsWire {
    uint16_t captures{0};
    uint8_t stf_min{0};
    uint8_t stf_mean{0};
    uint8_t stf_max{0};
    uint8_t ltf_min{0};
    uint8_t ltf_mean{0};
    uint8_t ltf_max{0};
    uint16_t cfo_captures{0};
    int32_t cfo_min{0};
    int32_t cfo_mean{0};
    int32_t cfo_max{0};
    uint32_t clipped_components{0};
};
#pragma pack(pop)
static_assert(sizeof(ProfilerStatsWire) <= 32, "Fix8v stats page must fit diagnostic SSID bytes");
}
