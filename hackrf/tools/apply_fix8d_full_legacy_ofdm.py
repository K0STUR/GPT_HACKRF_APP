#!/usr/bin/env python3
from pathlib import Path

root = Path('hackrf/source_expanded/firmware/common/wifi_aim')
hpp = root / 'wifi_aim_phy.hpp'
cpp = root / 'wifi_aim_phy.cpp'

h = hpp.read_text()
c = cpp.read_text()

# Header: max coded bits per OFDM symbol and puncture-mode plumbing.
h = h.replace(
    '    static constexpr std::size_t kMaxCbps = 192;\n',
    '    static constexpr std::size_t kMaxCbps = 288;  // 64-QAM: 48 data subcarriers * 6 bits\n'
)
h = h.replace(
    '    static bool rate_params(unsigned signal_rate_parser_value, unsigned& n_bpsc,\n'
    '                            unsigned& n_cbps, unsigned& n_dbps, uint8_t& rate_mbps);\n'
    '    bool viterbi(const uint8_t* coded, std::size_t coded_count, uint8_t* decoded, std::size_t& decoded_count);\n',
    '    static bool rate_params(unsigned signal_rate_parser_value, unsigned& n_bpsc,\n'
    '                            unsigned& n_cbps, unsigned& n_dbps, uint8_t& rate_mbps,\n'
    '                            unsigned& puncture_mode);\n'
    '    static std::size_t depuncture(const uint8_t* in, std::size_t in_count, unsigned puncture_mode,\n'
    '                                  uint8_t* out, std::size_t out_capacity);\n'
    '    bool viterbi(const uint8_t* coded, std::size_t coded_count, uint8_t* decoded, std::size_t& decoded_count);\n'
)
h = h.replace(
    '// Legacy OFDM 6/12/24 Mbit/s (all rate-1/2 modes: BPSK/QPSK/16-QAM).\n'
    '// These are the three mandatory OFDM basic-rate candidates most useful for\n'
    '// management-frame discovery. 20 Msps only.\n',
    '// Full legacy OFDM 6/9/12/18/24/36/48/54 Mbit/s. Supports BPSK, QPSK,\n'
    '// 16-QAM, 64-QAM and rate-1/2, 2/3, 3/4 punctured convolutional coding.\n'
    '// 20 Msps only.\n'
)

old_guard = '    if (!out_bits || (n_bpsc != 1u && n_bpsc != 2u && n_bpsc != 4u)) return false;'
new_guard = '    if (!out_bits || (n_bpsc != 1u && n_bpsc != 2u && n_bpsc != 4u && n_bpsc != 6u)) return false;'
if old_guard not in c:
    raise SystemExit('hard_symbol guard anchor missing')
c = c.replace(old_guard, new_guard, 1)

old_demod = '''        if (n_bpsc==1u) {
            out_bits[o++]=(re<0.0f)?1u:0u;
        } else if (n_bpsc==2u) {
            // QPSK Gray map used by IEEE legacy OFDM: one sign bit per axis.
            out_bits[o++]=(re<0.0f)?1u:0u;
            out_bits[o++]=(im<0.0f)?1u:0u;
        } else {
            // 16-QAM Gray map. Bit order per subcarrier is I-sign, I-inner,
            // Q-sign, Q-inner (matching the coded-bit grouping before mapping).
            out_bits[o++]=(re<0.0f)?1u:0u;
            out_bits[o++]=((re<0.0f?-re:re)<qam16_inner_threshold)?1u:0u;
            out_bits[o++]=(im<0.0f)?1u:0u;
            out_bits[o++]=((im<0.0f?-im:im)<qam16_inner_threshold)?1u:0u;
        }
'''
new_demod = '''        if (n_bpsc==1u) {
            out_bits[o++]=(re<0.0f)?1u:0u;
        } else if (n_bpsc==2u) {
            // QPSK: one sign bit per axis. The sign convention is inherited
            // from the existing channel-estimate orientation and is already
            // hardware-proven by SIGNAL decoding.
            out_bits[o++]=(re<0.0f)?1u:0u;
            out_bits[o++]=(im<0.0f)?1u:0u;
        } else if (n_bpsc==4u) {
            // 16-QAM Gray map. b0,b1 select I and b2,b3 select Q.
            out_bits[o++]=(re<0.0f)?1u:0u;
            out_bits[o++]=((re<0.0f?-re:re)<qam16_inner_threshold)?1u:0u;
            out_bits[o++]=(im<0.0f)?1u:0u;
            out_bits[o++]=((im<0.0f?-im:im)<qam16_inner_threshold)?1u:0u;
        } else {
            // 64-QAM Gray map. Normalized levels are 1,3,5,7 over sqrt(42).
            // For each axis: sign, inner-half bit, middle-ring bit.
            constexpr float t2 = 0.308606700f;  // 2/sqrt(42)
            constexpr float t4 = 0.617213400f;  // 4/sqrt(42)
            constexpr float t6 = 0.925820100f;  // 6/sqrt(42)
            const float ar = re<0.0f ? -re : re;
            const float ai = im<0.0f ? -im : im;
            out_bits[o++]=(re<0.0f)?1u:0u;
            out_bits[o++]=(ar<t4)?1u:0u;
            out_bits[o++]=(ar>=t2 && ar<t6)?1u:0u;
            out_bits[o++]=(im<0.0f)?1u:0u;
            out_bits[o++]=(ai<t4)?1u:0u;
            out_bits[o++]=(ai>=t2 && ai<t6)?1u:0u;
        }
'''
if old_demod not in c:
    raise SystemExit('hard_symbol demod anchor missing')
c = c.replace(old_demod, new_demod, 1)

start = c.index('bool M4OfdmWifiDecoder::rate_params(')
end = c.index('\nbool M4OfdmWifiDecoder::viterbi(', start)
new_rates = r'''bool M4OfdmWifiDecoder::rate_params(unsigned signal_rate_parser_value, unsigned& n_bpsc,
                                    unsigned& n_cbps, unsigned& n_dbps, uint8_t& rate_mbps,
                                    unsigned& puncture_mode) {
    // Parser values are bit-reversed relative to the familiar SIGNAL RATE
    // constants because decoded_[0] is accumulated as the numeric LSB.
    // puncture_mode: 0=1/2, 1=2/3, 2=3/4.
    switch (signal_rate_parser_value) {
        case 11u: n_bpsc=1; n_cbps=48;  n_dbps=24;  rate_mbps=6;  puncture_mode=0; return true; // 0xD
        case 15u: n_bpsc=1; n_cbps=48;  n_dbps=36;  rate_mbps=9;  puncture_mode=2; return true; // 0xF
        case 10u: n_bpsc=2; n_cbps=96;  n_dbps=48;  rate_mbps=12; puncture_mode=0; return true; // 0x5
        case 14u: n_bpsc=2; n_cbps=96;  n_dbps=72;  rate_mbps=18; puncture_mode=2; return true; // 0x7
        case 9u:  n_bpsc=4; n_cbps=192; n_dbps=96;  rate_mbps=24; puncture_mode=0; return true; // 0x9
        case 13u: n_bpsc=4; n_cbps=192; n_dbps=144; rate_mbps=36; puncture_mode=2; return true; // 0xB
        case 8u:  n_bpsc=6; n_cbps=288; n_dbps=192; rate_mbps=48; puncture_mode=1; return true; // 0x1
        case 12u: n_bpsc=6; n_cbps=288; n_dbps=216; rate_mbps=54; puncture_mode=2; return true; // 0x3
        default: return false;
    }
}

std::size_t M4OfdmWifiDecoder::depuncture(const uint8_t* in, std::size_t in_count,
                                           unsigned puncture_mode, uint8_t* out,
                                           std::size_t out_capacity) {
    if (!in || !out || !in_count) return 0;
    if (puncture_mode == 0u) {
        if (in_count > out_capacity) return 0;
        std::memcpy(out, in, in_count);
        return in_count;
    }

    static constexpr uint8_t p23[4] = {1,1,1,0};
    static constexpr uint8_t p34[6] = {1,1,1,0,0,1};
    const uint8_t* pattern = puncture_mode == 1u ? p23 : p34;
    const std::size_t period = puncture_mode == 1u ? 4u : 6u;

    std::size_t ii = 0, oo = 0, pi = 0;
    // OFDM N_DBPS values align every symbol to a full puncturing period. Keep
    // walking the final zero entries after the last transmitted bit so the
    // mother-code stream handed to Viterbi remains exactly rate-1/2.
    while (ii < in_count || pi != 0u) {
        if (oo >= out_capacity) return 0;
        if (pattern[pi]) {
            if (ii >= in_count) return 0;
            out[oo++] = static_cast<uint8_t>(in[ii++] & 1u);
        } else {
            out[oo++] = 2u;  // erasure: Viterbi assigns zero branch penalty
        }
        pi = (pi + 1u) % period;
    }
    return oo;
}
'''
c = c[:start] + new_rates + c[end:]

old_bm = '''            const uint16_t bm0=static_cast<uint16_t>((parity7(reg0&0155)!=r0)+(parity7(reg0&0117)!=r1));
            const uint16_t bm1=static_cast<uint16_t>((parity7(reg1&0155)!=r0)+(parity7(reg1&0117)!=r1));
'''
new_bm = '''            // Value 2 is a puncturing erasure. It contributes no branch
            // penalty, leaving the surviving transmitted bit(s) to decide.
            const uint16_t bm0=static_cast<uint16_t>(((r0<2u)&&(parity7(reg0&0155)!=r0))+((r1<2u)&&(parity7(reg0&0117)!=r1)));
            const uint16_t bm1=static_cast<uint16_t>(((r0<2u)&&(parity7(reg1&0155)!=r0))+((r1<2u)&&(parity7(reg1&0117)!=r1)));
'''
if old_bm not in c:
    raise SystemExit('viterbi branch metric anchor missing')
c = c.replace(old_bm, new_bm, 1)

old_rate_call = '''    unsigned n_bpsc=0,n_cbps=0,n_dbps=0; uint8_t rate_mbps=0;
    if (!rate_params(rate_parser,n_bpsc,n_cbps,n_dbps,rate_mbps)) return false;
'''
new_rate_call = '''    unsigned n_bpsc=0,n_cbps=0,n_dbps=0,puncture_mode=0; uint8_t rate_mbps=0;
    if (!rate_params(rate_parser,n_bpsc,n_cbps,n_dbps,rate_mbps,puncture_mode)) return false;
'''
if old_rate_call not in c:
    raise SystemExit('rate_params call anchor missing')
c = c.replace(old_rate_call, new_rate_call, 1)

old_loop = '''    std::size_t coded_n=0;
    for (std::size_t si=0;si<symbols && coded_n+n_cbps<=kMaxCodedBits;++si) {
        const std::size_t fft_start=L+224+si*80u;
        if (fft_start+64>count) break;
        if (!hard_symbol(s,fft_start,L,cfo_step_r,cfo_step_i,static_cast<unsigned>(si+1),n_bpsc,rx_bits)) return false;
        deinterleave(rx_bits,de_bits,n_cbps,n_bpsc);
        std::memcpy(coded_.data()+coded_n,de_bits,n_cbps);
        coded_n+=n_cbps;
    }
    std::size_t data_dec=0;
    if (coded_n<static_cast<std::size_t>(n_cbps) || !viterbi(coded_.data(),coded_n,decoded_.data(),data_dec) || data_dec<16+36*8) return false;
'''
new_loop = '''    std::size_t coded_n=0;
    for (std::size_t si=0;si<symbols;++si) {
        const std::size_t fft_start=L+224+si*80u;
        if (fft_start+64>count) break;
        if (!hard_symbol(s,fft_start,L,cfo_step_r,cfo_step_i,static_cast<unsigned>(si+1),n_bpsc,rx_bits)) return false;
        deinterleave(rx_bits,de_bits,n_cbps,n_bpsc);
        const std::size_t added=depuncture(de_bits,n_cbps,puncture_mode,
                                           coded_.data()+coded_n,kMaxCodedBits-coded_n);
        if (!added) return false;
        coded_n+=added;
    }
    std::size_t data_dec=0;
    if (coded_n<static_cast<std::size_t>(2u*n_dbps) || !viterbi(coded_.data(),coded_n,decoded_.data(),data_dec) || data_dec<16+36*8) return false;
'''
if old_loop not in c:
    raise SystemExit('DATA coded loop anchor missing')
c = c.replace(old_loop, new_loop, 1)

hpp.write_text(h)
cpp.write_text(c)
print('Fix8d full legacy OFDM patch applied')
