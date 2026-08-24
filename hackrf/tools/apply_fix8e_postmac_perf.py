#!/usr/bin/env python3
from pathlib import Path

ROOT = Path('hackrf/source_expanded')

def replace_once(path, old, new):
    p = ROOT / path
    text = p.read_text()
    if old not in text:
        raise SystemExit(f'anchor not found in {p}: {old[:80]!r}')
    if text.count(old) != 1:
        raise SystemExit(f'anchor not unique in {p}: count={text.count(old)}')
    p.write_text(text.replace(old, new, 1))

# ---- PHY trace + DSSS gating ----
replace_once(
    'firmware/common/wifi_aim/wifi_aim_phy.hpp',
'''struct M4OfdmTrace {
    uint8_t stage{0};
    uint8_t ltf_score{0};      // Fix8c repetition sync quality, 0..100
    uint8_t rate_raw{0xFF};    // parser representation of R1..R4
    uint16_t length{0};        // decoded PSDU length when available
};''',
'''struct M4OfdmTrace {
    uint8_t stage{0};
    uint8_t ltf_score{0};      // Fix8c repetition sync quality, 0..100
    uint8_t rate_raw{0xFF};    // parser representation of R1..R4
    uint16_t length{0};        // decoded PSDU length when available

    // Fix8e post-DATA classification. post_stage is sequential:
    // 1=remaining SERVICE bits descramble to zero, 2=802.11 protocol version 0,
    // 3=management frame, 4=Beacon/Probe Response, 5=SSID IE parsed.
    uint8_t post_stage{0};
    uint8_t frame_type{0xFF};
    uint8_t frame_subtype{0xFF};
    bool dsss_attempted{false};
    bool dsss_success{false};
};''')

replace_once(
    'firmware/common/wifi_aim/wifi_aim_phy.hpp',
'''    bool decode(const IQ8* samples, std::size_t sample_count, M4ApReport& out, M4OfdmTrace* trace = nullptr) {
        if (ofdm_.decode(samples, sample_count, out, trace)) return true;
        return dsss_.decode(samples, sample_count, out);
    }''',
'''    bool decode(const IQ8* samples, std::size_t sample_count, M4ApReport& out, M4OfdmTrace* trace = nullptr) {
        if (ofdm_.decode(samples, sample_count, out, trace)) return true;

        // Fix8e throughput guard: a parity-valid legacy OFDM SIGNAL means this
        // capture is already convincingly OFDM. Running the exhaustive DSSS
        // phase/offset search after that is wasted CPU and can make the M4 miss
        // later DMA blocks. Preserve DSSS fallback for captures that did not
        // reach OFDM parity, including real 1 Mbit/s beacons.
        if (trace && trace->stage >= 4u) return false;
        if (trace) trace->dsss_attempted = true;
        const bool ok = dsss_.decode(samples, sample_count, out);
        if (trace) trace->dsss_success = ok;
        return ok;
    }''')

# ---- OFDM post-DATA classification ----
replace_once(
    'firmware/common/wifi_aim/wifi_aim_phy.cpp',
'''    // IEEE 802.11 descrambler: derive the seven-bit state from the first seven
    // decoded SERVICE bits (which were zero before scrambling).
    unsigned state=0;
    for (unsigned i=0;i<7;++i) if (decoded_[i]) state|=1u<<(6-i);
    bytes_.fill(0);
    bytes_[0]=static_cast<uint8_t>(state);
    const std::size_t max_out_bits=std::min<std::size_t>(data_dec,bytes_.size()*8u);
    for (std::size_t i=7;i<max_out_bits;++i) {
        const unsigned feedback=((state&64u)?1u:0u)^((state&8u)?1u:0u);
        const unsigned bit=feedback^(decoded_[i]&1u);
        bytes_[i/8u]|=static_cast<uint8_t>(bit<<(i%8u));
        state=((state<<1)&0x7e)|feedback;
    }
    const std::size_t produced=(max_out_bits/8u>2u)?(max_out_bits/8u-2u):0u;
    const std::size_t prefix_n=std::min<std::size_t>({produced,want_bytes,kMaxPrefixBytes});
    if (prefix_n<36) return false;
    M4ApReport candidate{};
    if (!parse_prefix_fixed(bytes_.data()+2,prefix_n,candidate)) return false;
    if (trace) trace->stage = 8;''',
'''    // IEEE 802.11 descrambler: derive the seven-bit state from the first seven
    // decoded SERVICE bits (which were zero before scrambling).
    unsigned state=0;
    for (unsigned i=0;i<7;++i) if (decoded_[i]) state|=1u<<(6-i);
    bytes_.fill(0);
    bytes_[0]=static_cast<uint8_t>(state);
    const std::size_t max_out_bits=std::min<std::size_t>(data_dec,bytes_.size()*8u);
    bool service_tail_zero = true;
    for (std::size_t i=7;i<max_out_bits;++i) {
        const unsigned feedback=((state&64u)?1u:0u)^((state&8u)?1u:0u);
        const unsigned bit=feedback^(decoded_[i]&1u);
        if (i < 16u && bit) service_tail_zero = false;
        bytes_[i/8u]|=static_cast<uint8_t>(bit<<(i%8u));
        state=((state<<1)&0x7e)|feedback;
    }
    if (!service_tail_zero) return false;
    if (trace) trace->post_stage = 1;

    const std::size_t produced=(max_out_bits/8u>2u)?(max_out_bits/8u-2u):0u;
    const std::size_t prefix_n=std::min<std::size_t>({produced,want_bytes,kMaxPrefixBytes});
    if (prefix_n<36) return false;

    const uint8_t* frame = bytes_.data()+2;
    const uint16_t fc = le16(frame);
    if ((fc & 0x0003u) != 0u) return false;
    if (trace) trace->post_stage = 2;
    const uint8_t frame_type = static_cast<uint8_t>((fc >> 2) & 3u);
    const uint8_t frame_subtype = static_cast<uint8_t>((fc >> 4) & 15u);
    if (trace) {
        trace->frame_type = frame_type;
        trace->frame_subtype = frame_subtype;
    }
    if (frame_type != 0u) return false;
    if (trace) trace->post_stage = 3;
    if (frame_subtype != 8u && frame_subtype != 5u) return false;
    if (trace) trace->post_stage = 4;

    M4ApReport candidate{};
    if (!parse_prefix_fixed(frame,prefix_n,candidate)) return false;
    if (trace) {
        trace->post_stage = 5;
        trace->stage = 8;
    }''')

# ---- M4 aggregate counters ----
replace_once(
    'firmware/baseband/proc_wifi_aim.hpp',
'''    uint8_t ofdm_ltf_peak_{0};
    uint8_t ofdm_last_rate_{0xFF};
    uint16_t ofdm_last_length_{0};''',
'''    uint8_t ofdm_ltf_peak_{0};
    uint8_t ofdm_last_rate_{0xFF};
    uint16_t ofdm_last_length_{0};

    // Fix8e post-DATA OFDM and DSSS-path telemetry.
    std::array<uint8_t,5> ofdm_post_hits_{};
    uint8_t ofdm_last_type_{0xFF};
    uint8_t ofdm_last_subtype_{0xFF};
    uint8_t dsss_attempts_{0};
    uint8_t dsss_successes_{0};''')

replace_once(
    'firmware/baseband/proc_wifi_aim.cpp',
'''    ofdm_stage_hits_.fill(0);
    ofdm_ltf_peak_ = 0;
    ofdm_last_rate_ = 0xFFu;
    ofdm_last_length_ = 0;''',
'''    ofdm_stage_hits_.fill(0);
    ofdm_ltf_peak_ = 0;
    ofdm_last_rate_ = 0xFFu;
    ofdm_last_length_ = 0;
    ofdm_post_hits_.fill(0);
    ofdm_last_type_ = 0xFFu;
    ofdm_last_subtype_ = 0xFFu;
    dsss_attempts_ = 0;
    dsss_successes_ = 0;''')

replace_once(
    'firmware/baseband/proc_wifi_aim.cpp',
'''    wire.ssid[10] = static_cast<char>(ofdm_last_length_ & 0xFFu);
    wire.ssid[11] = static_cast<char>((ofdm_last_length_ >> 8) & 0xFFu);''',
'''    wire.ssid[10] = static_cast<char>(ofdm_last_length_ & 0xFFu);
    wire.ssid[11] = static_cast<char>((ofdm_last_length_ >> 8) & 0xFFu);
    for (std::size_t i = 0; i < ofdm_post_hits_.size(); ++i)
        wire.ssid[12 + i] = static_cast<char>(ofdm_post_hits_[i]);
    wire.ssid[17] = static_cast<char>(ofdm_last_type_);
    wire.ssid[18] = static_cast<char>(ofdm_last_subtype_);
    wire.ssid[19] = static_cast<char>(dsss_attempts_);
    wire.ssid[20] = static_cast<char>(dsss_successes_);''')

replace_once(
    'firmware/baseband/proc_wifi_aim.cpp',
'''    if (ofdm_trace.rate_raw != 0xFFu) ofdm_last_rate_ = ofdm_trace.rate_raw;
    if (ofdm_trace.length) ofdm_last_length_ = ofdm_trace.length;
    if (decoded) ++decode_successes_;''',
'''    if (ofdm_trace.rate_raw != 0xFFu) ofdm_last_rate_ = ofdm_trace.rate_raw;
    if (ofdm_trace.length) ofdm_last_length_ = ofdm_trace.length;
    for (uint8_t i = 0; i < ofdm_trace.post_stage && i < ofdm_post_hits_.size(); ++i)
        if (ofdm_post_hits_[i] != 0xFFu) ++ofdm_post_hits_[i];
    if (ofdm_trace.frame_type != 0xFFu) ofdm_last_type_ = ofdm_trace.frame_type;
    if (ofdm_trace.frame_subtype != 0xFFu) ofdm_last_subtype_ = ofdm_trace.frame_subtype;
    if (ofdm_trace.dsss_attempted && dsss_attempts_ != 0xFFu) ++dsss_attempts_;
    if (ofdm_trace.dsss_success && dsss_successes_ != 0xFFu) ++dsss_successes_;
    if (decoded) ++decode_successes_;''')

# ---- UI: preserve AP details after scan + expose new diagnostics ----
replace_once(
    'firmware/application/external/wifi_aim/ui_wifi_aim.cpp',
'''    if (w.flags & 0x80u) {
        // Fix8a reuses otherwise-unused diagnostic BSSID bytes. ssid_len=0xF8
        // distinguishes this from older Fix7b/Fix7c telemetry.
        if (w.ssid_len == 0xF8u || w.ssid_len == 0xF9u) {''',
'''    if (w.flags & 0x80u) {
        // While aiming, diagnostics must never overwrite LIVE/AVG/PEAK/DELTA.
        if (target_set_) return;

        // Fix8a reuses otherwise-unused diagnostic BSSID bytes. ssid_len=0xF8
        // distinguishes this from older Fix7b/Fix7c telemetry.
        if (w.ssid_len == 0xF8u || w.ssid_len == 0xF9u) {''')

replace_once(
    'firmware/application/external/wifi_aim/ui_wifi_aim.cpp',
'''            text_channel.set("SQ " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[8])) +
                             " R " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[9])) +
                             " N " + to_string_dec_uint(n));
        }
        update_done_status();
        return;''',
'''            text_channel.set("SQ " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[8])) +
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
        return;''')

print('Fix8e patch applied successfully')
