from pathlib import Path


def rep(path: str, old: str, new: str, count: int = 1):
    p = Path(path)
    s = p.read_text()
    if s.count(old) < count:
        raise SystemExit(f"anchor missing in {path}: {old[:120]!r}")
    p.write_text(s.replace(old, new, count))

phyh = "hackrf/source_expanded/firmware/common/wifi_aim/wifi_aim_phy.hpp"
phyc = "hackrf/source_expanded/firmware/common/wifi_aim/wifi_aim_phy.cpp"
proch = "hackrf/source_expanded/firmware/baseband/proc_wifi_aim.hpp"
procc = "hackrf/source_expanded/firmware/baseband/proc_wifi_aim.cpp"
uic = "hackrf/source_expanded/firmware/application/external/wifi_aim/ui_wifi_aim.cpp"

# ---- Decoder trace API ----
rep(phyh,
'''struct M4ApReport {
    uint8_t bssid[6]{};
    char ssid[33]{};
    uint8_t ssid_len{0};
    uint8_t channel{0};
    bool hidden{false};
    int16_t packet_db_x10{-1200};
    uint8_t phy_rate_mbps{0};
};''',
'''struct M4ApReport {
    uint8_t bssid[6]{};
    char ssid[33]{};
    uint8_t ssid_len{0};
    uint8_t channel{0};
    bool hidden{false};
    int16_t packet_db_x10{-1200};
    uint8_t phy_rate_mbps{0};
};

// Fix8b: maximum OFDM decoder stage reached by one capture.
// 1=LTF, 2=SIGNAL hard demod, 3=SIGNAL Viterbi, 4=parity,
// 5=RATE, 6=LENGTH, 7=DATA Viterbi, 8=MAC beacon/probe parser.
struct M4OfdmTrace {
    uint8_t stage{0};
    uint8_t ltf_score{0};      // best ideal-LTF correlation, 0..100
    uint8_t rate_raw{0xFF};    // parser representation of R1..R4
    uint16_t length{0};        // decoded PSDU length when available
};''')

rep(phyh,
'    bool decode(const IQ8* samples, std::size_t sample_count, M4ApReport& out);\n\n   private:\n    struct FCpx',
'    bool decode(const IQ8* samples, std::size_t sample_count, M4ApReport& out, M4OfdmTrace* trace = nullptr);\n\n   private:\n    struct FCpx')

rep(phyh,
'''    bool decode(const IQ8* samples, std::size_t sample_count, M4ApReport& out) {
        if (ofdm_.decode(samples, sample_count, out)) return true;
        return dsss_.decode(samples, sample_count, out);
    }''',
'''    bool decode(const IQ8* samples, std::size_t sample_count, M4ApReport& out, M4OfdmTrace* trace = nullptr) {
        if (ofdm_.decode(samples, sample_count, out, trace)) return true;
        return dsss_.decode(samples, sample_count, out);
    }''')

# Always expose the best ideal-LTF score, including failed threshold tests.
rep(phyc,
'''    if (best < 0.22f) return false;

    // Correlation also peaks at the second L-LTF.''',
'''    score = best;
    if (best < 0.22f) return false;

    // Correlation also peaks at the second L-LTF.''')

rep(phyc,
'bool M4OfdmWifiDecoder::decode(const IQ8* s, std::size_t count, M4ApReport& out) {\n    out={}; out.packet_db_x10=-1200;\n    std::size_t L=0; float cfo_step_r=1.0f, cfo_step_i=0.0f, ltf_score=0.0f;\n    if (!find_ltf(s,count,L,cfo_step_r,cfo_step_i,ltf_score)) return false;\n    if (L+224+64>count) return false;',
'''bool M4OfdmWifiDecoder::decode(const IQ8* s, std::size_t count, M4ApReport& out, M4OfdmTrace* trace) {
    out={}; out.packet_db_x10=-1200;
    if (trace) *trace = {};
    std::size_t L=0; float cfo_step_r=1.0f, cfo_step_i=0.0f, ltf_score=0.0f;
    const bool ltf_ok = find_ltf(s,count,L,cfo_step_r,cfo_step_i,ltf_score);
    if (trace) {
        const float q = std::max(0.0f, std::min(1.0f, ltf_score));
        trace->ltf_score = static_cast<uint8_t>(q * 100.0f + 0.5f);
    }
    if (!ltf_ok) return false;
    if (trace) trace->stage = 1;
    if (L+224+64>count) return false;''')

rep(phyc,
'    if (!hard_symbol(s,L+144,L,cfo_step_r,cfo_step_i,0,1,rx_bits)) return false; // SIGNAL is always BPSK 1/2\n    deinterleave(rx_bits,de_bits,48,1);\n    std::size_t sig_dec=0;\n    if (!viterbi(de_bits,48,decoded_.data(),sig_dec) || sig_dec<24) return false;\n    bool parity=false;\n    for (unsigned i=0;i<17;++i) parity^=(decoded_[i]&1u)!=0;\n    if (parity!=(decoded_[17]!=0)) return false;\n    unsigned rate_parser=0;\n    for (unsigned i=0;i<4;++i) if (decoded_[i]) rate_parser|=1u<<i;',
'''    if (!hard_symbol(s,L+144,L,cfo_step_r,cfo_step_i,0,1,rx_bits)) return false; // SIGNAL is always BPSK 1/2
    if (trace) trace->stage = 2;
    deinterleave(rx_bits,de_bits,48,1);
    std::size_t sig_dec=0;
    if (!viterbi(de_bits,48,decoded_.data(),sig_dec) || sig_dec<24) return false;
    if (trace) trace->stage = 3;
    unsigned rate_parser=0;
    for (unsigned i=0;i<4;++i) if (decoded_[i]) rate_parser|=1u<<i;
    if (trace) trace->rate_raw = static_cast<uint8_t>(rate_parser);
    bool parity=false;
    for (unsigned i=0;i<17;++i) parity^=(decoded_[i]&1u)!=0;
    if (parity!=(decoded_[17]!=0)) return false;
    if (trace) trace->stage = 4;''')

rep(phyc,
'    if (!rate_params(rate_parser,n_bpsc,n_cbps,n_dbps,rate_mbps)) return false;\n    unsigned psdu_len=0;\n    for (unsigned i=5;i<17;++i) if (decoded_[i]) psdu_len|=1u<<(i-5);\n    if (psdu_len<36 || psdu_len>2304) return false;',
'''    if (!rate_params(rate_parser,n_bpsc,n_cbps,n_dbps,rate_mbps)) return false;
    if (trace) trace->stage = 5;
    unsigned psdu_len=0;
    for (unsigned i=5;i<17;++i) if (decoded_[i]) psdu_len|=1u<<(i-5);
    if (trace) trace->length = static_cast<uint16_t>(psdu_len);
    if (psdu_len<36 || psdu_len>2304) return false;
    if (trace) trace->stage = 6;''')

rep(phyc,
'    if (coded_n<static_cast<std::size_t>(n_cbps) || !viterbi(coded_.data(),coded_n,decoded_.data(),data_dec) || data_dec<16+36*8) return false;\n\n    // IEEE 802.11 descrambler:',
'''    if (coded_n<static_cast<std::size_t>(n_cbps) || !viterbi(coded_.data(),coded_n,decoded_.data(),data_dec) || data_dec<16+36*8) return false;
    if (trace) trace->stage = 7;

    // IEEE 802.11 descrambler:''')

rep(phyc,
'    if (!parse_prefix_fixed(bytes_.data()+2,prefix_n,candidate)) return false;\n\n    // Relative packet level',
'''    if (!parse_prefix_fixed(bytes_.data()+2,prefix_n,candidate)) return false;
    if (trace) trace->stage = 8;

    // Relative packet level''')

# ---- M4 cumulative per-scan counters ----
rep(proch,
'''    uint8_t probe_barker_peak_{0};

    wifiaim::M4WifiDecoder decoder_{};''',
'''    uint8_t probe_barker_peak_{0};

    // Fix8b OFDM stage telemetry, reset at the start of every SCAN.
    std::array<uint8_t,8> ofdm_stage_hits_{};
    uint8_t ofdm_ltf_peak_{0};
    uint8_t ofdm_last_rate_{0xFF};
    uint16_t ofdm_last_length_{0};

    wifiaim::M4WifiDecoder decoder_{};''')

rep(procc,
'''    probe_barker_peak_ = 0;
}''',
'''    probe_barker_peak_ = 0;
    ofdm_stage_hits_.fill(0);
    ofdm_ltf_peak_ = 0;
    ofdm_last_rate_ = 0xFFu;
    ofdm_last_length_ = 0;
}''',1)

rep(procc,
'''    wire.ssid_len = 0xF8u;  // Fix8a raw-capture probe marker.
    wire.bssid[0] = probe_o16_hits_;
    wire.bssid[1] = probe_o64_hits_;
    wire.bssid[2] = probe_barker_hits_;
    wire.bssid[3] = probe_o16_peak_;
    wire.bssid[4] = probe_o64_peak_;
    wire.bssid[5] = probe_barker_peak_;''',
'''    wire.ssid_len = 0xF9u;  // Fix8b: Fix8a probe + OFDM internal stages.
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
    wire.ssid[11] = static_cast<char>((ofdm_last_length_ >> 8) & 0xFFu);''')

rep(procc,
'''    wifiaim::M4ApReport ap{};
    const bool decoded = decoder_.decode(capture_.data(), capture_count_, ap);
    if (decoded) ++decode_successes_;''',
'''    wifiaim::M4ApReport ap{};
    wifiaim::M4OfdmTrace ofdm_trace{};
    const bool decoded = decoder_.decode(capture_.data(), capture_count_, ap, &ofdm_trace);
    for (uint8_t i = 0; i < ofdm_trace.stage && i < ofdm_stage_hits_.size(); ++i)
        if (ofdm_stage_hits_[i] != 0xFFu) ++ofdm_stage_hits_[i];
    ofdm_ltf_peak_ = std::max(ofdm_ltf_peak_, ofdm_trace.ltf_score);
    if (ofdm_trace.rate_raw != 0xFFu) ofdm_last_rate_ = ofdm_trace.rate_raw;
    if (ofdm_trace.length) ofdm_last_length_ = ofdm_trace.length;
    if (decoded) ++decode_successes_;''')

# ---- M0 display: preserve Fix8a and add two exact OFDM stage rows ----
rep(uic,
'''        if (w.ssid_len == 0xF8u) {
            text_level.set("HIT 16/64/B " + to_string_dec_uint(w.bssid[0]) + "/" +
                           to_string_dec_uint(w.bssid[1]) + "/" + to_string_dec_uint(w.bssid[2]));
            text_avg.set("Q   16/64/B " + to_string_dec_uint(w.bssid[3]) + "/" +
                         to_string_dec_uint(w.bssid[4]) + "/" + to_string_dec_uint(w.bssid[5]));
            text_peak.set("M4 CH: " + to_string_dec_uint(diag_ack_channel_));
        }''',
'''        if (w.ssid_len == 0xF8u || w.ssid_len == 0xF9u) {
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
            text_channel.set("LQ " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[8])) +
                             " R " + to_string_dec_uint(static_cast<uint8_t>(w.ssid[9])) +
                             " N " + to_string_dec_uint(n));
        }''')

print("Fix8b stage diagnostics patched successfully")
