from pathlib import Path

phy = Path('hackrf/source_expanded/firmware/common/wifi_aim/wifi_aim_phy.cpp')
ui = Path('hackrf/source_expanded/firmware/application/external/wifi_aim/ui_wifi_aim.cpp')
hpp = Path('hackrf/source_expanded/firmware/common/wifi_aim/wifi_aim_phy.hpp')

text = phy.read_text()
start = text.index('bool M4OfdmWifiDecoder::find_ltf(')
end = text.index('\nvoid M4OfdmWifiDecoder::load_fft', start)

replacement = r'''bool M4OfdmWifiDecoder::find_ltf(const IQ8* s, std::size_t count, std::size_t& ltf1,
                                      float& cfo_step_r, float& cfo_step_i, float& score) {
    if (!s || count < 500) return false;

    // Fix8c: synchronize from a channel-invariant property of the legacy
    // preamble instead of requiring a strong match to an *ideal* undistorted
    // L-LTF. The two long-training symbols repeat after 64 samples, while the
    // preceding STF is strongly 16-sample periodic. Therefore
    //
    //     metric = Q64 * (1 - Q16)
    //
    // is high over the GI2/L-LTF region and low over STF. This remains useful
    // after multipath because both repeated LTF copies traverse the same RF
    // channel. We select the strongest short contiguous run and back the FFT
    // timing up by eight samples so SIGNAL/DATA FFT windows remain safely
    // inside their 16-sample cyclic prefixes.
    constexpr float kSyncThreshold = 0.15f;
    constexpr std::size_t kMinRun = 4;
    constexpr std::size_t kTimingBackoff = 8;

    if (count <= 128u) return false;
    const std::size_t limit = std::min<std::size_t>(count - 128u, static_cast<std::size_t>(2200u));

    bool in_run = false;
    std::size_t run_start = 0;
    std::size_t run_end = 0;
    float run_peak = 0.0f;

    std::size_t best_end = 0;
    float best_peak = 0.0f;
    bool have_best = false;

    auto finish_run = [&]() {
        if (in_run && (run_end - run_start + 1u) >= kMinRun && run_peak > best_peak) {
            best_peak = run_peak;
            best_end = run_end;
            have_best = true;
        }
        in_run = false;
        run_peak = 0.0f;
    };

    for (std::size_t d = 0; d < limit; ++d) {
        float c16r = 0.0f, c16i = 0.0f;
        float c64r = 0.0f, c64i = 0.0f;
        float e0 = 0.0f, e16 = 0.0f, e64 = 0.0f;

        for (std::size_t n = 0; n < 64u; ++n) {
            const float ar = static_cast<float>(s[d + n].i);
            const float ai = static_cast<float>(s[d + n].q);
            const float b16r = static_cast<float>(s[d + 16u + n].i);
            const float b16i = static_cast<float>(s[d + 16u + n].q);
            const float b64r = static_cast<float>(s[d + 64u + n].i);
            const float b64i = static_cast<float>(s[d + 64u + n].q);

            c16r += ar * b16r + ai * b16i;
            c16i += ar * b16i - ai * b16r;
            c64r += ar * b64r + ai * b64i;
            c64i += ar * b64i - ai * b64r;
            e0 += ar * ar + ai * ai;
            e16 += b16r * b16r + b16i * b16i;
            e64 += b64r * b64r + b64i * b64i;
        }

        float q16 = 0.0f;
        float q64 = 0.0f;
        if (e0 > 1.0f && e16 > 1.0f)
            q16 = (c16r * c16r + c16i * c16i) / (e0 * e16);
        if (e0 > 1.0f && e64 > 1.0f)
            q64 = (c64r * c64r + c64i * c64i) / (e0 * e64);

        q16 = std::max(0.0f, std::min(1.0f, q16));
        q64 = std::max(0.0f, std::min(1.0f, q64));
        const float metric = q64 * (1.0f - q16);

        if (metric >= kSyncThreshold) {
            if (!in_run) {
                in_run = true;
                run_start = d;
                run_peak = metric;
            }
            run_end = d;
            if (metric > run_peak) run_peak = metric;
        } else {
            finish_run();
        }
    }
    finish_run();

    if (!have_best) {
        score = best_peak;
        return false;
    }

    std::size_t best_d = best_end > kTimingBackoff ? best_end - kTimingBackoff : 0u;
    if (best_d + 128u > count) return false;

    // CFO from the same two repeated 64-sample windows selected above.
    float pr = 0.0f, pi = 0.0f;
    for (std::size_t n = 0; n < 64u; ++n) {
        const float ar = static_cast<float>(s[best_d + n].i);
        const float ai = static_cast<float>(s[best_d + n].q);
        const float br = static_cast<float>(s[best_d + 64u + n].i);
        const float bi = static_cast<float>(s[best_d + 64u + n].q);
        pr += ar * br + ai * bi;
        pi += ar * bi - ai * br;
    }

    const float mag2 = pr * pr + pi * pi;
    if (mag2 < 1.0e-12f) return false;
    const float inv_mag = fast_rsqrt(mag2);
    float root_r = pr * inv_mag, root_i = pi * inv_mag;
    for (unsigned k = 0; k < 6; ++k) {
        const float a = std::max(0.0f, (1.0f + root_r) * 0.5f);
        const float b = std::max(0.0f, (1.0f - root_r) * 0.5f);
        const float next_r = fast_sqrt(a);
        float next_i = fast_sqrt(b);
        if (root_i < 0.0f) next_i = -next_i;
        root_r = next_r;
        root_i = next_i;
    }

    cfo_step_r = root_r;
    cfo_step_i = -root_i;
    ltf1 = best_d;
    score = best_peak;
    return true;
}
'''

phy.write_text(text[:start] + replacement + text[end:])

ut = ui.read_text()
ut = ut.replace('text_channel.set("LQ " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[8])) +',
                'text_channel.set("SQ " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[8])) +')
ui.write_text(ut)

ht = hpp.read_text()
ht = ht.replace('uint8_t ltf_score{0};      // best ideal-LTF correlation, 0..100',
                'uint8_t ltf_score{0};      // Fix8c repetition sync quality, 0..100')
hpp.write_text(ht)

print('Fix8c LTF synchronizer applied')
