/* SPDX-License-Identifier: MIT
 * ACPI Appendix B: _DOD type 4 is an internal panel when bit 31 declares
 * the standard ID scheme. _BCL's first two entries are power defaults.
 */
#ifndef PHX_BACKLIGHT_POLICY_H
#define PHX_BACKLIGHT_POLICY_H
#include <stdint.h>
struct PhxBrightnessLevels {
    uint32_t values[256],count,current;
    bool contains(uint32_t v) const { for (uint32_t i=0;i<count;++i) if(values[i]==v)return true;return false; }
    bool decode(const uint32_t *bcl,uint32_t n,uint32_t bqc) {
        count=0;current=0;
        if (!bcl || n<4 || n>258) return false;
        for(uint32_t i=2;i<n;++i) {
            if(bcl[i]>100)return false; // ACPI brightness levels are percentages.
            for(uint32_t j=0;j<count;++j) if(values[j]==bcl[i])return false;
            values[count++]=bcl[i];
        }
        for(uint32_t i=1;i<count;++i) { auto v=values[i];uint32_t j=i;while(j && values[j-1]>v){values[j]=values[j-1];--j;}values[j]=v; }
        if(!contains(bcl[0]) || !contains(bcl[1]) || !contains(bqc))return false;
        // Never turn a lit panel completely off for a slider request.
        if(values[0]==0){for(uint32_t i=1;i<count;++i)values[i-1]=values[i];--count;}
        if(count<2 || !contains(bqc))return false; // index-valued/ambiguous BQC is unsupported.
        for(uint32_t i=0;i<count;++i)if(values[i]==bqc)current=i;
        return true;
    }
    uint32_t step(uint32_t from,uint32_t to) const {
        if(from>=count || to>=count)return from;
        const uint32_t stride=(count+11)/12;
        return from<to ? (to-from>stride?from+stride:to) : (from-to>stride?from-stride:to);
    }
};
static inline bool phxAcpiInternalPanel(uint64_t dod,uint64_t adr) {
    if(dod>0xffffffffull || adr>0xffff || (dod&0xffff)!=adr)return false;
    if(dod&0x80000000u)return ((dod>>8)&15)==4;
    // ACPI's legacy LCD ID; do not interpret arbitrary untyped IDs as panels.
    return (dod&0xffe2ffffu)==0x0110u;
}
// A failed or unacknowledged write is terminal; no retry of partial commands.
template<class Transport> static inline bool phxBrightnessTransition(PhxBrightnessLevels &levels,uint32_t target,Transport &t) {
    if(target>=levels.count)return false;
    uint32_t live=0;if(!t.read(live) || !levels.contains(live))return false;
    for(uint32_t i=0;i<levels.count;++i)if(levels.values[i]==live)levels.current=i;
    uint32_t next=levels.step(levels.current,target);
    if(next==levels.current)return true;
    uint32_t ack=0;if(!t.write(levels.values[next]) || !t.read(ack) || ack!=levels.values[next])return false;
    levels.current=next;return true;
}
struct PhxBrightnessRecord { uint32_t version,pci[5],level; uint8_t edid[128]; };
static inline bool phxBrightnessRecordMatches(const PhxBrightnessRecord &r,const uint32_t pci[5],const uint8_t edid[128],const PhxBrightnessLevels &levels) {
    if(r.version!=1 || !levels.contains(r.level))return false;
    for(unsigned i=0;i<5;++i)if(r.pci[i]!=pci[i])return false;
    for(unsigned i=0;i<128;++i)if(r.edid[i]!=edid[i])return false;
    return true;
}
#endif
