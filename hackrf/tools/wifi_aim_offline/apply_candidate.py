#!/usr/bin/env python3
from pathlib import Path
import argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    args = ap.parse_args()
    s = Path(args.src).read_text()

    # A/D: replace the inaccurate repetition-only LTF phase selection and the
    # post-selection fine-CFO block with a reference-style chain:
    # STF lag-16 coarse CFO -> CFO-aware LTF template timing -> LTF lag-64 fine CFO.
    old = '''    std::size_t best_d = best_end > kTimingBackoff ? best_end - kTimingBackoff : 0u;\n    if (best_d + 128u > count) return false;\n\n    float pr = 0.0f, pi = 0.0f;\n    for (std::size_t n = 0; n < 64u; ++n) {\n        const float ar = static_cast<float>(s[best_d + n].i);\n        const float ai = static_cast<float>(s[best_d + n].q);\n        const float br = static_cast<float>(s[best_d + 64u + n].i);\n        const float bi = static_cast<float>(s[best_d + 64u + n].q);\n        pr += ar * br + ai * bi;\n        pi += ar * bi - ai * br;\n    }\n\n    const float mag2 = pr * pr + pi * pi;\n    if (mag2 < 1.0e-12f) return false;\n    const float inv_mag = fast_rsqrt(mag2);\n    float root_r = pr * inv_mag, root_i = pi * inv_mag;\n    for (unsigned k = 0; k < 6; ++k) {\n        const float a = std::max(0.0f, (1.0f + root_r) * 0.5f);\n        const float b = std::max(0.0f, (1.0f - root_r) * 0.5f);\n        const float next_r = fast_sqrt(a);\n        float next_i = fast_sqrt(b);\n        if (root_i < 0.0f) next_i = -next_i;\n        root_r = next_r;\n        root_i = next_i;\n    }\n\n    cfo_step_r = root_r;\n    cfo_step_i = -root_i;\n    ltf1 = best_d;\n    score = best_peak;\n    return true;\n'''

    new = '''    // Offline reference candidate: use the strong 16-sample STF repetition\n    // before the LTF for coarse CFO. This gives the standard +/-Fs/32 capture\n    // range (~+/-625 kHz at 20 MS/s) before doing an absolute LTF template match.\n    const std::size_t nominal_d = best_end > kTimingBackoff ? best_end - kTimingBackoff : 0u;\n    const std::size_t stf_lo = best_end > 256u ? best_end - 256u : 0u;\n    std::size_t stf_hi = best_end > 96u ? best_end - 96u : 0u;\n    if (stf_hi < stf_lo) stf_hi = stf_lo;\n    if (count > 80u) stf_hi = std::min<std::size_t>(stf_hi, count - 80u);\n\n    float coarse_q = -1.0f, coarse_cr = 1.0f, coarse_ci = 0.0f;\n    for (std::size_t d=stf_lo; d<=stf_hi; ++d) {\n        float cr=0.0f, ci=0.0f, e0=0.0f, e1=0.0f;\n        for (std::size_t n=0;n<64u;++n) {\n            const float ar=static_cast<float>(s[d+n].i), ai=static_cast<float>(s[d+n].q);\n            const float br=static_cast<float>(s[d+16u+n].i), bi=static_cast<float>(s[d+16u+n].q);\n            cr += ar*br + ai*bi;\n            ci += ar*bi - ai*br;\n            e0 += ar*ar + ai*ai;\n            e1 += br*br + bi*bi;\n        }\n        if (e0<=1.0f || e1<=1.0f) continue;\n        const float q=(cr*cr+ci*ci)/(e0*e1);\n        if (q>coarse_q) { coarse_q=q; coarse_cr=cr; coarse_ci=ci; }\n    }\n    const float coarse_mag2=coarse_cr*coarse_cr+coarse_ci*coarse_ci;\n    if (coarse_mag2<1.0e-12f) return false;\n    const float coarse_inv=fast_rsqrt(coarse_mag2);\n    float coarse_root_r=coarse_cr*coarse_inv, coarse_root_i=coarse_ci*coarse_inv;\n    for (unsigned k=0;k<4u;++k) {\n        const float a=std::max(0.0f,(1.0f+coarse_root_r)*0.5f);\n        const float b=std::max(0.0f,(1.0f-coarse_root_r)*0.5f);\n        const float nr=fast_sqrt(a);\n        float ni=fast_sqrt(b);\n        if (coarse_root_i<0.0f) ni=-ni;\n        coarse_root_r=nr; coarse_root_i=ni;\n    }\n    const float coarse_step_r=coarse_root_r;\n    const float coarse_step_i=-coarse_root_i;\n\n    // Absolute LTF timing. De-rotate each candidate by coarse CFO before\n    // correlating with the known 64-sample LTF. A constant phase per candidate\n    // does not affect the normalized correlation magnitude.\n    const std::size_t local_lo=nominal_d>48u?nominal_d-48u:0u;\n    const std::size_t local_hi=std::min<std::size_t>(nominal_d+48u,count>128u?count-128u:0u);\n    float ref_e=0.0f;\n    for (const auto& r:kLtf) ref_e+=r.r*r.r+r.i*r.i;\n    float ref_best=-1.0f;\n    std::size_t best_d=nominal_d;\n    for (std::size_t d=local_lo;d<=local_hi;++d) {\n        float cr=0.0f,ci=0.0f,ey=0.0f,rr=1.0f,ri=0.0f;\n        for (std::size_t n=0;n<64u;++n) {\n            const float xr=static_cast<float>(s[d+n].i), xi=static_cast<float>(s[d+n].q);\n            const float yr=xr*rr-xi*ri, yi=xr*ri+xi*rr;\n            const float kr=kLtf[n].r, ki=kLtf[n].i;\n            cr += kr*yr + ki*yi;\n            ci += kr*yi - ki*yr;\n            ey += yr*yr + yi*yi;\n            const float nr=rr*coarse_step_r-ri*coarse_step_i;\n            const float ni=rr*coarse_step_i+ri*coarse_step_r;\n            rr=nr; ri=ni;\n        }\n        if (ey<=1.0f) continue;\n        const float q=(cr*cr+ci*ci)/(ref_e*ey);\n        if (q>ref_best) { ref_best=q; best_d=d; }\n    }\n    if (best_d+128u>count) return false;\n\n    // Fine residual CFO from the two repeated LTF symbols after accounting for\n    // the coarse correction across their 64-sample separation.\n    float pr=0.0f,pi=0.0f;\n    for (std::size_t n=0;n<64u;++n) {\n        const float ar=static_cast<float>(s[best_d+n].i), ai=static_cast<float>(s[best_d+n].q);\n        const float br=static_cast<float>(s[best_d+64u+n].i), bi=static_cast<float>(s[best_d+64u+n].q);\n        pr += ar*br + ai*bi;\n        pi += ar*bi - ai*br;\n    }\n    float c64r=1.0f,c64i=0.0f;\n    for (unsigned n=0;n<64u;++n) {\n        const float nr=c64r*coarse_step_r-c64i*coarse_step_i;\n        const float ni=c64r*coarse_step_i+c64i*coarse_step_r;\n        c64r=nr; c64i=ni;\n    }\n    const float rpr=pr*c64r-pi*c64i;\n    const float rpi=pr*c64i+pi*c64r;\n    const float mag2=rpr*rpr+rpi*rpi;\n    if (mag2<1.0e-12f) return false;\n    const float inv_mag=fast_rsqrt(mag2);\n    float root_r=rpr*inv_mag,root_i=rpi*inv_mag;\n    for (unsigned k=0;k<6u;++k) {\n        const float a=std::max(0.0f,(1.0f+root_r)*0.5f);\n        const float b=std::max(0.0f,(1.0f-root_r)*0.5f);\n        const float nr=fast_sqrt(a);\n        float ni=fast_sqrt(b);\n        if (root_i<0.0f) ni=-ni;\n        root_r=nr; root_i=ni;\n    }\n    const float fine_step_r=root_r, fine_step_i=-root_i;\n    cfo_step_r=coarse_step_r*fine_step_r-coarse_step_i*fine_step_i;\n    cfo_step_i=coarse_step_r*fine_step_i+coarse_step_i*fine_step_r;\n    ltf1=best_d;\n    score=ref_best>=0.0f?std::min(1.0f,ref_best):best_peak;\n    return true;\n'''

    if old not in s:
        raise SystemExit('find_ltf candidate anchor not found')
    s = s.replace(old, new, 1)

    # B: IEEE constellation sign convention: sign bit 0 = negative, 1 = positive.
    n_re = s.count('(re<0.0f)?1u:0u')
    n_im = s.count('(im<0.0f)?1u:0u')
    if n_re < 4 or n_im < 3:
        raise SystemExit(f'unexpected sign-demapper anchors re={n_re} im={n_im}')
    s = s.replace('(re<0.0f)?1u:0u', '(re>0.0f)?1u:0u')
    s = s.replace('(im<0.0f)?1u:0u', '(im>0.0f)?1u:0u')

    # C: request only SERVICE + PSDU + six DATA TAIL bits, not 80 extra bits.
    old_budget = 'const std::size_t want_bits=std::min<std::size_t>(kMaxDecodedBits,16u+want_bytes*8u+80u);'
    new_budget = 'const std::size_t want_bits=std::min<std::size_t>(kMaxDecodedBits,16u+want_bytes*8u+6u);'
    if old_budget not in s:
        raise SystemExit('DATA symbol-budget anchor not found')
    s = s.replace(old_budget, new_budget, 1)

    Path(args.dst).write_text(s)


if __name__ == '__main__':
    main()
