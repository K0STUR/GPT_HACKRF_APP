#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace wifiaim {

struct IQ8 { int8_t i{0}; int8_t q{0}; };

struct M4ApReport {
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
};

// Legacy 802.11b, long preamble, 1 Mbit/s DBPSK/DSSS.
class M4LegacyWifiDecoder {
   public:
    static constexpr std::size_t kMaxBits = 2048;
    static constexpr std::size_t kMaxPrefixBytes = 96;
    bool decode(const IQ8* samples, std::size_t sample_count, M4ApReport& out);

   private:
    std::array<uint8_t, kMaxBits> scrambled_{};
    std::array<uint8_t, kMaxBits> plain_{};
    std::array<uint8_t, kMaxPrefixBytes> prefix_{};
};

// Full legacy OFDM 6/9/12/18/24/36/48/54 Mbit/s. Supports BPSK, QPSK,
// 16-QAM, 64-QAM and rate-1/2, 2/3, 3/4 punctured convolutional coding.
// 20 Msps only.
class M4OfdmWifiDecoder {
   public:
    static constexpr std::size_t kMaxPrefixBytes = 96;
    static constexpr std::size_t kMaxDecodedBits = 896;
    static constexpr std::size_t kMaxCodedBits = kMaxDecodedBits * 2;
    static constexpr std::size_t kMaxCbps = 288;  // 64-QAM: 48 data subcarriers * 6 bits
    bool decode(const IQ8* samples, std::size_t sample_count, M4ApReport& out, M4OfdmTrace* trace = nullptr);

   private:
    struct FCpx { float r{0.0f}; float i{0.0f}; };

    std::array<FCpx, 64> fft_{};
    std::array<FCpx, 64> h_{};
    std::array<uint8_t, kMaxCodedBits> coded_{};
    std::array<uint8_t, kMaxDecodedBits> decoded_{};
    std::array<uint64_t, kMaxDecodedBits> survivor_{};
    std::array<uint8_t, kMaxPrefixBytes + 8> bytes_{};

    bool find_ltf(const IQ8* s, std::size_t count, std::size_t& ltf1, float& cfo_step_r, float& cfo_step_i, float& score);
    void load_fft(const IQ8* s, std::size_t start, std::size_t origin, float cfo_step_r, float cfo_step_i);
    void fft64();
    FCpx equalized(int k) const;
    bool hard_symbol(const IQ8* s, std::size_t fft_start, std::size_t origin,
                     float cfo_step_r, float cfo_step_i, unsigned pilot_symbol_index,
                     unsigned n_bpsc, uint8_t* out_bits);
    static void deinterleave(const uint8_t* in, uint8_t* out, unsigned n_cbps, unsigned n_bpsc);
    static bool rate_params(unsigned signal_rate_parser_value, unsigned& n_bpsc,
                            unsigned& n_cbps, unsigned& n_dbps, uint8_t& rate_mbps,
                            unsigned& puncture_mode);
    static std::size_t depuncture(const uint8_t* in, std::size_t in_count, unsigned puncture_mode,
                                  uint8_t* out, std::size_t out_capacity);
    bool viterbi(const uint8_t* coded, std::size_t coded_count, uint8_t* decoded, std::size_t& decoded_count);
};

// Combined decoder used by the app. OFDM is attempted first because its LTF
// gives a cheap, highly selective rejection; DSSS is the fallback.
class M4WifiDecoder {
   public:
    bool decode(const IQ8* samples, std::size_t sample_count, M4ApReport& out, M4OfdmTrace* trace = nullptr) {
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
    }
   private:
    M4OfdmWifiDecoder ofdm_{};
    M4LegacyWifiDecoder dsss_{};
};

} // namespace wifiaim
