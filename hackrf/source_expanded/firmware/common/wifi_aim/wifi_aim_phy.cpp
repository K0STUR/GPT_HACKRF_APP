#include "wifi_aim/wifi_aim_phy.hpp"

#include <algorithm>
#include <cstring>

namespace wifiaim {
namespace {
constexpr int8_t kBarker[11] = {+1, -1, +1, +1, -1, +1, +1, +1, -1, -1, -1};
struct C32 { int32_t i; int32_t q; };

inline uint16_t bits16(const uint8_t* b, std::size_t p, unsigned n) {
    uint16_t v = 0;
    for (unsigned k = 0; k < n; ++k) v |= static_cast<uint16_t>(b[p+k] & 1u) << k;
    return v;
}
inline uint8_t bits8(const uint8_t* b, std::size_t p) { return static_cast<uint8_t>(bits16(b,p,8)); }
inline uint16_t le16(const uint8_t* p) {
    return static_cast<uint16_t>(static_cast<uint16_t>(p[0]) |
                                 static_cast<uint16_t>(static_cast<uint16_t>(p[1]) << 8));
}
inline uint8_t parity7(uint8_t x) {
    x ^= x >> 4; x ^= x >> 2; x ^= x >> 1; return x & 1u;
}

inline float fast_log2_positive(float x) {
    uint32_t bits = 0;
    std::memcpy(&bits, &x, sizeof(bits));
    const int exponent = static_cast<int>((bits >> 23) & 0xffu) - 127;
    bits = (bits & 0x007fffffu) | 0x3f800000u;
    float mantissa = 1.0f;
    std::memcpy(&mantissa, &bits, sizeof(mantissa));
    const float z = (mantissa - 1.0f) / (mantissa + 1.0f);
    const float z2 = z * z;
    const float ln_m = 2.0f * z * (1.0f + z2 * (1.0f / 3.0f + z2 * (1.0f / 5.0f + z2 * (1.0f / 7.0f))));
    return static_cast<float>(exponent) + ln_m * 1.4426950409f;
}

inline int16_t relative_db_x10(float normalized_power) {
    const float x = std::max(normalized_power, 1.0e-12f);
    const float scaled = 30.102999566f * fast_log2_positive(x);
    int32_t rounded = static_cast<int32_t>(scaled >= 0.0f ? scaled + 0.5f : scaled - 0.5f);
    rounded = std::max<int32_t>(-1200, std::min<int32_t>(300, rounded));
    return static_cast<int16_t>(rounded);
}

inline float fast_rsqrt(float x) {
    if (x <= 0.0f) return 0.0f;
    float y=x;
    uint32_t bits=0;
    std::memcpy(&bits,&y,sizeof(bits));
    bits=0x5f375a86u-(bits>>1);
    std::memcpy(&y,&bits,sizeof(y));
    const float half=0.5f*x;
    y=y*(1.5f-half*y*y);
    y=y*(1.5f-half*y*y);
    return y;
}

inline float fast_sqrt(float x) {
    return x <= 0.0f ? 0.0f : x*fast_rsqrt(x);
}

bool parse_prefix_fixed(const uint8_t* f, std::size_t len, M4ApReport& out) {
    if (len < 36) return false;
    const uint16_t fc = le16(f);
    const uint8_t type = static_cast<uint8_t>((fc >> 2) & 3u);
    const uint8_t subtype = static_cast<uint8_t>((fc >> 4) & 15u);
    if (type != 0 || (subtype != 8 && subtype != 5)) return false;
    std::memcpy(out.bssid, f + 16, 6);

    bool ssid_seen = false;
    std::size_t p = 36;
    while (p + 2 <= len) {
        const uint8_t id = f[p];
        const uint8_t n = f[p+1];
        p += 2;
        if (p + n > len) break;
        if (id == 0) {
            ssid_seen = true;
            out.hidden = (n == 0);
            out.ssid_len = static_cast<uint8_t>(std::min<unsigned>(static_cast<unsigned>(n), 32U));
            std::memset(out.ssid, 0, sizeof(out.ssid));
            if (out.ssid_len) std::memcpy(out.ssid, f+p, out.ssid_len);
        } else if (id == 3 && n >= 1) {
            out.channel = f[p];
        }
        p += n;
        if (ssid_seen && out.channel) return true;
    }
    return ssid_seen;
}

struct RefC { float r; float i; };
constexpr RefC kLtf[64] = {
{0.156250000f,0.000000000f},{-0.005121250f,-0.120325133f},{0.039749698f,-0.111157943f},{0.096831885f,0.082797909f},
{0.021111770f,0.027885919f},{0.059823845f,-0.087706760f},{-0.115131215f,-0.055180495f},{-0.038315967f,-0.106170913f},
{0.097541261f,-0.025888348f},{0.053337734f,0.004076326f},{0.000988980f,-0.115004644f},{-0.136804877f,-0.047379811f},
{0.024475852f,-0.058531796f},{0.058668767f,-0.014938999f},{-0.022483206f,0.160657333f},{0.119239089f,-0.004095594f},
{0.062500000f,-0.062500000f},{0.036917942f,0.098344150f},{-0.057206346f,0.039298588f},{-0.131262609f,0.065227229f},
{0.082218322f,0.092356552f},{0.069556847f,0.014121959f},{-0.060310100f,0.081286124f},{-0.056455128f,-0.021803921f},
{-0.035041261f,-0.150888348f},{-0.121887009f,-0.016566218f},{-0.127324360f,-0.020501380f},{0.075073697f,-0.074040419f},
{-0.002805944f,0.053774266f},{-0.091887555f,0.115128709f},{0.091716549f,0.105871660f},{0.012284590f,0.097599554f},
{-0.156250000f,0.000000000f},{0.012284590f,-0.097599554f},{0.091716549f,-0.105871660f},{-0.091887555f,-0.115128709f},
{-0.002805944f,-0.053774266f},{0.075073697f,0.074040419f},{-0.127324360f,0.020501380f},{-0.121887009f,0.016566218f},
{-0.035041261f,0.150888348f},{-0.056455128f,0.021803921f},{-0.060310100f,-0.081286124f},{0.069556847f,-0.014121959f},
{0.082218322f,-0.092356552f},{-0.131262609f,-0.065227229f},{-0.057206346f,-0.039298588f},{0.036917942f,-0.098344150f},
{0.062500000f,0.062500000f},{0.119239089f,0.004095594f},{-0.022483206f,-0.160657333f},{0.058668767f,0.014938999f},
{0.024475852f,0.058531796f},{-0.136804877f,0.047379811f},{0.000988980f,0.115004644f},{0.053337734f,-0.004076326f},
{0.097541261f,0.025888348f},{-0.038315967f,0.106170913f},{-0.115131215f,0.055180495f},{0.059823845f,0.087706760f},
{0.021111770f,-0.027885919f},{0.096831885f,-0.082797909f},{0.039749698f,0.111157943f},{-0.005121250f,0.120325133f}
};

constexpr int8_t kLongBins[64] = {
0,1,-1,-1,1,1,-1,1,-1,1,-1,-1,-1,-1,-1,1,1,-1,-1,1,-1,1,-1,1,1,1,1,0,0,0,0,0,
0,0,0,0,0,0,1,1,-1,-1,1,1,-1,1,-1,1,1,1,1,1,1,-1,-1,1,1,-1,1,-1,1,1,1,1
};

constexpr RefC kTwiddle[32] = {
{1.000000000f,0.000000000f},{0.995184727f,-0.098017140f},{0.980785280f,-0.195090322f},{0.956940336f,-0.290284677f},
{0.923879533f,-0.382683432f},{0.881921264f,-0.471396737f},{0.831469612f,-0.555570233f},{0.773010453f,-0.634393284f},
{0.707106781f,-0.707106781f},{0.634393284f,-0.773010453f},{0.555570233f,-0.831469612f},{0.471396737f,-0.881921264f},
{0.382683432f,-0.923879533f},{0.290284677f,-0.956940336f},{0.195090322f,-0.980785280f},{0.098017140f,-0.995184727f},
{0.000000000f,-1.000000000f},{-0.098017140f,-0.995184727f},{-0.195090322f,-0.980785280f},{-0.290284677f,-0.956940336f},
{-0.382683432f,-0.923879533f},{-0.471396737f,-0.881921264f},{-0.555570233f,-0.831469612f},{-0.634393284f,-0.773010453f},
{-0.707106781f,-0.707106781f},{-0.773010453f,-0.634393284f},{-0.831469612f,-0.555570233f},{-0.881921264f,-0.471396737f},
{-0.923879533f,-0.382683432f},{-0.956940336f,-0.290284677f},{-0.980785280f,-0.195090322f},{-0.995184727f,-0.098017140f}
};

constexpr int8_t kPilotPolarity[64] = {
1,1,1,1,-1,-1,-1,1,-1,-1,-1,-1,1,1,-1,1,-1,-1,1,1,-1,1,1,-1,1,1,1,1,1,1,-1,1,
1,1,-1,1,1,-1,-1,1,1,1,-1,1,-1,-1,-1,1,-1,1,-1,-1,1,-1,-1,1,1,1,1,1,-1,-1,1,1
};
constexpr int kDataK[48] = {
-26,-25,-24,-23,-22,-20,-19,-18,-17,-16,-15,-14,-13,-12,-11,-10,-9,-8,-6,-5,-4,-3,-2,-1,
1,2,3,4,5,6,8,9,10,11,12,13,14,15,16,17,18,19,20,22,23,24,25,26
};
constexpr int kPilotK[4] = {-21,-7,7,21};
constexpr int kPilotBase[4] = {1,1,1,-1};

inline int bin_for_k(int k) { return k < 0 ? 64 + k : k; }
}  // namespace

bool M4LegacyWifiDecoder::decode(const IQ8* s, std::size_t count, M4ApReport& out) {
    out = {};
    out.packet_db_x10 = -1200;
    if (!s || count < 5000) return false;
    const std::size_t max_chips = (count * 11u) / 20u;

    for (int phase=0; phase<20; ++phase) {
        for (int symoff=0; symoff<11; ++symoff) {
            C32 prev{0,0};
            bool have_prev=false;
            std::size_t nb=0;
            float esum=0.0f;
            std::size_t chip=static_cast<std::size_t>(symoff);
            while (chip+10<max_chips && nb<kMaxBits) {
                C32 c{0,0};
                bool valid=true;
                for (int k=0;k<11;++k) {
                    const std::size_t ci=chip+static_cast<std::size_t>(k);
                    const std::size_t idx=(ci*20u+static_cast<unsigned>(phase)+5u)/11u;
                    if (idx>=count) { valid=false; break; }
                    c.i += static_cast<int32_t>(s[idx].i)*kBarker[k];
                    c.q += static_cast<int32_t>(s[idx].q)*kBarker[k];
                }
                if (!valid) break;
                if (have_prev) {
                    const int64_t dot=static_cast<int64_t>(c.i)*prev.i+static_cast<int64_t>(c.q)*prev.q;
                    scrambled_[nb++]=(dot<0)?1u:0u;
                    esum += static_cast<float>(c.i)*static_cast<float>(c.i) + static_cast<float>(c.q)*static_cast<float>(c.q);
                }
                prev=c; have_prev=true; chip+=11;
            }
            if (nb<256) continue;
            for (std::size_t n=0;n<nb;++n)
                plain_[n]=(n<7)?0u:static_cast<uint8_t>((scrambled_[n]^scrambled_[n-4]^scrambled_[n-7])&1u);

            for (std::size_t p=64; p+16+48+36*8<nb; ++p) {
                if (bits16(plain_.data(),p,16)!=0xF3A0) continue;
                const std::size_t hdr=p+16;
                if (bits8(plain_.data(),hdr)!=0x0A) continue;
                const uint16_t length_us=bits16(plain_.data(),hdr+16,16);
                if (!length_us || (length_us&7u)) continue;
                const std::size_t expected=length_us/8u;
                if (expected<36) continue;
                const std::size_t payload=hdr+48;
                const std::size_t avail=(nb-payload)/8u;
                const std::size_t nbytes=std::min({expected,avail,kMaxPrefixBytes});
                if (nbytes<36) continue;
                for (std::size_t j=0;j<nbytes;++j) prefix_[j]=bits8(plain_.data(),payload+j*8u);
                M4ApReport candidate{};
                if (!parse_prefix_fixed(prefix_.data(),nbytes,candidate)) continue;
                const float avg=esum/static_cast<float>(std::max<std::size_t>(1,nb));
                const float full=11.0f*127.0f;
                candidate.packet_db_x10=relative_db_x10(avg/(full*full));
                candidate.phy_rate_mbps=1;
                out=candidate;
                return true;
            }
        }
    }
    return false;
}

bool M4OfdmWifiDecoder::find_ltf(const IQ8* s, std::size_t count, std::size_t& ltf1,
                                      float& cfo_step_r, float& cfo_step_i, float& score,
                                      float& stf_score, bool& stf_admitted) {
    stf_score = 0.0f;
    stf_admitted = false;
    if (!s || count < 500) return false;
    // This common decoder is linked into both the M4 image and the stock M0
    // audit image. Keep the M0 .text boundary identical to Fix8t so unrelated
    // stock symbols retain their exact ABI addresses after the sync rewrite.
    __asm__ volatile("nop\n\tnop");
    // Fix8u: hardware captures proved that a 2,048-sample pre-trigger plus a
    // 2,200-sample search only inspected the first 152 samples of the trigger
    // block. Cover the useful trigger geometry without scanning all 20,000.
    constexpr std::size_t kSearchSamples = 5000u;
    constexpr float kStfThreshold = 0.75f;
    constexpr std::size_t kMinStfRun = 24u;
    constexpr float kLtfTemplateThreshold = 0.30f;

    if (count <= 128u) return false;
    const std::size_t limit = std::min<std::size_t>(count - 128u, kSearchSamples);

    // Standard STF admission: require a sustained normalized lag-16
    // correlation before looking for an LTF. Overlapping noise peaks near the
    // pre-trigger boundary no longer admit an unrelated q64 local maximum.
    bool stf_in_run = false;
    std::size_t stf_run_start = 0u, stf_run_end = 0u;
    std::size_t best_stf_start = 0u, best_stf_end = 0u;
    float stf_run_peak = 0.0f, best_stf_peak = 0.0f;
    bool have_stf = false;
    const std::size_t stf_limit = std::min<std::size_t>(limit, count - 80u);
    auto finish_stf_run = [&]() {
        if (stf_in_run && (stf_run_end - stf_run_start + 1u) >= kMinStfRun &&
            stf_run_peak > best_stf_peak) {
            best_stf_start = stf_run_start;
            best_stf_end = stf_run_end;
            best_stf_peak = stf_run_peak;
            have_stf = true;
        }
        stf_in_run = false;
        stf_run_peak = 0.0f;
    };
    for (std::size_t d = 0; d < stf_limit; ++d) {
        float cr = 0.0f, ci = 0.0f, e0 = 0.0f, e16 = 0.0f;
        for (std::size_t n = 0; n < 64u; ++n) {
            const float ar = static_cast<float>(s[d + n].i);
            const float ai = static_cast<float>(s[d + n].q);
            const float br = static_cast<float>(s[d + 16u + n].i);
            const float bi = static_cast<float>(s[d + 16u + n].q);
            cr += ar * br + ai * bi;
            ci += ar * bi - ai * br;
            e0 += ar * ar + ai * ai;
            e16 += br * br + bi * bi;
        }
        float q16 = 0.0f;
        if (e0 > 1.0f && e16 > 1.0f)
            q16 = (cr * cr + ci * ci) / (e0 * e16);
        if (q16 > stf_score) stf_score = q16;
        if (q16 >= kStfThreshold) {
            if (!stf_in_run) {
                stf_in_run = true;
                stf_run_start = d;
                stf_run_peak = q16;
            }
            stf_run_end = d;
            if (q16 > stf_run_peak) stf_run_peak = q16;
        } else {
            finish_stf_run();
        }
    }
    finish_stf_run();
    if (!have_stf) {
        score = 0.0f;
        return false;
    }
    stf_admitted = true;

    const std::size_t ltf_search_lo = std::min<std::size_t>(limit, best_stf_start + 128u);
    const std::size_t ltf_search_hi = std::min<std::size_t>(limit, best_stf_end + 176u);
    if (ltf_search_hi <= ltf_search_lo) return false;

    const std::size_t stf_lo = best_stf_start;
    std::size_t stf_hi = best_stf_end;
    if (count > 80u) stf_hi = std::min<std::size_t>(stf_hi, count - 80u);

    float coarse_q = -1.0f, coarse_cr = 1.0f, coarse_ci = 0.0f;
    for (std::size_t d=stf_lo; d<=stf_hi; ++d) {
        float cr=0.0f, ci=0.0f, e0=0.0f, e1=0.0f;
        for (std::size_t n=0;n<64u;++n) {
            const float ar=static_cast<float>(s[d+n].i), ai=static_cast<float>(s[d+n].q);
            const float br=static_cast<float>(s[d+16u+n].i), bi=static_cast<float>(s[d+16u+n].q);
            cr += ar*br + ai*bi;
            ci += ar*bi - ai*br;
            e0 += ar*ar + ai*ai;
            e1 += br*br + bi*bi;
        }
        if (e0<=1.0f || e1<=1.0f) continue;
        const float q=(cr*cr+ci*ci)/(e0*e1);
        if (q>coarse_q) { coarse_q=q; coarse_cr=cr; coarse_ci=ci; }
    }
    const float coarse_mag2=coarse_cr*coarse_cr+coarse_ci*coarse_ci;
    if (coarse_mag2<1.0e-12f) return false;
    const float coarse_inv=fast_rsqrt(coarse_mag2);
    float coarse_root_r=coarse_cr*coarse_inv, coarse_root_i=coarse_ci*coarse_inv;
    for (unsigned k=0;k<4u;++k) {
        const float a=std::max(0.0f,(1.0f+coarse_root_r)*0.5f);
        const float b=std::max(0.0f,(1.0f-coarse_root_r)*0.5f);
        const float nr=fast_sqrt(a);
        float ni=fast_sqrt(b);
        if (coarse_root_i<0.0f) ni=-ni;
        coarse_root_r=nr; coarse_root_i=ni;
    }
    const float coarse_step_r=coarse_root_r;
    const float coarse_step_i=-coarse_root_i;

    // Absolute LTF timing. De-rotate each candidate by coarse CFO and require
    // both repeated 64-sample long symbols to match the known LTF. Scoring the
    // weaker of the pair prevents LTF2 (followed by SIGNAL) from being selected
    // as LTF1, and supplies an absolute admission threshold rather than merely
    // accepting whichever local candidate happened to be best.
    const std::size_t local_lo=ltf_search_lo;
    const std::size_t local_hi=std::min<std::size_t>(ltf_search_hi,count-128u);
    float ref_e=0.0f;
    for (const auto& r:kLtf) ref_e+=r.r*r.r+r.i*r.i;
    float ref_best=-1.0f;
    std::size_t best_d=local_lo;
    for (std::size_t d=local_lo;d<=local_hi;++d) {
        float cr0=0.0f,ci0=0.0f,ey0=0.0f;
        float cr1=0.0f,ci1=0.0f,ey1=0.0f;
        float rr=1.0f,ri=0.0f;
        for (std::size_t n=0;n<128u;++n) {
            const float xr=static_cast<float>(s[d+n].i), xi=static_cast<float>(s[d+n].q);
            const float yr=xr*rr-xi*ri, yi=xr*ri+xi*rr;
            const auto& ref=kLtf[n&63u];
            if (n<64u) {
                cr0 += ref.r*yr + ref.i*yi;
                ci0 += ref.r*yi - ref.i*yr;
                ey0 += yr*yr + yi*yi;
            } else {
                cr1 += ref.r*yr + ref.i*yi;
                ci1 += ref.r*yi - ref.i*yr;
                ey1 += yr*yr + yi*yi;
            }
            const float nr=rr*coarse_step_r-ri*coarse_step_i;
            const float ni=rr*coarse_step_i+ri*coarse_step_r;
            rr=nr; ri=ni;
        }
        if (ey0<=1.0f || ey1<=1.0f) continue;
        const float q0=(cr0*cr0+ci0*ci0)/(ref_e*ey0);
        const float q1=(cr1*cr1+ci1*ci1)/(ref_e*ey1);
        const float q=std::min(q0,q1);
        if (q>ref_best) { ref_best=q; best_d=d; }
    }
    if (best_d+128u>count || ref_best<kLtfTemplateThreshold) {
        score=std::max(0.0f,ref_best);
        return false;
    }

    // Fine residual CFO from the two repeated LTF symbols after accounting for
    // the coarse correction across their 64-sample separation.
    float pr=0.0f,pi=0.0f;
    for (std::size_t n=0;n<64u;++n) {
        const float ar=static_cast<float>(s[best_d+n].i), ai=static_cast<float>(s[best_d+n].q);
        const float br=static_cast<float>(s[best_d+64u+n].i), bi=static_cast<float>(s[best_d+64u+n].q);
        pr += ar*br + ai*bi;
        pi += ar*bi - ai*br;
    }
    float c64r=1.0f,c64i=0.0f;
    for (unsigned n=0;n<64u;++n) {
        const float nr=c64r*coarse_step_r-c64i*coarse_step_i;
        const float ni=c64r*coarse_step_i+c64i*coarse_step_r;
        c64r=nr; c64i=ni;
    }
    const float rpr=pr*c64r-pi*c64i;
    const float rpi=pr*c64i+pi*c64r;
    const float mag2=rpr*rpr+rpi*rpi;
    if (mag2<1.0e-12f) return false;
    const float inv_mag=fast_rsqrt(mag2);
    float root_r=rpr*inv_mag,root_i=rpi*inv_mag;
    for (unsigned k=0;k<6u;++k) {
        const float a=std::max(0.0f,(1.0f+root_r)*0.5f);
        const float b=std::max(0.0f,(1.0f-root_r)*0.5f);
        const float nr=fast_sqrt(a);
        float ni=fast_sqrt(b);
        if (root_i<0.0f) ni=-ni;
        root_r=nr; root_i=ni;
    }
    const float fine_step_r=root_r, fine_step_i=-root_i;
    cfo_step_r=coarse_step_r*fine_step_r-coarse_step_i*fine_step_i;
    cfo_step_i=coarse_step_r*fine_step_i+coarse_step_i*fine_step_r;
    ltf1=best_d;
    score=std::min(1.0f,ref_best);
    return true;
}

void M4OfdmWifiDecoder::load_fft(const IQ8* s, std::size_t start, std::size_t origin,
                                 float cfo_step_r, float cfo_step_i) {
    uint32_t delta=static_cast<uint32_t>(start-origin);
    float rr=1.0f, ri=0.0f;
    float br=cfo_step_r, bi=cfo_step_i;
    while (delta) {
        if (delta&1u) {
            const float nr=rr*br-ri*bi;
            const float ni=rr*bi+ri*br;
            rr=nr; ri=ni;
        }
        const float nr=br*br-bi*bi;
        const float ni=2.0f*br*bi;
        br=nr; bi=ni;
        delta>>=1;
    }
    for (std::size_t n=0;n<64;++n) {
        const float xr=s[start+n].i, xi=s[start+n].q;
        fft_[n].r=xr*rr-xi*ri;
        fft_[n].i=xr*ri+xi*rr;
        const float nr=rr*cfo_step_r-ri*cfo_step_i;
        const float ni=rr*cfo_step_i+ri*cfo_step_r;
        rr=nr; ri=ni;
    }
    fft64();
}

void M4OfdmWifiDecoder::fft64() {
    for (unsigned i=1,j=0;i<64;++i) {
        unsigned bit=32;
        for (; j&bit; bit>>=1) j^=bit;
        j^=bit;
        if (i<j) std::swap(fft_[i],fft_[j]);
    }
    for (unsigned len=2;len<=64;len<<=1) {
        const unsigned half=len>>1;
        const unsigned step=64/len;
        for (unsigned base=0;base<64;base+=len) {
            for (unsigned j=0;j<half;++j) {
                const auto w=kTwiddle[j*step];
                const FCpx b=fft_[base+j+half];
                const FCpx v{b.r*w.r-b.i*w.i,b.r*w.i+b.i*w.r};
                const FCpx u=fft_[base+j];
                fft_[base+j]={u.r+v.r,u.i+v.i};
                fft_[base+j+half]={u.r-v.r,u.i-v.i};
            }
        }
    }
}

M4OfdmWifiDecoder::FCpx M4OfdmWifiDecoder::equalized(int k) const {
    const int b=bin_for_k(k);
    const auto ub = static_cast<std::size_t>(b);
    const FCpx y=fft_[ub], h=h_[ub];
    const float den=h.r*h.r+h.i*h.i;
    if (den<1e-6f) return {};
    return {(y.r*h.r+y.i*h.i)/den,(y.i*h.r-y.r*h.i)/den};
}

bool M4OfdmWifiDecoder::hard_symbol(const IQ8* s, std::size_t fft_start, std::size_t origin,
                                     float cfo_step_r, float cfo_step_i, unsigned pilot_symbol_index,
                                     unsigned n_bpsc, uint8_t* out_bits) {
    if (!out_bits || (n_bpsc != 1u && n_bpsc != 2u && n_bpsc != 4u && n_bpsc != 6u)) return false;
    load_fft(s,fft_start,origin,cfo_step_r,cfo_step_i);
    const int pol=kPilotPolarity[pilot_symbol_index & 63u];
    float cr=0.0f, ci=0.0f;
    for (unsigned p=0;p<4;++p) {
        FCpx z=equalized(kPilotK[p]);
        const float e=static_cast<float>(kPilotBase[p]*pol);
        cr += z.r*e; ci += z.i*e;
    }
    const float cpe_pow=cr*cr+ci*ci;
    if (cpe_pow<1e-8f) return false;
    const float inv_cpe=fast_rsqrt(cpe_pow);
    constexpr float qam16_inner_threshold=0.632455532f;
    unsigned o=0;
    for (unsigned n=0;n<48;++n) {
        const FCpx z=equalized(kDataK[n]);
        const float re=(z.r*cr+z.i*ci)*inv_cpe;
        const float im=(z.i*cr-z.r*ci)*inv_cpe;
        if (n_bpsc==1u) {
            out_bits[o++]=(re>0.0f)?1u:0u;
        } else if (n_bpsc==2u) {
            out_bits[o++]=(re>0.0f)?1u:0u;
            out_bits[o++]=(im>0.0f)?1u:0u;
        } else if (n_bpsc==4u) {
            out_bits[o++]=(re>0.0f)?1u:0u;
            out_bits[o++]=((re<0.0f?-re:re)<qam16_inner_threshold)?1u:0u;
            out_bits[o++]=(im>0.0f)?1u:0u;
            out_bits[o++]=((im<0.0f?-im:im)<qam16_inner_threshold)?1u:0u;
        } else {
            constexpr float t2 = 0.308606700f;
            constexpr float t4 = 0.617213400f;
            constexpr float t6 = 0.925820100f;
            const float ar = re<0.0f ? -re : re;
            const float ai = im<0.0f ? -im : im;
            out_bits[o++]=(re>0.0f)?1u:0u;
            out_bits[o++]=(ar<t4)?1u:0u;
            out_bits[o++]=(ar>=t2 && ar<t6)?1u:0u;
            out_bits[o++]=(im>0.0f)?1u:0u;
            out_bits[o++]=(ai<t4)?1u:0u;
            out_bits[o++]=(ai>=t2 && ai<t6)?1u:0u;
        }
    }
    return true;
}

void M4OfdmWifiDecoder::deinterleave(const uint8_t* in, uint8_t* out, unsigned n_cbps, unsigned n_bpsc) {
    if (!in || !out || !n_cbps) return;
    const unsigned s=std::max(n_bpsc/2u,1u);
    for (unsigned k=0;k<n_cbps;++k) {
        const unsigned first=s*(k/s)+((k+(16u*k)/n_cbps)%s);
        const unsigned second=16u*first-(n_cbps-1u)*((16u*first)/n_cbps);
        out[second]=in[k];
    }
}

bool M4OfdmWifiDecoder::rate_params(unsigned signal_rate_parser_value, unsigned& n_bpsc,
                                    unsigned& n_cbps, unsigned& n_dbps, uint8_t& rate_mbps,
                                    unsigned& puncture_mode) {
    switch (signal_rate_parser_value) {
        case 11u: n_bpsc=1; n_cbps=48;  n_dbps=24;  rate_mbps=6;  puncture_mode=0; return true;
        case 15u: n_bpsc=1; n_cbps=48;  n_dbps=36;  rate_mbps=9;  puncture_mode=2; return true;
        case 10u: n_bpsc=2; n_cbps=96;  n_dbps=48;  rate_mbps=12; puncture_mode=0; return true;
        case 14u: n_bpsc=2; n_cbps=96;  n_dbps=72;  rate_mbps=18; puncture_mode=2; return true;
        case 9u:  n_bpsc=4; n_cbps=192; n_dbps=96;  rate_mbps=24; puncture_mode=0; return true;
        case 13u: n_bpsc=4; n_cbps=192; n_dbps=144; rate_mbps=36; puncture_mode=2; return true;
        case 8u:  n_bpsc=6; n_cbps=288; n_dbps=192; rate_mbps=48; puncture_mode=1; return true;
        case 12u: n_bpsc=6; n_cbps=288; n_dbps=216; rate_mbps=54; puncture_mode=2; return true;
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
    while (ii < in_count || pi != 0u) {
        if (oo >= out_capacity) return 0;
        if (pattern[pi]) {
            if (ii >= in_count) return 0;
            out[oo++] = static_cast<uint8_t>(in[ii++] & 1u);
        } else {
            out[oo++] = 2u;
        }
        pi = (pi + 1u) % period;
    }
    return oo;
}

bool M4OfdmWifiDecoder::viterbi(const uint8_t* coded, std::size_t coded_count,
                                 uint8_t* decoded, std::size_t& decoded_count) {
    if (!coded || !decoded || (coded_count&1u)) return false;
    const std::size_t steps=coded_count/2u;
    if (!steps || steps>kMaxDecodedBits) return false;
    constexpr uint16_t INF=30000;
    uint16_t pm[64], nm[64];
    for (unsigned s=0;s<64;++s) pm[s]=INF;
    pm[0]=0;
    for (std::size_t t=0;t<steps;++t) {
        uint64_t decisions=0;
        const uint8_t r0=coded[2*t], r1=coded[2*t+1];
        for (unsigned ns=0;ns<64;++ns) {
            const uint8_t bit=ns&1u;
            const unsigned p0=ns>>1;
            const unsigned p1=p0|32u;
            const uint8_t reg0=static_cast<uint8_t>(((p0<<1)&0x7e)|bit);
            const uint8_t reg1=static_cast<uint8_t>(((p1<<1)&0x7e)|bit);
            const uint16_t bm0=static_cast<uint16_t>(((r0<2u)&&(parity7(reg0&0155)!=r0))+((r1<2u)&&(parity7(reg0&0117)!=r1)));
            const uint16_t bm1=static_cast<uint16_t>(((r0<2u)&&(parity7(reg1&0155)!=r0))+((r1<2u)&&(parity7(reg1&0117)!=r1)));
            const uint16_t m0=static_cast<uint16_t>(pm[p0]+bm0);
            const uint16_t m1=static_cast<uint16_t>(pm[p1]+bm1);
            if (m1<m0) { nm[ns]=m1; decisions|=(uint64_t{1}<<ns); }
            else nm[ns]=m0;
        }
        std::memcpy(pm,nm,sizeof(pm));
        survivor_[t]=decisions;
    }
    // Fix8j: SIGNAL is a 24-bit terminated convolutional block. Its six TAIL
    // zeros guarantee encoder state 0 at the end, so traceback must start at
    // state 0. Prefix DATA decoding is intentionally left unconstrained.
    unsigned state=0;
    if (steps != 24u) {
        for (unsigned s=1;s<64;++s) if (pm[s]<pm[state]) state=s;
    }
    for (std::size_t tt=steps;tt-- > 0;) {
        decoded[tt]=static_cast<uint8_t>(state&1u);
        const unsigned hi=static_cast<unsigned>((survivor_[tt]>>state)&1u);
        state=(state>>1)|(hi<<5);
    }
    decoded_count=steps;
    return true;
}

bool M4OfdmWifiDecoder::decode(const IQ8* s, std::size_t count, M4ApReport& out, M4OfdmTrace* trace) {
    out={}; out.packet_db_x10=-1200;
    if (trace) *trace = {};
    std::size_t L=0; float cfo_step_r=1.0f, cfo_step_i=0.0f, ltf_score=0.0f;
    float stf_score=0.0f; bool stf_admitted=false;
    const bool ltf_ok = find_ltf(s,count,L,cfo_step_r,cfo_step_i,ltf_score,stf_score,stf_admitted);
    if (trace) {
        const float qs = std::max(0.0f, std::min(1.0f, stf_score));
        trace->stf_score = static_cast<uint8_t>(qs * 100.0f + 0.5f);
        trace->stf_admitted = stf_admitted;
        const float q = std::max(0.0f, std::min(1.0f, ltf_score));
        trace->ltf_score = static_cast<uint8_t>(q * 100.0f + 0.5f);
        trace->ltf_position = static_cast<uint16_t>(std::min<std::size_t>(L, 0xFFFFu));
        // The decoder's complex step de-rotates the received signal, hence
        // CFO has the opposite sign. At the 20 MS/s input and the STF's
        // +/-Fs/32 acquisition range, |imag/real| < 0.2. The cubic atan
        // approximation is accurate to better than about 250 Hz across that
        // range and avoids adding libm code to the constrained M4 image.
        if (cfo_step_r > 0.0f) {
            const float x = cfo_step_i / cfo_step_r;
            const float phase = x - (x * x * x) / 3.0f;
            trace->cfo_hz = static_cast<int32_t>(-phase * 3183098.862f);
        }
    }
    if (!ltf_ok) return false;
    if (trace) trace->stage = 1;
    if (L+224+64>count) return false;

    load_fft(s,L,L,cfo_step_r,cfo_step_i);
    for (unsigned b=0;b<64;++b) h_[b]=fft_[b];
    load_fft(s,L+64,L,cfo_step_r,cfo_step_i);
    for (unsigned b=0;b<64;++b) {
        if (!kLongBins[b]) { h_[b]={}; continue; }
        const float sign=static_cast<float>(kLongBins[b]);
        h_[b].r=(h_[b].r+fft_[b].r)*0.5f*sign;
        h_[b].i=(h_[b].i+fft_[b].i)*0.5f*sign;
    }

    uint8_t rx_bits[kMaxCbps]{};
    uint8_t de_bits[kMaxCbps]{};
    if (!hard_symbol(s,L+144,L,cfo_step_r,cfo_step_i,0,1,rx_bits)) return false;
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
    if (trace) trace->stage = 4;
    if (decoded_[4] != 0u) return false;
    for (unsigned i=18;i<24;++i) if (decoded_[i] != 0u) return false;

    unsigned n_bpsc=0,n_cbps=0,n_dbps=0,puncture_mode=0; uint8_t rate_mbps=0;
    if (!rate_params(rate_parser,n_bpsc,n_cbps,n_dbps,rate_mbps,puncture_mode)) return false;
    if (trace) trace->stage = 5;
    unsigned psdu_len=0;
    for (unsigned i=5;i<17;++i) if (decoded_[i]) psdu_len|=1u<<(i-5);
    if (trace) trace->length = static_cast<uint16_t>(psdu_len);
    if (psdu_len<36 || psdu_len>2304) return false;
    if (trace) trace->stage = 6;

    const std::size_t want_bytes=std::min<std::size_t>(psdu_len,kMaxPrefixBytes);
    const std::size_t want_bits=std::min<std::size_t>(kMaxDecodedBits,16u+want_bytes*8u+6u);
    std::size_t symbols=(want_bits+n_dbps-1u)/n_dbps;
    const std::size_t available_symbols=(count>(L+224+64)) ? 1u+(count-(L+224+64))/80u : 0u;
    symbols=std::min(symbols,available_symbols);
    if (!symbols) return false;

    std::size_t coded_n=0;
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
    if (trace) trace->stage = 7;

    // Fix8p: exact nearest-codeword search across all 127 legal non-zero
    // scrambler sequences. Unlike Fix8n's radius-1 fast path, FC now reports
    // the true Hamming distance across all 16 known-zero SERVICE bits.
    // Distance <=2 is admitted experimentally; existing MAC structure checks
    // remain mandatory before an AP can be reported.
    uint8_t best_state=0u, service_errors=0xFFu;
    for (unsigned candidate=1u;candidate<128u;++candidate) {
        uint8_t errors=0u;
        for (unsigned i=0u;i<7u;++i)
            errors+=static_cast<uint8_t>((decoded_[i]&1u)!=((candidate>>(6u-i))&1u));
        unsigned st=candidate;
        for (unsigned i=7u;i<16u;++i) {
            const unsigned feedback=((st>>6)^(st>>3))&1u;
            errors+=static_cast<uint8_t>((decoded_[i]&1u)!=feedback);
            st=((st<<1)&0x7eu)|feedback;
        }
        if (errors<service_errors) {
            service_errors=errors;
            best_state=static_cast<uint8_t>(candidate);
        }
    }
    if (trace) trace->service_errors=service_errors;
    if (!best_state || service_errors>2u) return false;
    unsigned state=best_state;
    for (unsigned i=7u;i<16u;++i) {
        const unsigned feedback=((state>>6)^(state>>3))&1u;
        state=((state<<1)&0x7eu)|feedback;
    }
    bytes_.fill(0);
    const std::size_t max_out_bits=std::min<std::size_t>(data_dec,bytes_.size()*8u);
    for (std::size_t i=16u;i<max_out_bits;++i) {
        const unsigned feedback=((state>>6)^(state>>3))&1u;
        const unsigned bit=feedback^(decoded_[i]&1u);
        bytes_[i/8u]|=static_cast<uint8_t>(bit<<(i%8u));
        state=((state<<1)&0x7eu)|feedback;
    }
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
    }

    float e=0.0f;
    for (std::size_t n=0;n<128 && L+n<count;++n) {
        const float xr=s[L+n].i, xi=s[L+n].q;
        e+=xr*xr+xi*xi;
    }
    const float avg=e/128.0f;
    candidate.packet_db_x10=relative_db_x10(avg/(127.0f*127.0f));
    candidate.phy_rate_mbps=rate_mbps;
    out=candidate;
    return true;
}

}  // namespace wifiaim
