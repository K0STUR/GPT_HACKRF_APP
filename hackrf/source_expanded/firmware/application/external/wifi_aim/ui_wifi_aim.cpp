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
    explicit BoundedC8Writer(volatile bool* done) : done_{done} {}
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
            *done_ = true;
        }
        // Once 40 kB is complete, consume M4's drain padding without writing it.
        return File::Size{bytes};
    }

   private:
    File file_{};
    File::Size remaining_{kCaptureBytes};
    bool notified_{false};
    volatile bool* done_{nullptr};
};

WifiAimView::WifiAimView(NavigationView& nav) : nav_(nav) {
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
        if (!scanning_) { tune_channel(current_channel_ > 1 ? current_channel_ - 1 : 13); update_profile_display(); }
    };
    button_next.on_select = [this](Button&) {
        if (!scanning_) { tune_channel(current_channel_ < 13 ? current_channel_ + 1 : 1); update_profile_display(); }
    };
    button_target.on_select = [this](Button&) { profile_page_ = 0u; update_profile_display(); };
    button_ref.on_select = [this](Button&) { profile_page_ = 1u; update_profile_display(); };
    // ACC alternates accepted-capture statistics and the Fix8w DSSS pipeline.
    button_mode.on_select = [this](Button&) {
        profile_page_ = profile_page_ == 2u ? 3u : 2u;
        update_profile_display();
    };
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
    text_status.set(std::string(diag_capture_done_ ? "IQ SAVED " : "PROF ") +
                    "CH" + to_string_dec_uint(current_channel_) + " " +
                    to_string_dec_uint(timer_ms_ / 1000u) + "/10s E" +
                    to_string_dec_uint(profile_counts_[wifiaim::PROFILE_ENERGY]));
}

void WifiAimView::update_done_status() {
    if (scanning_) return;
    text_status.set("DONE CH" + to_string_dec_uint(current_channel_) + " AP" +
                    to_string_dec_uint(profile_counts_[wifiaim::PROFILE_FINAL_AP]));
}

void WifiAimView::start_scan() {
    scan_capture_base_ = diag_capture_total_;
    scan_decode_base_ = diag_decode_total_;
    diag_ack_channel_ = 0;
    profile_counts_.fill(0);
    profile_rejected_ = {};
    profile_accepted_ = {};
    dsss_stage_counts_.fill(0);
    diag_capture_done_ = false;
    scanning_ = true; scan_channel_ = current_channel_; timer_ms_ = 0;
    tune_channel(current_channel_); set_decoder(true);
    update_scan_status();
}

void WifiAimView::end_scan() {
    scanning_ = false; set_decoder(false);
    // Initial value; M4 final disabled-state telemetry refreshes C/D/M and
    // Fix8a probe values once more after the last channel completes.
    update_done_status();
    update_profile_display();
}

void WifiAimView::on_frame_sync() {
    constexpr uint32_t frame_ms = 17;
    if (diag_capture_active_ && diag_capture_done_) on_diag_capture_done();
    if (scanning_) {
        // Do not retune while the selected 1 ms buffer is being drained to SD.
        if (diag_capture_active_) return;
        timer_ms_ += frame_ms;
        if (timer_ms_ >= 10000u) { end_scan(); return; }
        update_scan_status();
        return;
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

    if ((w.flags & 0x80u) && w.ssid_len == 0xFBu) {
        std::memcpy(profile_counts_.data(), w.bssid, 3u * sizeof(uint16_t));
        std::memcpy(profile_counts_.data() + 3u, w.ssid,
                    (wifiaim::PROFILE_COUNTER_COUNT - 3u) * sizeof(uint16_t));
        update_profile_display();
        return;
    }
    if ((w.flags & 0x80u) && w.ssid_len == 0xF8u) {
        std::memcpy(dsss_stage_counts_.data(), w.ssid,
                    wifiaim::DSSS_STAGE_COUNT * sizeof(uint16_t));
        update_profile_display();
        return;
    }
    if ((w.flags & 0x80u) && (w.ssid_len == 0xFCu || w.ssid_len == 0xFDu)) {
        auto& stats = w.ssid_len == 0xFCu ? profile_rejected_ : profile_accepted_;
        std::memcpy(&stats, w.ssid, sizeof(stats));
        update_profile_display();
        return;
    }

    // Real AP reports are already counted by M4 as PROFILE_FINAL_AP. Fix8v
    // intentionally omits the old AP browser/aim mode to fit the profiler in
    // the 32 kB external-app slot without changing the decoder.
}

void WifiAimView::start_diag_capture(const wifiaim::WireApReport& wire) {
    if (diag_capture_active_) return;

    diag_metadata_ = {};
    diag_metadata_.channel = wire.channel;
    for (std::size_t i = 0; i < 6; ++i) diag_metadata_.ofdm_stage_hits[i] = wire.bssid[i];
    diag_metadata_.ofdm_stage_hits[6] = static_cast<uint8_t>(wire.ssid[0]);
    diag_metadata_.ofdm_stage_hits[7] = static_cast<uint8_t>(wire.ssid[1]);
    diag_metadata_.sq = static_cast<uint8_t>(wire.ssid[2]);
    diag_metadata_.stf = static_cast<uint8_t>(wire.ssid[9]);
    diag_metadata_.lna_gain_db = receiver_model.lna();
    diag_metadata_.vga_gain_db = receiver_model.vga();
    diag_metadata_.rf_amp = receiver_model.rf_amp();
    std::memcpy(&diag_metadata_.ltf_position, &wire.ssid[3], sizeof(diag_metadata_.ltf_position));
    std::memcpy(&diag_metadata_.cfo_hz, &wire.ssid[5], sizeof(diag_metadata_.cfo_hz));
    std::memcpy(&diag_metadata_.clipped_components, &wire.ssid[10], sizeof(diag_metadata_.clipped_components));

    const auto dir_error = ensure_directory(u"WIFI_DIAG");
    if (dir_error.code()) {
        set_decoder(false);
        set_decoder(true);
        text_status.set("IQ ERR SD");
        return;
    }
    diag_c8_path_ = next_filename_matching_pattern(u"WIFI_DIAG/WAIM_???.C8");
    if (diag_c8_path_.empty()) {
        set_decoder(false);
        set_decoder(true);
        text_status.set("IQ ERR SD");
        return;
    }
    diag_txt_path_ = diag_c8_path_;
    diag_txt_path_.replace_extension(u".TXT");

    diag_capture_done_ = false;
    diag_capture_error_ = 0;
    diag_capture_active_ = true;
    auto writer = std::make_unique<BoundedC8Writer>(&diag_capture_done_);
    const auto create_error = writer->create(diag_c8_path_);
    if (create_error.is_valid()) {
        diag_capture_active_ = false;
        set_decoder(false);
        set_decoder(true);
        text_status.set("IQ ERR SD");
        return;
    }
    diag_capture_thread_ = std::make_unique<CaptureThread>(
        std::move(writer), 400u, 2u,
        [this]() {
            diag_capture_done_ = true;
        },
        [this](File::Error error) {
            diag_capture_error_ = error.code();
            diag_capture_done_ = true;
        });
}

void WifiAimView::on_diag_capture_done() {
    if (!diag_capture_active_) return;
    diag_capture_thread_.reset();
    diag_capture_active_ = false;
    if (diag_capture_error_) {
        text_status.set("IQ ERR SD");
        return;
    }

    const auto metadata_error = write_diag_metadata();
    if (metadata_error.is_valid()) {
        text_status.set("IQ ERR SD");
        return;
    }
    text_status.set("IQ SAVED 1");
}

Optional<File::Error> WifiAimView::write_diag_metadata() {
    File metadata;
    const auto create_error = metadata.create(diag_txt_path_);
    if (create_error.is_valid()) return create_error;

    char text[420];
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
    META_LABEL("STF=", diag_metadata_.stf);
    META_LABEL("clipped_components=", diag_metadata_.clipped_components);
    META_LABEL("clipping_permille=", static_cast<uint32_t>(diag_metadata_.clipped_components) / 40u);
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

std::string WifiAimView::signed_dec(int32_t value) const {
    if (value >= 0) return to_string_dec_uint(static_cast<uint32_t>(value));
    return "-" + to_string_dec_uint(static_cast<uint32_t>(-static_cast<int64_t>(value)));
}

void WifiAimView::update_profile_display() {
    if (scanning_) update_scan_status();
    else update_done_status();

    if (profile_page_ == 0u) {
        text_ap.set("E/256/128 " + to_string_dec_uint(profile_counts_[wifiaim::PROFILE_ENERGY]) + "/" +
                    to_string_dec_uint(profile_counts_[wifiaim::PROFILE_SHADOW_256]) + "/" +
                    to_string_dec_uint(profile_counts_[wifiaim::PROFILE_SHADOW_128]));
        text_bssid.set("STF/LTF " + to_string_dec_uint(profile_counts_[wifiaim::PROFILE_STF]) + "/" +
                       to_string_dec_uint(profile_counts_[wifiaim::PROFILE_LTF]));
        text_channel.set("SIG V/P/RL " + to_string_dec_uint(profile_counts_[wifiaim::PROFILE_SIGNAL_VITERBI]) + "/" +
                         to_string_dec_uint(profile_counts_[wifiaim::PROFILE_SIGNAL_PARITY]) + "/" +
                         to_string_dec_uint(profile_counts_[wifiaim::PROFILE_RATE_LENGTH]));
        text_level.set("DATA/SVC " + to_string_dec_uint(profile_counts_[wifiaim::PROFILE_DATA_VITERBI]) + "/" +
                       to_string_dec_uint(profile_counts_[wifiaim::PROFILE_SERVICE]));
        text_avg.set("VER/MGMT " + to_string_dec_uint(profile_counts_[wifiaim::PROFILE_PROTOCOL]) + "/" +
                     to_string_dec_uint(profile_counts_[wifiaim::PROFILE_MANAGEMENT]));
        text_peak.set("BPR/SSID " + to_string_dec_uint(profile_counts_[wifiaim::PROFILE_BEACON_PROBE]) + "/" +
                      to_string_dec_uint(profile_counts_[wifiaim::PROFILE_SSID]));
        text_delta.set("FINAL AP " + to_string_dec_uint(profile_counts_[wifiaim::PROFILE_FINAL_AP]));
        return;
    }

    if (profile_page_ == 3u) {
        text_ap.set("DSSS pipeline");
        text_bssid.set("ADM/BARK " + to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_ADMISSION]) + "/" +
                       to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_BARKER_CORRELATION]));
        text_channel.set("TIME/DIFF " + to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_SYMBOL_TIMING]) + "/" +
                         to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_DIFFERENTIAL_DECODE]));
        text_level.set("DSCR/PLCP " + to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_DESCRAMBLE]) + "/" +
                       to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_PLCP_HEADER]));
        text_avg.set("PAY/MAC " + to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_PAYLOAD]) + "/" +
                     to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_MAC_TYPE]));
        text_peak.set("BPR/SSID " + to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_BEACON_PROBE]) + "/" +
                      to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_SSID]));
        text_delta.set("DSSS AP " + to_string_dec_uint(dsss_stage_counts_[wifiaim::DSSS_FINAL_AP]));
        return;
    }

    const auto& s = profile_page_ == 1u ? profile_rejected_ : profile_accepted_;
    text_ap.set(profile_page_ == 1u ? "REJECTED captures" : "ACCEPTED captures");
    text_bssid.set("N " + to_string_dec_uint(s.captures));
    text_channel.set("STF min/avg/max " + to_string_dec_uint(s.stf_min) + "/" +
                     to_string_dec_uint(s.stf_mean) + "/" + to_string_dec_uint(s.stf_max));
    text_level.set("LTF min/avg/max " + to_string_dec_uint(s.ltf_min) + "/" +
                   to_string_dec_uint(s.ltf_mean) + "/" + to_string_dec_uint(s.ltf_max));
    text_avg.set("CFO min " + signed_dec(s.cfo_min));
    text_peak.set("CFO avg/max " + signed_dec(s.cfo_mean) + "/" + signed_dec(s.cfo_max));
    const uint32_t clip_permille = s.captures
        ? s.clipped_components / (static_cast<uint32_t>(s.captures) * 40u)
        : 0u;
    text_delta.set("CLIP " + to_string_dec_uint(s.clipped_components) + " " +
                   to_string_dec_uint(clip_permille / 10u) + "." +
                   to_string_dec_uint(clip_permille % 10u) + "%");
}

} // namespace ui::external_app::wifi_aim
