#include "ui_wifi_aim.hpp"

#include "baseband_api.hpp"
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
}

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

void WifiAimView::start_scan() {
    ap_count_ = 0; selected_ = 0; target_set_ = false;
    target_level_count_ = target_level_pos_ = 0; peak_x10_ = -1200; ref_valid_ = false;
    scanning_ = true; scan_channel_ = 1; timer_ms_ = 0;
    tune_channel(scan_channel_); set_decoder(true);
    text_status.set("SCAN CH1/13...");
}

void WifiAimView::end_scan() {
    scanning_ = false; set_decoder(false);
    text_status.set("Scan done: " + to_string_dec_uint(ap_count_) + " AP");
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
        timer_ms_ += frame_ms;
        if (timer_ms_ >= 450) {
            timer_ms_ = 0;
            if (scan_channel_ >= 13) { end_scan(); return; }
            ++scan_channel_; tune_channel(scan_channel_);
            text_status.set("SCAN CH" + to_string_dec_uint(scan_channel_) + "/13...");
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
    if (std::memcmp(w.magic, "WAIM", 4) != 0 || w.version != 2 || w.channel < 1 || w.channel > 13) return;

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
    }
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
