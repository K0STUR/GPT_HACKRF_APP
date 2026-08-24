#pragma once

#include "wifi_aim/wifi_aim_phy.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>

namespace wifiaim {

struct CaptureProbeResult {
    uint8_t ofdm16_score{0};
    uint8_t ofdm64_score{0};
    uint8_t barker_score{0};
    uint8_t flags{0};

    enum : uint8_t {
        OFDM16 = 1u << 0,
        OFDM64 = 1u << 1,
        BARKER = 1u << 2,
    };
};

inline uint8_t clamp_score(float q) {
    if (!(q > 0.0f)) return 0;
    const float x = std::min(1.0f, q) * 100.0f;
    return static_cast<uint8_t>(x + 0.5f);
}

// Maximum normalized complex correlation between two windows separated by
// `lag`. This does not decode OFDM; it only asks whether the raw capture has
// the strong repetition expected from legacy 802.11 STF/LTF structure.
inline uint8_t repeated_window_score(const IQ8* s, std::size_t count,
                                     std::size_t lag, std::size_t window) {
    if (!s || count < lag + window + 1) return 0;
    const std::size_t scan_end = std::min<std::size_t>(count - lag - window, 4096u);
    float best = 0.0f;
    for (std::size_t d = 0; d <= scan_end; d += 8u) {
        float cr = 0.0f, ci = 0.0f, ea = 0.0f, eb = 0.0f;
        for (std::size_t n = 0; n < window; ++n) {
            const float ar = static_cast<float>(s[d + n].i);
            const float ai = static_cast<float>(s[d + n].q);
            const float br = static_cast<float>(s[d + lag + n].i);
            const float bi = static_cast<float>(s[d + lag + n].q);
            cr += ar * br + ai * bi;
            ci += ar * bi - ai * br;
            ea += ar * ar + ai * ai;
            eb += br * br + bi * bi;
        }
        if (ea < 1.0f || eb < 1.0f) continue;
        const float q = (cr * cr + ci * ci) / (ea * eb);
        if (q > best) best = q;
    }
    return clamp_score(best);
}

// Raw Barker-11 despread quality. We test all 20 sample phases of the
// 20 Msps -> 11 Mcps mapping and a limited number of complete 11-chip symbols.
// Perfect Barker spreading approaches 100; uncorrelated noise is much lower.
inline uint8_t barker11_score(const IQ8* s, std::size_t count) {
    static constexpr int8_t barker[11] = {+1,-1,+1,+1,-1,+1,+1,+1,-1,-1,-1};
    if (!s || count < 256) return 0;
    float best = 0.0f;
    for (unsigned phase = 0; phase < 20; ++phase) {
        for (unsigned sym = 0; sym < 96; ++sym) {
            const std::size_t chip0 = static_cast<std::size_t>(sym) * 11u;
            float cr = 0.0f, ci = 0.0f, e = 0.0f;
            bool valid = true;
            for (unsigned k = 0; k < 11; ++k) {
                const std::size_t chip = chip0 + k;
                const std::size_t idx = (chip * 20u + phase + 5u) / 11u;
                if (idx >= count) { valid = false; break; }
                const float xr = static_cast<float>(s[idx].i);
                const float xi = static_cast<float>(s[idx].q);
                cr += xr * static_cast<float>(barker[k]);
                ci += xi * static_cast<float>(barker[k]);
                e += xr * xr + xi * xi;
            }
            if (!valid) break;
            if (e < 1.0f) continue;
            const float q = (cr * cr + ci * ci) / (11.0f * e);
            if (q > best) best = q;
        }
    }
    return clamp_score(best);
}

inline CaptureProbeResult probe_capture(const IQ8* s, std::size_t count) {
    CaptureProbeResult r{};
    // STF repeats every 16 samples; use several periods for selectivity.
    r.ofdm16_score = repeated_window_score(s, count, 16u, 64u);
    // Two legacy L-LTF symbols repeat after 64 samples.
    r.ofdm64_score = repeated_window_score(s, count, 64u, 64u);
    r.barker_score = barker11_score(s, count);

    // Deliberately conservative flags. Raw scores remain visible even if a
    // capture falls just below a threshold, so thresholds can be tuned from
    // real hardware evidence instead of guessed repeatedly.
    if (r.ofdm16_score >= 55u) r.flags |= CaptureProbeResult::OFDM16;
    if (r.ofdm64_score >= 60u) r.flags |= CaptureProbeResult::OFDM64;
    if (r.barker_score >= 70u) r.flags |= CaptureProbeResult::BARKER;
    return r;
}

}  // namespace wifiaim
