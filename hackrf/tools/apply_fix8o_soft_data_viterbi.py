from pathlib import Path

p = Path('hackrf/source_expanded/firmware/common/wifi_aim/wifi_aim_phy.cpp')
s = p.read_text()
start_marker = '    std::size_t coded_n=0;\n'
end_marker = '    if (trace) trace->stage = 7;\n'
start = s.index(start_marker)
end = s.index(end_marker, start) + len(end_marker)

new = r'''    // Fix8o: keep the proven hard-decision SIGNAL path unchanged, but retain
    // quantized constellation confidence for DATA Viterbi. 0 strongly favors
    // coded bit 0, 14 strongly favors bit 1, and 7 is a neutral erasure.
    auto quant_soft = [](float favors_zero) -> uint8_t {
        const float qf = 7.0f - favors_zero * 8.0f;
        int q = static_cast<int>(qf + 0.5f);
        if (q < 0) q = 0;
        if (q > 14) q = 14;
        return static_cast<uint8_t>(q);
    };

    auto soft_symbol = [&](std::size_t fft_start, unsigned pilot_symbol_index,
                           unsigned bits_per_subcarrier, uint8_t* out_soft) -> bool {
        if (!out_soft || (bits_per_subcarrier != 1u && bits_per_subcarrier != 2u &&
                          bits_per_subcarrier != 4u && bits_per_subcarrier != 6u)) return false;
        load_fft(s,fft_start,L,cfo_step_r,cfo_step_i);
        const int pol=kPilotPolarity[pilot_symbol_index & 63u];
        float cr=0.0f, ci=0.0f;
        for (unsigned p=0;p<4;++p) {
            const FCpx z=equalized(kPilotK[p]);
            const float e=static_cast<float>(kPilotBase[p]*pol);
            cr += z.r*e; ci += z.i*e;
        }
        const float cpe_pow=cr*cr+ci*ci;
        if (cpe_pow<1e-8f) return false;
        const float inv_cpe=fast_rsqrt(cpe_pow);
        constexpr float qam16_inner_threshold=0.632455532f;
        constexpr float t2=0.308606700f;
        constexpr float t4=0.617213400f;
        constexpr float t6=0.925820100f;
        unsigned o=0;
        for (unsigned n=0;n<48;++n) {
            const FCpx z=equalized(kDataK[n]);
            const float re=(z.r*cr+z.i*ci)*inv_cpe;
            const float im=(z.i*cr-z.r*ci)*inv_cpe;
            const float ar=re<0.0f ? -re : re;
            const float ai=im<0.0f ? -im : im;
            if (bits_per_subcarrier==1u) {
                out_soft[o++]=quant_soft(re);
            } else if (bits_per_subcarrier==2u) {
                out_soft[o++]=quant_soft(re);
                out_soft[o++]=quant_soft(im);
            } else if (bits_per_subcarrier==4u) {
                out_soft[o++]=quant_soft(re);
                out_soft[o++]=quant_soft(ar-qam16_inner_threshold);
                out_soft[o++]=quant_soft(im);
                out_soft[o++]=quant_soft(ai-qam16_inner_threshold);
            } else {
                auto bit2_soft = [&](float a) -> uint8_t {
                    float d=0.0f;
                    if (a<t2) d=t2-a;
                    else if (a<t6) d=-std::min(a-t2,t6-a);
                    else d=a-t6;
                    return quant_soft(d);
                };
                out_soft[o++]=quant_soft(re);
                out_soft[o++]=quant_soft(ar-t4);
                out_soft[o++]=bit2_soft(ar);
                out_soft[o++]=quant_soft(im);
                out_soft[o++]=quant_soft(ai-t4);
                out_soft[o++]=bit2_soft(ai);
            }
        }
        return true;
    };

    auto depuncture_soft = [](const uint8_t* in, std::size_t in_count,
                              unsigned mode, uint8_t* out_soft,
                              std::size_t out_capacity) -> std::size_t {
        if (!in || !out_soft || !in_count) return 0;
        if (mode==0u) {
            if (in_count>out_capacity) return 0;
            std::memcpy(out_soft,in,in_count);
            return in_count;
        }
        static constexpr uint8_t p23[4]={1,1,1,0};
        static constexpr uint8_t p34[6]={1,1,1,0,0,1};
        const uint8_t* pattern=mode==1u ? p23 : p34;
        const std::size_t period=mode==1u ? 4u : 6u;
        std::size_t ii=0,oo=0,pi=0;
        while (ii<in_count || pi!=0u) {
            if (oo>=out_capacity) return 0;
            if (pattern[pi]) {
                if (ii>=in_count) return 0;
                out_soft[oo++]=in[ii++];
            } else {
                out_soft[oo++]=7u;
            }
            pi=(pi+1u)%period;
        }
        return oo;
    };

    auto viterbi_soft = [&](const uint8_t* soft, std::size_t soft_count,
                            uint8_t* decoded, std::size_t& decoded_count) -> bool {
        if (!soft || !decoded || (soft_count&1u)) return false;
        const std::size_t steps=soft_count/2u;
        if (!steps || steps>kMaxDecodedBits) return false;
        constexpr uint16_t INF=30000u;
        uint16_t pm[64],nm[64];
        for (unsigned st=0;st<64;++st) pm[st]=INF;
        pm[0]=0u;
        auto bit_cost=[](uint8_t r,uint8_t expected)->uint16_t {
            return expected ? static_cast<uint16_t>(14u-r) : static_cast<uint16_t>(r);
        };
        for (std::size_t t=0;t<steps;++t) {
            uint64_t decisions=0;
            const uint8_t r0=soft[2u*t],r1=soft[2u*t+1u];
            for (unsigned ns=0;ns<64;++ns) {
                const uint8_t bit=static_cast<uint8_t>(ns&1u);
                const unsigned p0=ns>>1;
                const unsigned p1=p0|32u;
                const uint8_t reg0=static_cast<uint8_t>(((p0<<1)&0x7e)|bit);
                const uint8_t reg1=static_cast<uint8_t>(((p1<<1)&0x7e)|bit);
                const uint16_t bm0=static_cast<uint16_t>(
                    bit_cost(r0,parity7(reg0&0155))+bit_cost(r1,parity7(reg0&0117)));
                const uint16_t bm1=static_cast<uint16_t>(
                    bit_cost(r0,parity7(reg1&0155))+bit_cost(r1,parity7(reg1&0117)));
                const uint16_t m0=static_cast<uint16_t>(pm[p0]+bm0);
                const uint16_t m1=static_cast<uint16_t>(pm[p1]+bm1);
                if (m1<m0) { nm[ns]=m1; decisions|=(uint64_t{1}<<ns); }
                else nm[ns]=m0;
            }
            std::memcpy(pm,nm,sizeof(pm));
            survivor_[t]=decisions;
        }
        unsigned state=0u;
        for (unsigned st=1;st<64;++st) if (pm[st]<pm[state]) state=st;
        for (std::size_t tt=steps;tt-- > 0;) {
            decoded[tt]=static_cast<uint8_t>(state&1u);
            const unsigned hi=static_cast<unsigned>((survivor_[tt]>>state)&1u);
            state=(state>>1)|(hi<<5);
        }
        decoded_count=steps;
        return true;
    };

    std::size_t coded_n=0;
    for (std::size_t si=0;si<symbols;++si) {
        const std::size_t fft_start=L+224+si*80u;
        if (fft_start+64>count) break;
        if (!soft_symbol(fft_start,static_cast<unsigned>(si+1),n_bpsc,rx_bits)) return false;
        deinterleave(rx_bits,de_bits,n_cbps,n_bpsc);
        const std::size_t added=depuncture_soft(de_bits,n_cbps,puncture_mode,
                                                coded_.data()+coded_n,kMaxCodedBits-coded_n);
        if (!added) return false;
        coded_n+=added;
    }
    std::size_t data_dec=0;
    if (coded_n<static_cast<std::size_t>(2u*n_dbps) ||
        !viterbi_soft(coded_.data(),coded_n,decoded_.data(),data_dec) ||
        data_dec<16+36*8) return false;
    if (trace) trace->stage = 7;
'''

s = s[:start] + new + s[end:]
p.write_text(s)
print('Fix8o soft DATA Viterbi applied')
