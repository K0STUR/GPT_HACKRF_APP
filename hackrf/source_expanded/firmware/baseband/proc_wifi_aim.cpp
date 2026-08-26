#include "proc_wifi_aim.hpp"

#include "event_m4.hpp"
#include "portapack_shared_memory.hpp"
#include "wifi_aim/wifi_aim_capture_probe.hpp"

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

void WifiAimProcessor::send_wire_report(const wifiaim::WireApReport& wire, FskPacketData& storage) {
    std::memset(storage.data, 0, sizeof(storage.data));
    std::memcpy(storage.data, &wire, sizeof(wire));
    storage.dataLen = sizeof(wire);
    storage.max_dB = wire.packet_db_x10 / 10;
    storage.power = static_cast<float>(wire.packet_db_x10) / 10.0f;
    FSKRxPacketMessage msg{&storage};
    shared_memory.application_queue.push(msg);
}

void WifiAimProcessor::reset_probe_diag() {
    probe_o16_hits_ = 0;
    probe_o64_hits_ = 0;
    probe_barker_hits_ = 0;
    probe_o16_peak_ = 0;
    probe_o64_peak_ = 0;
    probe_barker_peak_ = 0;
    ofdm_stage_hits_.fill(0);
    ofdm_ltf_peak_ = 0;
    ofdm_last_rate_ = 0xFFu;
    ofdm_last_length_ = 0;
    ofdm_post_hits_.fill(0);
    ofdm_last_type_ = 0xFFu;
    ofdm_last_subtype_ = 0xFFu;
    ofdm_service_seen_ = false;
    dsss_attempts_ = 0;
    dsss_successes_ = 0;
}

void WifiAimProcessor::fill_probe_diag(wifiaim::WireApReport& wire) const {
    // Diagnostic-only packets do not use BSSID/SSID fields. Reuse those six
    // bytes as a compact Fix8a telemetry payload without changing WireApReport
    // layout or any stock-core message ABI.
    wire.ssid_len = 0xF9u;  // Fix8b: Fix8a probe + OFDM internal stages.
    wire.bssid[0] = probe_o16_hits_;
    wire.bssid[1] = probe_o64_hits_;
    wire.bssid[2] = probe_barker_hits_;
    wire.bssid[3] = probe_o16_peak_;
    wire.bssid[4] = probe_o64_peak_;
    wire.bssid[5] = probe_barker_peak_;
    for (std::size_t i = 0; i < ofdm_stage_hits_.size(); ++i)
        wire.ssid[i] = static_cast<char>(ofdm_stage_hits_[i]);
    wire.ssid[8] = static_cast<char>(ofdm_ltf_peak_);
    wire.ssid[9] = static_cast<char>(ofdm_last_rate_);
    wire.ssid[10] = static_cast<char>(ofdm_last_length_ & 0xFFu);
    wire.ssid[11] = static_cast<char>((ofdm_last_length_ >> 8) & 0xFFu);
    for (std::size_t i = 0; i < ofdm_post_hits_.size(); ++i)
        wire.ssid[12 + i] = static_cast<char>(ofdm_post_hits_[i]);
    wire.ssid[17] = static_cast<char>(ofdm_last_type_);
    wire.ssid[18] = static_cast<char>(ofdm_last_subtype_);
    wire.ssid[19] = static_cast<char>(dsss_attempts_);
    wire.ssid[20] = static_cast<char>(dsss_successes_);
}

void WifiAimProcessor::send_diag_state() {
    // Use the existing FSKPacket IPC path already used by Fix6. bit7 means
    // telemetry only and must not become an AP entry. Fix7c keeps telemetry
    // in diag_packet_, separate from successful AP payloads.
    wifiaim::WireApReport wire{};
    wire.channel = tuned_channel_;
    wire.flags = 0x80u;
    wire.capture_total = static_cast<uint16_t>(capture_attempts_ & 0x3FFFu);
    wire.decode_total = static_cast<uint16_t>(decode_successes_ & 0x3FFFu);
    fill_probe_diag(wire);
    send_wire_report(wire, diag_packet_);
}

void WifiAimProcessor::send_diag_capture_ready(const wifiaim::M4OfdmTrace& trace) {
    // Fix8t-DIAG: one self-contained snapshot describing the frozen buffer.
    // The stock FSKPacket transport remains unchanged; 0xFA identifies this
    // diagnostic subtype and no pointer to M4 RAM crosses the core boundary.
    wifiaim::WireApReport wire{};
    wire.channel = tuned_channel_;
    wire.flags = 0x80u;
    wire.ssid_len = 0xFAu;
    wire.capture_total = static_cast<uint16_t>(capture_attempts_ & 0x3FFFu);
    wire.decode_total = static_cast<uint16_t>(decode_successes_ & 0x3FFFu);
    wire.bssid[0] = ofdm_stage_hits_[0];  // L
    wire.bssid[1] = ofdm_stage_hits_[1];  // H
    wire.bssid[2] = ofdm_stage_hits_[2];  // V
    wire.bssid[3] = ofdm_stage_hits_[3];  // P
    wire.bssid[4] = ofdm_stage_hits_[4];  // R
    wire.bssid[5] = ofdm_stage_hits_[5];  // N
    wire.ssid[0] = static_cast<char>(ofdm_stage_hits_[6]);  // D
    wire.ssid[1] = static_cast<char>(ofdm_stage_hits_[7]);  // M
    wire.ssid[2] = static_cast<char>(trace.ltf_score);      // SQ for this capture
    std::memcpy(&wire.ssid[3], &trace.ltf_position, sizeof(trace.ltf_position));
    std::memcpy(&wire.ssid[5], &trace.cfo_hz, sizeof(trace.cfo_hz));
    wire.ssid[9] = static_cast<char>(trace.rate_raw);
    std::memcpy(&wire.ssid[10], &trace.length, sizeof(trace.length));
    wire.ssid[12] = static_cast<char>(trace.stage);
    wire.ssid[13] = static_cast<char>(trace.post_stage);
    wire.ssid[14] = static_cast<char>(trace.service_errors);
    send_wire_report(wire, diag_packet_);
}

void WifiAimProcessor::reset_detector() {
    capture_count_ = 0;
    pretrigger_count_ = 0;
    state_ = State::Waiting;
}

void WifiAimProcessor::finish_capture() {
    // Fix8a asks a question independent from the actual decoder: does the raw
    // capture contain repetition/Barker structure characteristic of Wi-Fi?
    const auto probe = wifiaim::probe_capture(capture_.data(), capture_count_);
    if ((probe.flags & wifiaim::CaptureProbeResult::OFDM16) && probe_o16_hits_ != 0xFFu) ++probe_o16_hits_;
    if ((probe.flags & wifiaim::CaptureProbeResult::OFDM64) && probe_o64_hits_ != 0xFFu) ++probe_o64_hits_;
    if ((probe.flags & wifiaim::CaptureProbeResult::BARKER) && probe_barker_hits_ != 0xFFu) ++probe_barker_hits_;
    probe_o16_peak_ = std::max(probe_o16_peak_, probe.ofdm16_score);
    probe_o64_peak_ = std::max(probe_o64_peak_, probe.ofdm64_score);
    probe_barker_peak_ = std::max(probe_barker_peak_, probe.barker_score);

    wifiaim::M4ApReport ap{};
    wifiaim::M4OfdmTrace ofdm_trace{};
    // Fix8g: reuse the cheap raw Barker probe as an admission signal for the
    // expensive DSSS fallback. The decoder still performs final validation.
    const bool decoded = decoder_.decode(capture_.data(), capture_count_, ap, &ofdm_trace, probe.barker_score);
    for (uint8_t i = 0; i < ofdm_trace.stage && i < ofdm_stage_hits_.size(); ++i)
        if (ofdm_stage_hits_[i] != 0xFFu) ++ofdm_stage_hits_[i];
    ofdm_ltf_peak_ = std::max(ofdm_ltf_peak_, ofdm_trace.ltf_score);
    // Fix8l: A/N telemetry must describe the candidate that actually reached
    // DATA Viterbi. Later parity-only/noisy captures used to overwrite these
    // fields and made hardware results impossible to classify by PHY rate.
    if (ofdm_trace.stage >= 7u) {
        if (ofdm_trace.rate_raw != 0xFFu) ofdm_last_rate_ = ofdm_trace.rate_raw;
        if (ofdm_trace.length) ofdm_last_length_ = ofdm_trace.length;
    }
    for (uint8_t i = 0; i < ofdm_trace.post_stage && i < ofdm_post_hits_.size(); ++i)
        if (ofdm_post_hits_[i] != 0xFFu) ++ofdm_post_hits_[i];
    // Fix8m: after DATA Viterbi, FC is min SERVICE errors / raw RATE.
    // Before first DATA candidate, retain older DSSS FC diagnostics.
    if (ofdm_trace.stage >= 7u && ofdm_trace.service_errors != 0xFFu) {
        if (!ofdm_service_seen_ || ofdm_trace.service_errors < ofdm_last_type_) {
            ofdm_last_type_ = ofdm_trace.service_errors;
            ofdm_last_subtype_ = ofdm_trace.rate_raw;
        }
        ofdm_service_seen_ = true;
    } else if (!ofdm_service_seen_) {
        if (ofdm_trace.frame_type != 0xFFu) ofdm_last_type_ = ofdm_trace.frame_type;
        if (ofdm_trace.frame_subtype != 0xFFu) ofdm_last_subtype_ = ofdm_trace.frame_subtype;
    }
    if (ofdm_trace.dsss_attempted && dsss_attempts_ != 0xFFu) ++dsss_attempts_;
    if (ofdm_trace.dsss_success && dsss_successes_ != 0xFFu) ++dsss_successes_;
    if (decoded) ++decode_successes_;

    wifiaim::WireApReport wire{};
    wire.channel = tuned_channel_;
    wire.capture_total = static_cast<uint16_t>(capture_attempts_ & 0x3FFFu);
    wire.decode_total = static_cast<uint16_t>(decode_successes_ & 0x3FFFu);

    const bool freeze_for_diag = !diag_capture_saved_ && !diag_capture_pending_ && ofdm_trace.stage >= 7u;

    if (decoded) {
        // A real AP report is always emitted immediately and uses its own
        // backing packet buffer so channel-retune telemetry cannot overwrite it.
        if (ap.channel == 0) ap.channel = tuned_channel_;
        wire.channel = ap.channel;
        wire.packet_db_x10 = ap.packet_db_x10;
        std::memcpy(wire.bssid, ap.bssid, 6);
        wire.ssid_len = static_cast<uint8_t>(std::min<unsigned>(static_cast<unsigned>(ap.ssid_len), 32U));
        if (wire.ssid_len) std::memcpy(wire.ssid, ap.ssid, wire.ssid_len);
        wire.flags = ap.hidden ? 0x01u : 0x00u;
        wire.phy_rate_mbps = ap.phy_rate_mbps;
        send_wire_report(wire, ap_packet_);
    } else if (!freeze_for_diag && (capture_attempts_ % kDiagCaptureStride) == 0u) {
        // A busy/noisy RF channel can produce hundreds of failed captures per
        // second. We only need periodic progress here; exact totals are also
        // sent on every decoder/channel state change.
        wire.flags = 0x80u;
        fill_probe_diag(wire);
        send_wire_report(wire, diag_packet_);
    }

    if (freeze_for_diag) {
        // Keep capture_ and capture_count_ untouched until M0 opens the C8 file
        // and replies with stock CaptureConfig. Incoming RF is ignored while
        // Frozen/Dumping, so the saved bytes are exactly the decoded capture.
        diag_capture_pending_ = true;
        diag_dump_offset_ = 0;
        state_ = State::Frozen;
        send_diag_capture_ready(ofdm_trace);
        return;
    }

    capture_count_ = 0;
    pretrigger_count_ = 0;
    cooldown_buffers_ = 2;
    state_ = State::Cooldown;
}

void WifiAimProcessor::execute(const buffer_c8_t& buffer) {
    if (state_ == State::Dumping) {
        if (diag_stream_) {
            const std::size_t total_bytes = kCaptureSamples * sizeof(wifiaim::IQ8);
            if (diag_dump_offset_ < total_bytes) {
                const auto* bytes = reinterpret_cast<const uint8_t*>(capture_.data());
                diag_dump_offset_ += diag_stream_->write(
                    bytes + diag_dump_offset_, total_bytes - diag_dump_offset_);
            }
        }
        return;
    }
    if (state_ == State::Frozen) return;
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
        // Follow the floor slowly. Keep the previous DMA block so the decoder
        // sees the Wi-Fi preamble/LTF even if the trigger occurs one block late.
        if (p < noise_power_ * 2u) noise_power_ = (noise_power_ * 31u + p) / 32u;
        const uint32_t threshold = noise_power_ + (noise_power_ >> 2) + 32u;  // ~1.25x + margin
        if (p >= threshold) {
            ++capture_attempts_;
            capture_count_ = pretrigger_count_;
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
            // Reuse the stock HunterConfig ABI for M0 -> M4 control only.
            const auto& m = *reinterpret_cast<const HunterConfigMessage*>(message);
            if (m.energy_threshold >= 1 && m.energy_threshold <= 13)
                tuned_channel_ = static_cast<uint8_t>(m.energy_threshold);

            // A scan always begins by enabling channel 1. Reset only the Fix8a
            // per-scan probe values here; C/D keep their existing cumulative
            // semantics and are delta'd by M0 as before.
            if (m.start && tuned_channel_ == 1u) {
                reset_probe_diag();
                diag_capture_saved_ = false;
            }

            // M0 pauses channel hopping while a one-shot dump is active. Keep
            // the frozen bytes intact even if a late UI control message arrives.
            if (diag_capture_pending_) {
                enabled_ = m.start;
                break;
            }

            enabled_ = m.start;
            capture_count_ = 0;
            pretrigger_count_ = 0;
            warmup_buffers_ = 8;
            cooldown_buffers_ = 0;
            state_ = enabled_ ? State::Warmup : State::Waiting;
            // Exact counters + channel acknowledgement at every state/channel
            // transition; this also gives exact final counters when SCAN ends.
            send_diag_state();
            break;
        }
        case Message::ID::CaptureConfig: {
            if (!diag_capture_pending_) break;
            const auto& m = *reinterpret_cast<const CaptureConfigMessage*>(message);
            if (m.config && state_ == State::Frozen) {
                // StreamInput owns the stock shared FIFO buffers. M4 only drains
                // the already-frozen 40 kB capture; it never forwards live RF.
                diag_stream_ = std::make_unique<StreamInput>(m.config);
                diag_dump_offset_ = 0;
                state_ = State::Dumping;
            } else if (!m.config) {
                const bool complete = diag_dump_offset_ == kCaptureSamples * sizeof(wifiaim::IQ8);
                diag_stream_.reset();
                diag_capture_pending_ = false;
                diag_capture_saved_ = complete;
                capture_count_ = 0;
                pretrigger_count_ = 0;
                cooldown_buffers_ = 2;
                state_ = enabled_ ? State::Cooldown : State::Waiting;
            }
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
