#pragma once

#include "baseband_processor.hpp"
#include "baseband_thread.hpp"
#include "rssi_thread.hpp"
#include "message.hpp"
#include "wifi_aim/wifi_aim_phy.hpp"
#include "wifi_aim_wire.hpp"
#include "stream_input.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>

class WifiAimProcessor : public BasebandProcessor {
   public:
    void execute(const buffer_c8_t& buffer) override;
    void on_message(const Message* const message) override;

   private:
    static constexpr std::size_t baseband_fs = 20'000'000;
    static constexpr std::size_t kCaptureSamples = 20'000;   // 1.00 ms @ 20 MS/s
    static constexpr std::size_t kPretriggerSamples = 2'048; // one DMA block of history
    static constexpr uint16_t kDiagCaptureStride = 16;       // throttle failed-capture telemetry

    enum class State : uint8_t { Warmup, Waiting, Capturing, Cooldown, Frozen, Dumping };

    bool enabled_{false};
    State state_{State::Warmup};
    uint8_t warmup_buffers_{8};
    uint8_t cooldown_buffers_{0};
    uint32_t noise_power_{64};
    uint8_t tuned_channel_{1};

    // Reuse the start of capture_ as the rolling pre-trigger block while
    // waiting. This costs no extra M4 capture RAM compared with Fix6.
    std::array<wifiaim::IQ8, kCaptureSamples> capture_{};
    std::size_t pretrigger_count_{0};
    std::size_t capture_count_{0};
    uint16_t capture_attempts_{0};
    uint16_t decode_successes_{0};

    // Fix8t-DIAG freezes one PHY-interesting capture (DATA Viterbi reached)
    // and drains it through stock CaptureConfig/StreamInput only after the
    // 20,000-sample RAM capture is complete. No live 20 MS/s SD stream exists.
    bool diag_capture_saved_{false};
    bool diag_capture_pending_{false};
    std::size_t diag_dump_offset_{0};
    std::unique_ptr<StreamInput> diag_stream_{};

    // Fix8a raw-IQ preamble probe. These counters answer whether captures
    // resemble 802.11 OFDM/DSSS before changing the actual Wi-Fi decoder.
    uint8_t probe_o16_hits_{0};
    uint8_t probe_o64_hits_{0};
    uint8_t probe_barker_hits_{0};
    uint8_t probe_o16_peak_{0};
    uint8_t probe_o64_peak_{0};
    uint8_t probe_barker_peak_{0};

    // Fix8b OFDM stage telemetry, reset at the start of every SCAN.
    std::array<uint8_t,8> ofdm_stage_hits_{};
    uint8_t ofdm_ltf_peak_{0};
    uint8_t ofdm_last_rate_{0xFF};
    uint16_t ofdm_last_length_{0};

    // Fix8e post-DATA OFDM and DSSS-path telemetry.
    std::array<uint8_t,5> ofdm_post_hits_{};
    uint8_t ofdm_last_type_{0xFF};
    uint8_t ofdm_last_subtype_{0xFF};
    bool ofdm_service_seen_{false};
    uint8_t dsss_attempts_{0};
    uint8_t dsss_successes_{0};

    wifiaim::M4WifiDecoder decoder_{};

    // FSKRxPacketMessage carries a pointer to FskPacketData. Keep AP reports
    // and telemetry in separate backing stores so a retune ACK cannot overwrite
    // a freshly queued AP payload before M0 consumes it.
    FskPacketData ap_packet_{};
    FskPacketData diag_packet_{};
    FskPacketData profile_rejected_packet_{};
    FskPacketData profile_accepted_packet_{};

    struct EnergyPowers {
        uint32_t full{0};
        uint32_t max256{0};
        uint32_t max128{0};
    };
    std::array<uint16_t, wifiaim::PROFILE_COUNTER_COUNT> profile_counts_{};
    wifiaim::ProfilerStatsWire rejected_stats_{};
    wifiaim::ProfilerStatsWire accepted_stats_{};

    EnergyPowers block_powers(const buffer_c8_t& buffer) const;
    void remember_pretrigger(const buffer_c8_t& buffer);
    void copy_into_capture(const buffer_c8_t& buffer);
    void finish_capture();
    void reset_detector();
    void reset_probe_diag();
    void reset_profiler();
    void update_profile_stats(wifiaim::ProfilerStatsWire& stats,
                              const wifiaim::M4OfdmTrace& trace, uint16_t clipped);
    void fill_profile_counters(wifiaim::WireApReport& wire) const;
    void fill_profile_stats(wifiaim::WireApReport& wire, uint8_t subtype,
                            const wifiaim::ProfilerStatsWire& stats) const;
    void send_profiler_snapshot();
    void fill_probe_diag(wifiaim::WireApReport& wire) const;
    void send_diag_state();
    void send_diag_capture_ready(const wifiaim::M4OfdmTrace& trace, uint16_t clipped);
    void send_wire_report(const wifiaim::WireApReport& wire, FskPacketData& storage);

    // These threads auto-start in their constructors. Keep them LAST so every
    // state/buffer used by execute() is initialized before the DMA thread runs.
    BasebandThread baseband_thread{baseband_fs, this, baseband::Direction::Receive};
    RSSIThread rssi_thread{};
};
