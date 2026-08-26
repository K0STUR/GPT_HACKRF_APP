#include "ui_wifi_aim.hpp"

#include "baseband_api.hpp"
#include "event_m0.hpp"
#include "receiver_model.hpp"
#include "string_format.hpp"

#include <algorithm>
#include <cstring>

using namespace portapack;

namespace ui::external_app::wifi_aim {
namespace {
rf::Frequency channel_frequency(uint8_t ch) {
    if (ch >= 1 && ch <= 13) return 2'412'000'000ULL + static_cast<rf::Frequency>(ch - 1) * 5'000'000ULL;
    return 2'412'000'000ULL;
}
bool same_bssid(const std::array<uint8_t,6>& a, const uint8_t* b) {
    return std::memcmp(a.data(), b, 6) == 0;
}
void meta_text(char* out, std::size_t& pos, const char* text) {
    while (*text) out[pos++] = *text++;
}
void meta_uint(char* out, std::size_t& pos, uint32_t value) {
    char reverse[10];
    std::size_t count = 0;
    do {
        reverse[count++] = static_cast<char>('0' + value % 10u);
        value /= 10u;
    } while (value);
    while (count) out[pos++] = reverse[--count];
}
void meta_int(char* out, std::size_t& pos, int32_t value) {
    if (value < 0) {
        out[pos++] = '-';
        meta_uint(out, pos, static_cast<uint32_t>(-static_cast<int64_t>(value)));
    } else {
        meta_uint(out, pos, static_cast<uint32_t>(value));
    }
}
}

class BoundedC8Writer final : public stream::Writer {
   public:
    static constexpr std::size_t kCaptureBytes = 20'000u * 2u;
    Optional<File::Error> create(const std::filesystem::path& path) {
        return file_.create(path);
    }

    File::Result<File::Size> write(const void* const buffer, const File::Size bytes) override {
        const auto keep = std::min<File::Size>(bytes, remaining_);
        if (keep) {
            auto result = file_.write(buffer, keep);
            if (result.is_error()) return result.error();
            remaining_ -= keep;
        }
        if (!remaining_ && !notified_) {
            notified_ = true;
            CaptureThreadDoneMessage message{};
            EventDispatcher::send_message(message);
        }
        // Once 40 kB is complete, consume M4's drain padding without writing it.
        return File::Size{bytes};
    }

   private:
    File file_{};
    File::Size remaining_{kCaptureBytes};
    bool notified_{false};
};

WifiAimView::WifiAimView(NavigationView& nav) : nav_(nav) {
    target_levels_.fill(-1200);
    add_children({&field_lna,&field_vga,&field_rf_amp,&rssi,
                  &text_status,&text_ap,&text_bssid,&text_channel,&text_level,
                  &text_avg,&text_peak,&text_delta,&button_scan,&button_prev,
                  &button_next,&button_target,&button_ref,&button_mode});

    baseband::run_prepared_image(portapack::memory::map::m4_code.base());
    receiver_model.set_target_frequency(channel_frequency(1));
    receiver_model.set_baseband_bandwidth(20'000'000);
    receiver_model.set_sampling_rate(20'000'000);
    receiver_model.enable();
    set_decoder(false);

    button_scan.on_select = [this](Button&) { start_scan(); };
    button_prev.on_select = [this](Button&) {
        if (ap_count_) { selected_ = (selected_ + ap_count_ - 1) % ap_count_; update_ap_display(); }
    };
    button_next.on_select = [this](Button&) {
        if (ap_count_) { selected_ = (selected_ + 1) % ap_count_; update_ap_display(); }
    };
    button_target.on_select = [this](Button&) { select_target(); };
    button_ref.on_select = [this](Button&) {
        if (target_level_count_) { ref_x10_ = target_average(); ref_valid_ = true; update_aim_display(target_levels_[(target_level_pos_+15)%16]); }
    };
    button_mode.on_select = [this](Button&) { cycle_mode(); };
}

WifiAimView::~WifiAimView() {
    // Let a bounded one-shot transfer finish (or observe termination) before
    // shutting down M4, otherwise the worker could remain asleep on its FIFO.
    diag_capture_thread_.reset();
    set_decoder(false);
    receiver_model.disable();
    baseband::shutdown();
}

void WifiAimView::focus() { button_scan.focus(); }

void WifiAimView::set_decoder(bool on) {
    if (decoder_enabled_ == on) return;
    decoder_enabled_ = on;
    // ABI-safe reuse: our M4 image interprets HunterConfig.start as decoder enable.
    baseband::set_hunter_config(current_channel_, 0, on);
}

void WifiAimView::tune_channel(uint8_t ch) {
    if (ch < 1 || ch > 13) return;
    current_channel_ = ch;
    receiver_model.set_target_frequency(channel_frequency(ch));
    // Retuning while decoder is enabled: cycle it to reset M4 floor/warm-up.
    if (decoder_enabled_) { set_decoder(false); set_decoder(true); }
}

uint16_t WifiAimView::scan_capture_delta() const {
    return static_cast<uint16_t>((diag_capture_total_ - scan_capture_base_) & 0x3FFFu);
}

uint16_t WifiAimView::scan_decode_delta() const {
    return static_cast<uint16_t>((diag_decode_total_ - scan_decode_base_) & 0x3FFFu);
}

void WifiAimView::update_scan_status() {
    if (!scanning_) return;
    text_status.set("S " + to_string_dec_uint(scan_channel_) + "/13 C" +
                    to_string_dec_uint(scan_capture_delta()) + " D" +
                    to_string_dec_uint(scan_decode_delta()) + " M" +
                    to_string_dec_uint(diag_ack_channel_));
}

void WifiAimView::update_done_status() {
    if (scanning_ || target_set_) return;
    text_status.set("Done " + to_string_dec_uint(ap_count_) + "AP C" +
                    to_string_dec_uint(scan_capture_delta()) + " D" +
                    to_string_dec_uint(scan_decode_delta()) + " M" +
                    to_string_dec_uint(diag_ack_channel_));
}

void WifiAimView::start_scan() {
    ap_count_ = 0; selected_ = 0; target_set_ = false;
    target_level_count_ = target_level_pos_ = 0; peak_x10_ = -1200; ref_valid_ = false;
    scan_capture_base_ = diag_capture_total_;
    scan_decode_base_ = diag_decode_total_;
    diag_ack_channel_ = 0;
    scanning_ = true; scan_channel_ = 1; timer_ms_ = 0;
    tune_channel(scan_channel_); set_decoder(true);
    update_scan_status();
}

void WifiAimView::end_scan() {
    scanning_ = false; set_decoder(false);
    // Initial value; M4 final disabled-state telemetry refreshes C/D/M and
    // Fix8a probe values once more after the last channel completes.
    update_done_status();
    update_ap_display();
}

void WifiAimView::select_target() {
    if (!ap_count_ || selected_ >= ap_count_) return;
    const auto& ap = aps_[selected_];
    target_set_ = true; target_bssid_ = ap.bssid; target_ssid_ = ap.ssid; target_ssid_len_ = ap.ssid_len; target_channel_ = ap.channel;
    scanning_ = false; tune_channel(target_channel_);
    target_level_count_ = target_level_pos_ = 0; peak_x10_ = -1200; ref_valid_ = false;
    auto_phase_ms_ = 0;
    if (decode_mode_ == DecodeMode::Off) set_decoder(false); else set_decoder(true);
    text_status.set("AIM target locked");
    update_ap_display();
}

void WifiAimView::cycle_mode() {
    if (decode_mode_ == DecodeMode::Off) decode_mode_ = DecodeMode::Auto;
    else if (decode_mode_ == DecodeMode::Auto) decode_mode_ = DecodeMode::On;
    else decode_mode_ = DecodeMode::Off;
    button_mode.set_text(decode_mode_ == DecodeMode::Off ? "OFF" : decode_mode_ == DecodeMode::Auto ? "AUTO" : "ON");
    auto_phase_ms_ = 0;
    if (!target_set_ || scanning_) return;
    set_decoder(decode_mode_ != DecodeMode::Off);
}

void WifiAimView::on_frame_sync() {
    constexpr uint32_t frame_ms = 17;
    if (scanning_) {
        // Do not retune while the selected 1 ms buffer is being drained to SD.
        if (diag_capture_active_) return;
        timer_ms_ += frame_ms;
        // Give normal ~100 ms beacon intervals several chances per channel.
        if (timer_ms_ >= 1000) {
            timer_ms_ = 0;
            if (scan_channel_ >= 13) { end_scan(); return; }
            ++scan_channel_; tune_channel(scan_channel_);
            update_scan_status();
        }
        return;
    }
    if (target_set_ && decode_mode_ == DecodeMode::Auto) {
        // 300 ms decode window, 200 ms quiet window. This really gates M4 DSP.
        auto_phase_ms_ = (auto_phase_ms_ + frame_ms) % 500;
        set_decoder(auto_phase_ms_ < 300);
    }
}

void WifiAimView::on_packet(const FSKRxPacketMessage* msg) {
    if (!msg || !msg->packet || msg->packet->dataLen < sizeof(wifiaim::WireApReport)) return;
    wifiaim::WireApReport w{};
    std::memcpy(&w, msg->packet->data, sizeof(w));
    if (std::memcmp(w.magic, "WAIM", 4) != 0 || w.version != 3 || w.channel < 1 || w.channel > 13) return;

    // Fix7c/Fix8a transport diagnostics over the existing FSKPacket path.
    // This avoids adding a HunterTrigger MessageHandlerRegistration to M0.
    diag_capture_total_ = static_cast<uint16_t>(w.capture_total & 0x3FFFu);
    diag_decode_total_ = static_cast<uint16_t>(w.decode_total & 0x3FFFu);
    diag_ack_channel_ = w.channel;
    update_scan_status();

    // Fix8t-DIAG capture-ready subtype. M4 is frozen and will ignore live RF
    // until the bounded C8 worker has consumed exactly 20,000 IQ samples.
    if ((w.flags & 0x80u) && w.ssid_len == 0xFAu) {
        start_diag_capture(w);
        return;
    }

    // bit7 marks a diagnostics-only packet; it is not an access point report.
    if (w.flags & 0x80u) {
        // While aiming, diagnostics must never overwrite LIVE/AVG/PEAK/DELTA.
        if (target_set_) return;

        // Fix8a reuses otherwise-unused diagnostic BSSID bytes. ssid_len=0xF8
        // distinguishes this from older Fix7b/Fix7c telemetry.
        if (w.ssid_len == 0xF8u || w.ssid_len == 0xF9u) {
            text_level.set("HIT 16/64/B " + to_string_dec_uint(w.bssid[0]) + "/" +
                           to_string_dec_uint(w.bssid[1]) + "/" + to_string_dec_uint(w.bssid[2]));
            text_avg.set("Q   16/64/B " + to_string_dec_uint(w.bssid[3]) + "/" +
                         to_string_dec_uint(w.bssid[4]) + "/" + to_string_dec_uint(w.bssid[5]));
            text_peak.set("M4 CH: " + to_string_dec_uint(diag_ack_channel_));
        }
        if (w.ssid_len == 0xF9u) {
            text_ap.set("OF L/H/V/P " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[0])) + "/" +
                        to_string_dec_uint(static_cast<uint8_t>(w.ssid[1])) + "/" +
                        to_string_dec_uint(static_cast<uint8_t>(w.ssid[2])) + "/" +
                        to_string_dec_uint(static_cast<uint8_t>(w.ssid[3])));
            text_bssid.set("OF R/N/D/M " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[4])) + "/" +
                           to_string_dec_uint(static_cast<uint8_t>(w.ssid[5])) + "/" +
                           to_string_dec_uint(static_cast<uint8_t>(w.ssid[6])) + "/" +
                           to_string_dec_uint(static_cast<uint8_t>(w.ssid[7])));
            const uint16_t n = static_cast<uint16_t>(static_cast<uint8_t>(w.ssid[10])) |
                               static_cast<uint16_t>(static_cast<uint8_t>(w.ssid[11]) << 8);
            text_channel.set("SQ " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[8])) +
                             " R " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[9])) +
                             " N " + to_string_dec_uint(n));

            text_delta.set("P S/F/G/B/I " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[12])) + "/" +
                           to_string_dec_uint(static_cast<uint8_t>(w.ssid[13])) + "/" +
                           to_string_dec_uint(static_cast<uint8_t>(w.ssid[14])) + "/" +
                           to_string_dec_uint(static_cast<uint8_t>(w.ssid[15])) + "/" +
                           to_string_dec_uint(static_cast<uint8_t>(w.ssid[16])));
            text_peak.set("DS A/S " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[19])) + "/" +
                          to_string_dec_uint(static_cast<uint8_t>(w.ssid[20])) + " FC " +
                          to_string_dec_uint(static_cast<uint8_t>(w.ssid[17])) + "/" +
                          to_string_dec_uint(static_cast<uint8_t>(w.ssid[18])));
        }
        update_done_status();
        // Fix8e usability: the final disabled-state telemetry arrives after
        // end_scan(). If an AP was found, restore the user-facing AP/BSSID/CH
        // fields after recording diagnostics instead of hiding the result.
        if (!scanning_ && ap_count_) update_ap_display();
        return;
    }

    std::size_t ap_index = ap_count_;
    for (std::size_t i = 0; i < ap_count_; ++i) {
        if (same_bssid(aps_[i].bssid, w.bssid)) { ap_index = i; break; }
    }
    if (ap_index == ap_count_) {
        if (ap_count_ >= kMaxAps) return;
        ApEntry& a = aps_[ap_count_++];
        for (std::size_t i = 0; i < 6; ++i) a.bssid[i] = w.bssid[i];
        const bool hidden = (w.flags & 1) != 0;
        if (hidden) {
            static constexpr char kHidden[] = "<hidden>";
            a.ssid_len = sizeof(kHidden) - 1;
            std::memcpy(a.ssid.data(), kHidden, a.ssid_len);
        } else {
            a.ssid_len = std::min<uint8_t>(w.ssid_len, 32);
            if (a.ssid_len) std::memcpy(a.ssid.data(), w.ssid, a.ssid_len);
        }
        a.ssid[a.ssid_len] = 0;
        a.channel = w.channel; a.last_db_x10 = w.packet_db_x10; a.hits = 1; a.phy_rate_mbps = w.phy_rate_mbps;
        ap_index = ap_count_ - 1;
    } else {
        ApEntry& a = aps_[ap_index];
        a.last_db_x10 = w.packet_db_x10; a.phy_rate_mbps = w.phy_rate_mbps; ++a.hits;
        if (a.ssid_len && a.ssid[0] == '<' && w.ssid_len && !(w.flags & 1)) {
            a.ssid_len = std::min<uint8_t>(w.ssid_len, 32);
            std::memcpy(a.ssid.data(), w.ssid, a.ssid_len);
            a.ssid[a.ssid_len] = 0;
        }
    }

    if (target_set_ && same_bssid(target_bssid_, w.bssid)) {
        push_target_level(w.packet_db_x10);
        update_aim_display(w.packet_db_x10);
    } else if (!scanning_) {
        update_ap_display();
        update_done_status();
    }
}

void WifiAimView::start_diag_capture(const wifiaim::WireApReport& wire) {
    if (diag_capture_active_) return;

    diag_metadata_ = {};
    diag_metadata_.channel = wire.channel;
    for (std::size_t i = 0; i < 6; ++i) diag_metadata_.ofdm_stage_hits[i] = wire.bssid[i];
    diag_metadata_.ofdm_stage_hits[6] = static_cast<uint8_t>(wire.ssid[0]);
    diag_metadata_.ofdm_stage_hits[7] = static_cast<uint8_t>(wire.ssid[1]);
    diag_metadata_.sq = static_cast<uint8_t>(wire.ssid[2]);
    diag_metadata_.lna_gain_db = receiver_model.lna();
    diag_metadata_.vga_gain_db = receiver_model.vga();
    diag_metadata_.rf_amp = receiver_model.rf_amp();
    std::memcpy(&diag_metadata_.ltf_position, &wire.ssid[3], sizeof(diag_metadata_.ltf_position));
    std::memcpy(&diag_metadata_.cfo_hz, &wire.ssid[5], sizeof(diag_metadata_.cfo_hz));

    const auto dir_error = ensure_directory(u"WIFI_DIAG");
    if (dir_error.code()) {
        baseband::capture_stop();
        text_status.set("IQ ERR SD");
        return;
    }
    diag_c8_path_ = next_filename_matching_pattern(u"WIFI_DIAG/WAIM_???.C8");
    if (diag_c8_path_.empty()) {
        baseband::capture_stop();
        text_status.set("IQ ERR SD");
        return;
    }
    diag_txt_path_ = diag_c8_path_;
    diag_txt_path_.replace_extension(u".TXT");

    diag_capture_active_ = true;
    text_status.set("IQ SAVING...");
    auto writer = std::make_unique<BoundedC8Writer>();
    const auto create_error = writer->create(diag_c8_path_);
    if (create_error.is_valid()) {
        diag_capture_active_ = false;
        baseband::capture_stop();
        text_status.set("IQ ERR SD");
        return;
    }
    diag_capture_thread_ = std::make_unique<CaptureThread>(
        std::move(writer), 400u, 2u,
        []() {
            CaptureThreadDoneMessage message{};
            EventDispatcher::send_message(message);
        },
        [](File::Error error) {
            CaptureThreadDoneMessage message{error.code()};
            EventDispatcher::send_message(message);
        });
}

void WifiAimView::on_diag_capture_done(const CaptureThreadDoneMessage& message) {
    if (!diag_capture_active_) return;
    diag_capture_thread_.reset();
    diag_capture_active_ = false;
    if (message.error) {
        text_status.set("IQ ERR SD");
        return;
    }

    const auto metadata_error = write_diag_metadata();
    if (metadata_error.is_valid()) {
        text_status.set("IQ ERR SD");
        return;
    }
    if (diag_saved_count_ != 0xFFu) ++diag_saved_count_;
    text_status.set("IQ SAVED " + to_string_dec_uint(diag_saved_count_));
}

Optional<File::Error> WifiAimView::write_diag_metadata() {
    File metadata;
    const auto create_error = metadata.create(diag_txt_path_);
    if (create_error.is_valid()) return create_error;

    char text[320];
    std::size_t pos = 0;
#define META_LABEL(label, value)       \
    do {                               \
        meta_text(text, pos, label);   \
        meta_uint(text, pos, value);   \
        meta_text(text, pos, "\r\n"); \
    } while (0)
    meta_text(text, pos, "sample_rate_sps=20000000\r\nfirmware=" VERSION_STRING "\r\n");
    META_LABEL("frequency_hz=", static_cast<uint32_t>(channel_frequency(diag_metadata_.channel)));
    META_LABEL("channel=", diag_metadata_.channel);
    META_LABEL("lna_gain_db=", diag_metadata_.lna_gain_db);
    META_LABEL("vga_gain_db=", diag_metadata_.vga_gain_db);
    META_LABEL("rf_amp=", diag_metadata_.rf_amp ? 1u : 0u);
    META_LABEL("SQ=", diag_metadata_.sq);
    meta_text(text, pos, "L/H/V/P=");
    for (std::size_t i = 0; i < 4; ++i) {
        if (i) text[pos++] = '/';
        meta_uint(text, pos, diag_metadata_.ofdm_stage_hits[i]);
    }
    meta_text(text, pos, "\r\nR/N/D/M=");
    for (std::size_t i = 4; i < 8; ++i) {
        if (i != 4) text[pos++] = '/';
        meta_uint(text, pos, diag_metadata_.ofdm_stage_hits[i]);
    }
    meta_text(text, pos, "\r\n");
    META_LABEL("ltf_position=", diag_metadata_.ltf_position);
    meta_text(text, pos, "cfo_hz=");
    meta_int(text, pos, diag_metadata_.cfo_hz);
    meta_text(text, pos, "\r\n");
#undef META_LABEL

    const auto write_result = metadata.write(text, pos);
    if (write_result.is_error()) return write_result.error();
    metadata.close();
    return {};
}

void WifiAimView::push_target_level(int16_t x) {
    target_levels_[target_level_pos_] = x;
    target_level_pos_ = (target_level_pos_ + 1) % target_levels_.size();
    if (target_level_count_ < target_levels_.size()) ++target_level_count_;
    if (x > peak_x10_) peak_x10_ = x;
}

int16_t WifiAimView::target_average() const {
    if (!target_level_count_) return -1200;
    int32_t sum = 0;
    for (std::size_t i=0;i<target_level_count_;++i) sum += target_levels_[i];
    return static_cast<int16_t>(sum / static_cast<int32_t>(target_level_count_));
}

std::string WifiAimView::db10(int16_t x10) const {
    const bool neg = x10 < 0;
    int32_t a = neg ? -static_cast<int32_t>(x10) : x10;
    return std::string(neg ? "-" : "") + to_string_dec_uint(static_cast<uint32_t>(a/10)) + "." + to_string_dec_uint(static_cast<uint32_t>(a%10)) + " dBr";
}

std::string WifiAimView::mac(const std::array<uint8_t,6>& b) const {
    return to_string_mac_address(const_cast<uint8_t*>(b.data()), 6, false);
}

void WifiAimView::update_ap_display() {
    if (target_set_) {
        text_ap.set("AP: " + std::string(target_ssid_.data(), target_ssid_len_));
        text_bssid.set("BSSID: " + mac(target_bssid_));
        text_channel.set("CH: " + to_string_dec_uint(target_channel_) + " / " + to_string_dec_uint(channel_frequency(target_channel_)/1'000'000ULL) + "MHz");
        return;
    }
    if (!ap_count_) {
        text_ap.set("AP: -"); text_bssid.set("BSSID: -"); text_channel.set("CH: -"); return;
    }
    if (selected_ >= ap_count_) selected_ = 0;
    const auto& a=aps_[selected_];
    text_ap.set("AP " + to_string_dec_uint(selected_+1) + "/" + to_string_dec_uint(ap_count_) + ": " + std::string(a.ssid.data(), a.ssid_len));
    text_bssid.set("BSSID: " + mac(a.bssid));
    text_channel.set("CH: " + to_string_dec_uint(a.channel) + "  " + to_string_dec_uint(a.phy_rate_mbps) + "M  last " + db10(a.last_db_x10));
}

void WifiAimView::update_aim_display(int16_t live) {
    text_level.set("LIVE target: " + db10(live));
    const int16_t avg=target_average();
    text_avg.set("AVG target: " + db10(avg));
    text_peak.set("PEAK target: " + db10(peak_x10_));
    if (ref_valid_) text_delta.set("DELTA REF: " + db10(static_cast<int16_t>(avg-ref_x10_)));
    else text_delta.set("DELTA REF: press REF");
}

} // namespace ui::external_app::wifi_aim
