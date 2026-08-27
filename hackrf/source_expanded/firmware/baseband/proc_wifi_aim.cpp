#include "proc_wifi_aim.hpp"

#include "event_m4.hpp"
#include "portapack_shared_memory.hpp"
#include "wifi_aim/wifi_aim_capture_probe.hpp"

#include <algorithm>
#include <cstring>

WifiAimProcessor::EnergyPowers WifiAimProcessor::block_powers(const buffer_c8_t& buffer) const {
    EnergyPowers out{};
    if (!buffer.count) return out;
    // A DMA/baseband block is far below the ~133k samples required to
    // overflow this accumulator at full-scale int8 IQ. Keeping it 32-bit
    // avoids dragging the 64-bit division helper into the small M4 image.
    uint32_t sum = 0, sum128 = 0, sum256 = 0;
    for (std::size_t n = 0; n < buffer.count; ++n) {
        const int32_t i = buffer.p[n].real();
        const int32_t q = buffer.p[n].imag();
        const uint32_t sample_power = static_cast<uint32_t>(i * i + q * q);
        sum += sample_power;
        sum128 += sample_power;
        sum256 += sample_power;
        if ((n & 127u) == 127u) {
            out.max128 = std::max(out.max128, sum128 >> 7);
            sum128 = 0;
        }
        if ((n & 255u) == 255u) {
            out.max256 = std::max(out.max256, sum256 >> 8);
            sum256 = 0;
        }
    }
    const std::size_t tail128 = buffer.count & 127u;
    const std::size_t tail256 = buffer.count & 255u;
    if (tail128) out.max128 = std::max(out.max128, sum128 / static_cast<uint32_t>(tail128));
    if (tail256) out.max256 = std::max(out.max256, sum256 / static_cast<uint32_t>(tail256));
    out.full = sum / static_cast<uint32_t>(buffer.count);
    return out;
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

namespace {
void sat_inc(uint16_t& value) {
    if (value != 0xFFFFu) ++value;
}
}

void WifiAimProcessor::reset_profiler() {
    profile_counts_.fill(0);
    dsss_stage_counts_.fill(0);
    rejected_stats_ = {};
    accepted_stats_ = {};
}

void WifiAimProcessor::fill_dsss_counters(wifiaim::WireApReport& wire) const {
    // Fix8w-DIAG subtype. Eleven uint16_t counters fit in the existing SSID
    // payload; no WireApReport or stock message ABI changes are required.
    wire.ssid_len = 0xF8u;
    std::memcpy(wire.ssid, dsss_stage_counts_.data(),
                wifiaim::DSSS_STAGE_COUNT * sizeof(uint16_t));
}

void WifiAimProcessor::update_profile_stats(wifiaim::ProfilerStatsWire& stats,
                                             const wifiaim::M4OfdmTrace& trace,
                                             uint16_t clipped) {
    const uint16_t old_count = stats.captures;
    if (stats.captures != 0xFFFFu) ++stats.captures;
    const uint16_t count = stats.captures;
    if (!old_count) {
        stats.stf_min = stats.stf_mean = stats.stf_max = trace.stf_score;
        stats.ltf_min = stats.ltf_mean = stats.ltf_max = trace.ltf_score;
    } else if (count != old_count) {
        stats.stf_min = std::min(stats.stf_min, trace.stf_score);
        stats.stf_max = std::max(stats.stf_max, trace.stf_score);
        stats.stf_mean = static_cast<uint8_t>(
            static_cast<int32_t>(stats.stf_mean) +
            (static_cast<int32_t>(trace.stf_score) - stats.stf_mean) / count);
        stats.ltf_min = std::min(stats.ltf_min, trace.ltf_score);
        stats.ltf_max = std::max(stats.ltf_max, trace.ltf_score);
        stats.ltf_mean = static_cast<uint8_t>(
            static_cast<int32_t>(stats.ltf_mean) +
            (static_cast<int32_t>(trace.ltf_score) - stats.ltf_mean) / count);
    }
    if (trace.stage >= 1u) {
        const uint16_t old_cfo_count = stats.cfo_captures;
        if (stats.cfo_captures != 0xFFFFu) ++stats.cfo_captures;
        if (!old_cfo_count) {
            stats.cfo_min = stats.cfo_mean = stats.cfo_max = trace.cfo_hz;
        } else if (stats.cfo_captures != old_cfo_count) {
            stats.cfo_min = std::min(stats.cfo_min, trace.cfo_hz);
            stats.cfo_max = std::max(stats.cfo_max, trace.cfo_hz);
            stats.cfo_mean += (trace.cfo_hz - stats.cfo_mean) / stats.cfo_captures;
        }
    }
    const uint32_t room = 0xFFFFFFFFu - stats.clipped_components;
    stats.clipped_components += std::min<uint32_t>(room, clipped);
}

void WifiAimProcessor::fill_profile_counters(wifiaim::WireApReport& wire) const {
    wire.ssid_len = 0xFBu;
    std::memcpy(wire.bssid, profile_counts_.data(), 3u * sizeof(uint16_t));
    std::memcpy(wire.ssid, profile_counts_.data() + 3u,
                (wifiaim::PROFILE_COUNTER_COUNT - 3u) * sizeof(uint16_t));
}

void WifiAimProcessor::fill_profile_stats(wifiaim::WireApReport& wire, uint8_t subtype,
                                          const wifiaim::ProfilerStatsWire& stats) const {
    wire.ssid_len = subtype;
    std::memcpy(wire.ssid, &stats, sizeof(stats));
}

void WifiAimProcessor::send_profiler_snapshot() {
    wifiaim::WireApReport wire{};
    wire.channel = tuned_channel_;
    wire.flags = 0x80u;
    wire.capture_total = static_cast<uint16_t>(capture_attempts_ & 0x3FFFu);
    wire.decode_total = static_cast<uint16_t>(decode_successes_ & 0x3FFFu);
    fill_profile_counters(wire);
    send_wire_report(wire, diag_packet_);

    wire = {};
    wire.channel = tuned_channel_;
    wire.flags = 0x80u;
    fill_profile_stats(wire, 0xFCu, rejected_stats_);
    send_wire_report(wire, profile_rejected_packet_);

    wire = {};
    wire.channel = tuned_channel_;
    wire.flags = 0x80u;
    fill_profile_stats(wire, 0xFDu, accepted_stats_);
    send_wire_report(wire, profile_accepted_packet_);

    wire = {};
    wire.channel = tuned_channel_;
    wire.flags = 0x80u;
    fill_dsss_counters(wire);
    send_wire_report(wire, profile_dsss_packet_);
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
    fill_profile_counters(wire);
    send_wire_report(wire, diag_packet_);
}

void WifiAimProcessor::send_diag_capture_ready(const wifiaim::M4OfdmTrace& trace, uint16_t clipped) {
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
    wire.ssid[9] = static_cast<char>(trace.stf_score);
    std::memcpy(&wire.ssid[10], &clipped, sizeof(clipped));
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
    uint16_t clipped = 0;
    for (std::size_t n = 0; n < capture_count_; ++n) {
        const int16_t i = capture_[n].i;
        const int16_t q = capture_[n].q;
        if (i <= -127 || i >= 127) ++clipped;
        if (q <= -127 || q >= 127) ++clipped;
    }

    if (ofdm_trace.stf_admitted) sat_inc(profile_counts_[wifiaim::PROFILE_STF]);
    if (ofdm_trace.stage >= 1u) sat_inc(profile_counts_[wifiaim::PROFILE_LTF]);
    if (ofdm_trace.stage >= 3u) sat_inc(profile_counts_[wifiaim::PROFILE_SIGNAL_VITERBI]);
    if (ofdm_trace.stage >= 4u) sat_inc(profile_counts_[wifiaim::PROFILE_SIGNAL_PARITY]);
    if (ofdm_trace.stage >= 6u) sat_inc(profile_counts_[wifiaim::PROFILE_RATE_LENGTH]);
    if (ofdm_trace.stage >= 7u) sat_inc(profile_counts_[wifiaim::PROFILE_DATA_VITERBI]);
    if (ofdm_trace.post_stage >= 1u) sat_inc(profile_counts_[wifiaim::PROFILE_SERVICE]);
    if (ofdm_trace.post_stage >= 2u) sat_inc(profile_counts_[wifiaim::PROFILE_PROTOCOL]);
    if (ofdm_trace.post_stage >= 3u) sat_inc(profile_counts_[wifiaim::PROFILE_MANAGEMENT]);
    if (ofdm_trace.post_stage >= 4u) sat_inc(profile_counts_[wifiaim::PROFILE_BEACON_PROBE]);
    if (ofdm_trace.post_stage >= 5u) sat_inc(profile_counts_[wifiaim::PROFILE_SSID]);
    if (decoded) sat_inc(profile_counts_[wifiaim::PROFILE_FINAL_AP]);
    update_profile_stats(decoded ? accepted_stats_ : rejected_stats_, ofdm_trace, clipped);
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
    for (uint8_t stage = 0; stage < wifiaim::DSSS_STAGE_COUNT; ++stage) {
        if (ofdm_trace.dsss_stage_mask & static_cast<uint16_t>(1u << stage))
            sat_inc(dsss_stage_counts_[stage]);
    }
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
        fill_profile_counters(wire);
        send_wire_report(wire, diag_packet_);
    }

    if (freeze_for_diag) {
        // Keep capture_ and capture_count_ untouched until M0 opens the C8 file
        // and replies with stock CaptureConfig. Incoming RF is ignored while
        // Frozen/Dumping, so the saved bytes are exactly the decoded capture.
        diag_capture_pending_ = true;
        diag_dump_offset_ = 0;
        state_ = State::Frozen;
        send_diag_capture_ready(ofdm_trace, clipped);
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
            } else {
                // CaptureThread may already be asleep in BufferExchange::get()
                // when M0 asks it to stop. Feed frozen (never live) padding so
                // it wakes, observes termination, and lets CaptureConfig close.
                diag_stream_->write(capture_.data(), 400u);
            }
        }
        return;
    }
    if (state_ == State::Frozen) return;
    if (!enabled_) return;

    const EnergyPowers powers = block_powers(buffer);
    const uint32_t p = powers.full;

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
        // Fix8v shadow profilers only: production capture remains gated by
        // the unchanged full-block mean below.
        if (powers.max256 >= threshold) sat_inc(profile_counts_[wifiaim::PROFILE_SHADOW_256]);
        if (powers.max128 >= threshold) sat_inc(profile_counts_[wifiaim::PROFILE_SHADOW_128]);
        if (p >= threshold) {
            sat_inc(profile_counts_[wifiaim::PROFILE_ENERGY]);
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
            if (m.start && !enabled_) {
                reset_probe_diag();
                reset_profiler();
                diag_capture_saved_ = false;
            }

            // M0 pauses channel hopping while a one-shot dump is active. A
            // disable while still Frozen is the ABI-safe cancellation path for
            // an SD/open error before CaptureThread can send CaptureConfig.
            if (diag_capture_pending_) {
                enabled_ = m.start;
                if (!m.start && state_ == State::Frozen) {
                    diag_capture_pending_ = false;
                    diag_capture_saved_ = false;
                    capture_count_ = 0;
                    pretrigger_count_ = 0;
                    state_ = State::Waiting;
                    send_profiler_snapshot();
                }
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
            send_profiler_snapshot();
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
