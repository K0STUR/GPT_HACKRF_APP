#include "proc_wifi_aim.hpp"

#include "event_m4.hpp"
#include "portapack_shared_memory.hpp"

#include <algorithm>
#include <cstring>

uint32_t WifiAimProcessor::block_power(const buffer_c8_t& buffer) const {
    if (!buffer.count) return 0;
    // A DMA/baseband block is far below the ~133k samples required to
    // overflow this accumulator at full-scale int8 IQ. Keeping it 32-bit
    // avoids dragging the 64-bit division helper into the small M4 image.
    uint32_t sum = 0;
    for (std::size_t n = 0; n < buffer.count; ++n) {
        const int32_t i = buffer.p[n].real();
        const int32_t q = buffer.p[n].imag();
        sum += static_cast<uint32_t>(i * i + q * q);
    }
    return sum / static_cast<uint32_t>(buffer.count);
}

void WifiAimProcessor::remember_pretrigger(const buffer_c8_t& buffer) {
    // Reuse capture_[0..] while Waiting. Keep only the newest DMA-block tail;
    // when a burst fires we continue writing directly after these samples.
    const std::size_t n = std::min<std::size_t>(buffer.count, kPretriggerSamples);
    const std::size_t start = buffer.count - n;
    for (std::size_t i = 0; i < n; ++i) {
        capture_[i].i = buffer.p[start + i].real();
        capture_[i].q = buffer.p[start + i].imag();
    }
    pretrigger_count_ = n;
}

void WifiAimProcessor::copy_into_capture(const buffer_c8_t& buffer) {
    const std::size_t room = kCaptureSamples - capture_count_;
    const std::size_t ncopy = std::min<std::size_t>(room, buffer.count);
    for (std::size_t n = 0; n < ncopy; ++n) {
        capture_[capture_count_ + n].i = buffer.p[n].real();
        capture_[capture_count_ + n].q = buffer.p[n].imag();
    }
    capture_count_ += ncopy;
}

void WifiAimProcessor::send_diag_stats() {
    // ABI-safe diagnostic transport: HunterTrigger already exists in n_260808.
    // 0xCccccddd: C = stats marker, c = capture attempts, d = successful decodes.
    HunterTriggerMessage msg{};
    msg.energy = 0xC0000000u |
                 ((static_cast<uint32_t>(capture_attempts_) & 0x3FFFu) << 14) |
                 (static_cast<uint32_t>(decode_successes_) & 0x3FFFu);
    shared_memory.application_queue.push(msg);
}

void WifiAimProcessor::send_diag_ack() {
    // 0xF00000cc confirms M4 received HunterConfig and reports tuned channel.
    HunterTriggerMessage msg{};
    msg.energy = 0xF0000000u | static_cast<uint32_t>(tuned_channel_);
    shared_memory.application_queue.push(msg);
}

void WifiAimProcessor::reset_detector() {
    capture_count_ = 0;
    pretrigger_count_ = 0;
    state_ = State::Waiting;
}

void WifiAimProcessor::finish_capture() {
    wifiaim::M4ApReport ap{};
    if (decoder_.decode(capture_.data(), capture_count_, ap)) {
        ++decode_successes_;
        if (ap.channel == 0) ap.channel = tuned_channel_;
        wifiaim::WireApReport wire{};
        wire.channel = ap.channel;
        wire.packet_db_x10 = ap.packet_db_x10;
        std::memcpy(wire.bssid, ap.bssid, 6);
        wire.ssid_len = static_cast<uint8_t>(std::min<unsigned>(static_cast<unsigned>(ap.ssid_len), 32U));
        if (wire.ssid_len) std::memcpy(wire.ssid, ap.ssid, wire.ssid_len);
        wire.flags = ap.hidden ? 0x01 : 0x00;
        wire.phy_rate_mbps = ap.phy_rate_mbps;

        std::memset(packet_.data, 0, sizeof(packet_.data));
        std::memcpy(packet_.data, &wire, sizeof(wire));
        packet_.dataLen = sizeof(wire);
        packet_.max_dB = ap.packet_db_x10 / 10;
        packet_.power = static_cast<float>(ap.packet_db_x10) / 10.0f;
        FSKRxPacketMessage msg{&packet_};
        shared_memory.application_queue.push(msg);
    }

    send_diag_stats();
    capture_count_ = 0;
    pretrigger_count_ = 0;
    cooldown_buffers_ = 2;
    state_ = State::Cooldown;
}

void WifiAimProcessor::execute(const buffer_c8_t& buffer) {
    if (!enabled_) return;

    const uint32_t p = block_power(buffer);

    if (state_ == State::Warmup) {
        // Learn a local background estimate immediately after a retune. Also
        // retain the latest block so a packet starting on the warmup boundary
        // still has useful pre-trigger history.
        noise_power_ = (noise_power_ * 3u + p) / 4u;
        remember_pretrigger(buffer);
        if (warmup_buffers_ && --warmup_buffers_ == 0) state_ = State::Waiting;
        return;
    }

    if (state_ == State::Cooldown) {
        remember_pretrigger(buffer);
        if (cooldown_buffers_ && --cooldown_buffers_ == 0) state_ = State::Waiting;
        return;
    }

    if (state_ == State::Waiting) {
        // Follow the floor slowly. Fix7 deliberately uses a less conservative
        // trigger than Fix6 and prepends the previous DMA block when a burst is
        // detected, so the 802.11 preamble/LTF is not lost at the block edge.
        if (p < noise_power_ * 2u) noise_power_ = (noise_power_ * 31u + p) / 32u;
        const uint32_t threshold = noise_power_ + (noise_power_ >> 2) + 32u;  // ~1.25x + margin
        if (p >= threshold) {
            ++capture_attempts_;
            capture_count_ = pretrigger_count_; // previous block already lives at capture_[0..]
            copy_into_capture(buffer);
            pretrigger_count_ = 0;
            state_ = State::Capturing;
        } else {
            remember_pretrigger(buffer);
        }
        return;
    }

    if (state_ == State::Capturing) {
        copy_into_capture(buffer);
        if (capture_count_ >= kCaptureSamples) finish_capture();
    }
}

void WifiAimProcessor::on_message(const Message* const message) {
    switch (message->id) {
        case Message::ID::HunterConfig: {
            // Reuse an existing ABI-safe message instead of changing message.hpp.
            const auto& m = *reinterpret_cast<const HunterConfigMessage*>(message);
            if (m.energy_threshold >= 1 && m.energy_threshold <= 13)
                tuned_channel_ = static_cast<uint8_t>(m.energy_threshold);
            enabled_ = m.start;
            capture_count_ = 0;
            pretrigger_count_ = 0;
            warmup_buffers_ = 8;
            cooldown_buffers_ = 0;
            state_ = enabled_ ? State::Warmup : State::Waiting;
            send_diag_ack();
            send_diag_stats();
            break;
        }
        default:
            break;
    }
}

#ifndef WIFI_AIM_UNIT_TEST
int main() {
    EventDispatcher event_dispatcher{std::make_unique<WifiAimProcessor>()};
    event_dispatcher.run();
    return 0;
}
#endif
