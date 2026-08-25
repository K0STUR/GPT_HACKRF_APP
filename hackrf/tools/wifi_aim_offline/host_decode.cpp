#include <array>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#define private public
#include "wifi_aim/wifi_aim_phy.hpp"
#undef private

static std::string json_escape(const char* s, std::size_t n) {
    std::ostringstream o;
    for (std::size_t i = 0; i < n; ++i) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        if (c == '"' || c == '\\') o << '\\' << static_cast<char>(c);
        else if (c >= 32 && c < 127) o << static_cast<char>(c);
        else o << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c) << std::dec;
    }
    return o.str();
}

static std::string bits_string(const uint8_t* b, std::size_t n) {
    std::string s; s.reserve(n);
    for (std::size_t i=0;i<n;++i) s.push_back((b[i]&1u)?'1':'0');
    return s;
}

int main(int argc, char** argv) {
    if (argc != 2) { std::cerr << "usage: wifi_aim_host_decode <interleaved_iq8.bin>\n"; return 2; }
    std::ifstream f(argv[1], std::ios::binary);
    if (!f) { std::cerr << "cannot open input\n"; return 2; }
    std::vector<int8_t> raw((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    if (raw.size() < 2 || (raw.size() & 1u)) { std::cerr << "input must contain interleaved signed int8 I,Q pairs\n"; return 2; }
    std::vector<wifiaim::IQ8> iq(raw.size()/2u);
    for (std::size_t i=0;i<iq.size();++i) { iq[i].i=raw[2u*i]; iq[i].q=raw[2u*i+1u]; }

    wifiaim::M4OfdmWifiDecoder decoder;
    wifiaim::M4ApReport ap{};
    wifiaim::M4OfdmTrace tr{};
    const bool ok=decoder.decode(iq.data(),iq.size(),ap,&tr);

    std::size_t ltf_index=0;
    float cfo_r=1.0f,cfo_i=0.0f,ltf_raw_score=0.0f;
    const bool ltf_recheck=decoder.find_ltf(iq.data(),iq.size(),ltf_index,cfo_r,cfo_i,ltf_raw_score);

    std::string signal_bits;
    if (tr.stage>=3u && tr.stage<7u) {
        signal_bits.reserve(24);
        for (unsigned i=0;i<24u;++i) signal_bits.push_back(decoder.decoded_[i]?'1':'0');
    }

    uint8_t hard[48]{};
    uint8_t deint[48]{};
    bool hard_ok=false;
    if (ltf_recheck && ltf_index+208u<=iq.size()) {
        // decoder.decode() has already populated h_ using this same candidate.
        hard_ok=decoder.hard_symbol(iq.data(),ltf_index+144u,ltf_index,cfo_r,cfo_i,0u,1u,hard);
        if (hard_ok) decoder.deinterleave(hard,deint,48u,1u);
    }
    const std::string hard_bits=hard_ok?bits_string(hard,48):std::string{};
    const std::string deint_bits=hard_ok?bits_string(deint,48):std::string{};

    std::ostringstream bssid; bssid<<std::hex<<std::setfill('0');
    for (int i=0;i<6;++i) { if(i)bssid<<':'; bssid<<std::setw(2)<<unsigned(ap.bssid[i]); }

    std::cout
        << "{\"ok\":"<<(ok?"true":"false")
        << ",\"samples\":"<<iq.size()
        << ",\"stage\":"<<unsigned(tr.stage)
        << ",\"ltf_score\":"<<unsigned(tr.ltf_score)
        << ",\"ltf_recheck\":"<<(ltf_recheck?"true":"false")
        << ",\"ltf_index\":"<<ltf_index
        << ",\"cfo_step_r\":"<<cfo_r
        << ",\"cfo_step_i\":"<<cfo_i
        << ",\"signal_hard_bits\":\""<<hard_bits<<"\""
        << ",\"signal_deinterleaved_bits\":\""<<deint_bits<<"\""
        << ",\"signal_bits\":\""<<signal_bits<<"\""
        << ",\"rate_raw\":"<<unsigned(tr.rate_raw)
        << ",\"length\":"<<tr.length
        << ",\"post_stage\":"<<unsigned(tr.post_stage)
        << ",\"service_errors\":"<<unsigned(tr.service_errors)
        << ",\"frame_type\":"<<unsigned(tr.frame_type)
        << ",\"frame_subtype\":"<<unsigned(tr.frame_subtype)
        << ",\"rate_mbps\":"<<unsigned(ap.phy_rate_mbps)
        << ",\"channel\":"<<unsigned(ap.channel)
        << ",\"bssid\":\""<<bssid.str()<<"\""
        << ",\"ssid\":\""<<json_escape(ap.ssid,ap.ssid_len)<<"\"}\n";
    return 0;
}
