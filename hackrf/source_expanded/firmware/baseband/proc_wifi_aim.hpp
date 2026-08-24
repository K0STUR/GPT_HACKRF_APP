#pragma once

#include "baseband_processor.hpp"
#include "baseband_thread.hpp"
#include "rssi_thread.hpp"
#include "message.hpp"
#include "wifi_aim/wifi_aim_phy.hpp"
#include "wifi_aim_wire.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

class WifiAimProcessor : public BasebandProcessor {
   public:
    void execute(const buffer_c8_t& buffer) override;
    void on_message(const Message* const message) override;

   private:
    static constexpr std::size_t baseband_fs = 20'000'000;
    static constexpr std::size_t kCaptureSamples = 20'000;   // 1.00 ms @ 20 MS/s
    static constexpr std::size_t kPretriggerSamples = 2'048; // one DMA block of history
    static constexpr uint16_t kDiagCaptureStride = 16;       // throttle failed-capture telemetry

    enum class State : uint8_t { Warmup, Waiting, Capturing, Cooldown };

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

    // Fix8a raw-IQ preamble probe. These counters answer whether captures
    // resemble 802.11 OFDM/DSSS before changing the actual Wi-Fi decoder.
    uint8_t probe_o16_hits_{0};
    uint8_t probe_o64_hits_{0};
    uint8_t probe_barker_hits_{0};
    uint8_t probe_o16_peak_{0};
    uint8_t probe_o64_peak_{0};
    uint8_t probe_barker_peak_{0};

    wifiaim::M4WifiDecoder decoder_{};

    // FSKRxPacketMessage carries a pointer to FskPacketData. Keep AP reports
    // and telemetry in separate backing stores so a retune ACK cannot overwrite
    // a freshly queued AP payload before M0 consumes it.
    FskPacketData ap_packet_{};
    FskPacketData diag_packet_{};

    uint32_t block_power(const buffer_c8_t& buffer) const;
    void remember_pretrigger(const buffer_c8_t& buffer);
    void copy_into_capture(const buffer_c8_t& buffer);
    void finish_capture();
    void reset_detector();
    void reset_probe_diag();
    void fill_probe_diag(wifiaim::WireApReport& wire) const;
    void send_diag_state();
    void send_wire_report(const wifiaim::WireApReport& wire, FskPacketData& storage);

    // These threads auto-start in their constructors. Keep them LAST so every
    // state/buffer used by execute() is initialized before the DMA thread runs.
    BasebandThread baseband_thread{baseband_fs, this, baseband::Direction::Receive};
    RSSIThread rssi_thread{};
};
