#pragma once

#include "ui.hpp"
#include "ui_navigation.hpp"
#include "ui_receiver.hpp"
#include "message.hpp"
#include "file.hpp"
#include "capture_thread.hpp"
#include "wifi_aim_wire.hpp"

#include <array>
#include <cstdint>
#include <memory>
#include <string>

namespace ui::external_app::wifi_aim {

struct DiagCaptureMetadata {
    uint8_t channel{0};
    std::array<uint8_t, 8> ofdm_stage_hits{};
    uint8_t sq{0};
    uint8_t stf{0};
    uint8_t lna_gain_db{0};
    uint8_t vga_gain_db{0};
    bool rf_amp{false};
    uint16_t ltf_position{0};
    int32_t cfo_hz{0};
    uint16_t clipped_components{0};
};

class WifiAimView final : public View {
   public:
    explicit WifiAimView(NavigationView& nav);
    ~WifiAimView();
    void focus() override;
    std::string title() const override { return "WiFi AIM"; }

   private:
    NavigationView& nav_;
    bool scanning_{false};
    bool decoder_enabled_{false};
    uint8_t scan_channel_{1};
    uint8_t current_channel_{1};
    uint32_t timer_ms_{0};
    bool diag_capture_active_{false};
    volatile bool diag_capture_done_{false};
    volatile uint32_t diag_capture_error_{0};
    DiagCaptureMetadata diag_metadata_{};
    std::filesystem::path diag_c8_path_{};
    std::filesystem::path diag_txt_path_{};
    std::unique_ptr<CaptureThread> diag_capture_thread_{};

    // Fix7b/Fix7c receive M4 diagnostics through the already-existing
    // FSKPacket handler, avoiding a new HunterTrigger registration in M0.
    uint16_t diag_capture_total_{0};
    uint16_t diag_decode_total_{0};
    uint16_t scan_capture_base_{0};
    uint16_t scan_decode_base_{0};
    uint8_t diag_ack_channel_{0};
    std::array<uint16_t, wifiaim::PROFILE_COUNTER_COUNT> profile_counts_{};
    wifiaim::ProfilerStatsWire profile_rejected_{};
    wifiaim::ProfilerStatsWire profile_accepted_{};
    uint8_t profile_page_{0};

    LNAGainField field_lna{{UI_POS_X(0), UI_POS_Y(0)}};
    VGAGainField field_vga{{UI_POS_X(7), UI_POS_Y(0)}};
    RFAmpField field_rf_amp{{UI_POS_X(14), UI_POS_Y(0)}};
    RSSI rssi{{UI_POS_X(0), UI_POS_Y(1), UI_POS_MAXWIDTH, 4}};

    Text text_status{{UI_POS_X(1), UI_POS_Y(5), 224,16}, "Ready"};
    Text text_ap{{UI_POS_X(1), UI_POS_Y(6), 224,16}, "AP: -"};
    Text text_bssid{{UI_POS_X(1), UI_POS_Y(7), 224,16}, "BSSID: -"};
    Text text_channel{{UI_POS_X(1), UI_POS_Y(8), 224,16}, "CH: -"};
    Text text_level{{UI_POS_X(1), UI_POS_Y(9), 224,16}, "LIVE: -"};
    Text text_avg{{UI_POS_X(1), UI_POS_Y(10), 224,16}, "AVG: -"};
    Text text_peak{{UI_POS_X(1), UI_POS_Y(11), 224,16}, "PEAK: -"};
    Text text_delta{{UI_POS_X(1), UI_POS_Y(12), 224,16}, "DELTA REF: -"};

    Button button_scan{{UI_POS_X(1), UI_POS_Y(14), 70,28}, "RUN 10s"};
    Button button_prev{{UI_POS_X(10), UI_POS_Y(14), 62,28}, "CH -"};
    Button button_next{{UI_POS_X(20), UI_POS_Y(14), 62,28}, "CH +"};
    Button button_target{{UI_POS_X(1), UI_POS_Y(17), 70,28}, "COUNT"};
    Button button_ref{{UI_POS_X(10), UI_POS_Y(17), 62,28}, "REJ"};
    Button button_mode{{UI_POS_X(20), UI_POS_Y(17), 62,28}, "ACC"};

    MessageHandlerRegistration frame_sync_handler_{
        Message::ID::DisplayFrameSync,
        [this](const Message* const) { on_frame_sync(); }};
    MessageHandlerRegistration packet_handler_{
        Message::ID::FSKPacket,
        [this](const Message* const p) { on_packet(static_cast<const FSKRxPacketMessage*>(p)); }};
    void set_decoder(bool on);
    void tune_channel(uint8_t ch);
    void start_scan();
    void end_scan();
    void on_frame_sync();
    void on_packet(const FSKRxPacketMessage* msg);
    void start_diag_capture(const wifiaim::WireApReport& wire);
    void on_diag_capture_done();
    Optional<File::Error> write_diag_metadata();
    void update_scan_status();
    void update_done_status();
    uint16_t scan_capture_delta() const;
    uint16_t scan_decode_delta() const;
    void update_profile_display();
    std::string signed_dec(int32_t value) const;
};

} // namespace ui::external_app::wifi_aim
