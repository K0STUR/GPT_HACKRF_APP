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
    static constexpr std::size_t kCaptureSamples = 20'000; // 1.00 ms @ 20 MS/s; covers long-preamble DSSS beacon prefix

    enum class State : uint8_t { Warmup, Waiting, Capturing, Cooldown };

    BasebandThread baseband_thread{baseband_fs, this, baseband::Direction::Receive};
    RSSIThread rssi_thread{};

    bool enabled_{false};
    State state_{State::Warmup};
    uint8_t warmup_buffers_{8};
    uint8_t cooldown_buffers_{0};
    uint32_t noise_power_{64};
    uint8_t tuned_channel_{1};

    std::array<wifiaim::IQ8, kCaptureSamples> capture_{};
    std::size_t capture_count_{0};
    wifiaim::M4WifiDecoder decoder_{};
    FskPacketData packet_{};

    uint32_t block_power(const buffer_c8_t& buffer) const;
    void copy_into_capture(const buffer_c8_t& buffer);
    void finish_capture();
    void reset_detector();
};
