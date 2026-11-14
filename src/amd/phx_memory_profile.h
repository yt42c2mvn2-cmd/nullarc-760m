/* SPDX-License-Identifier: MIT */
#ifndef PHX_MEMORY_PROFILE_H
#define PHX_MEMORY_PROFILE_H
#include "phx_memory_layout.h"
#include "phx_vbios.h"
struct PhxRegisterExpected { uint32_t value,mask; };
struct PhxReservedRange { uint64_t offset,bytes; };
struct PhxMemoryProfile {
    uint64_t mc_base,physical_base,vram_bytes,aperture_bytes,console_exclusion;
    uint32_t rom_format,rom_content,master_format,master_content,firmware_format,firmware_content,firmware_revision;
    uint32_t usage_format,usage_content,firmware_start_kib;
    uint64_t firmware_usage,driver_usage,extra_firmware;
    const PhxRegisterExpected *registers;
    uint32_t register_count;
    const PhxReservedRange *reserved_ranges;
    uint32_t reserved_count;
};
static inline bool phxMemoryProfileMatches(const phx_memory_layout &m,const PhxVbiosInfo &f,
        const uint32_t *first,const uint32_t *second,uint32_t count,const PhxMemoryProfile &p) {
    if (!phx_memory_layout_valid(&m) || !first || !second || !p.registers || count!=p.register_count || !count ||
        m.mc_base!=p.mc_base || m.physical_base!=p.physical_base || m.vram_bytes!=p.vram_bytes ||
        m.cpu_aperture_bytes!=p.aperture_bytes || !p.console_exclusion || p.console_exclusion>m.cpu_aperture_bytes ||
        f.romFormat!=p.rom_format || f.romContent!=p.rom_content || f.masterFormat!=p.master_format || f.masterContent!=p.master_content ||
        f.firmwareFormat!=p.firmware_format || f.firmwareContent!=p.firmware_content || f.firmwareRevision!=p.firmware_revision ||
        !f.usageDecoded || f.usageFormat!=p.usage_format || f.usageContent!=p.usage_content || f.firmwareStartRawKiB!=p.firmware_start_kib ||
        f.firmwareUsageBytes!=p.firmware_usage || f.driverUsageBytes!=p.driver_usage || !f.extraDecoded || f.extraFirmwareBytes!=p.extra_firmware) return false;
    for (uint32_t i=0;i<count;++i) {
        const auto &r=p.registers[i];
        if ((r.value&~r.mask) || (first[i]&r.mask)!=r.value || (second[i]&r.mask)!=r.value) return false;
    }
    if(p.reserved_count>16 || (p.reserved_count && !p.reserved_ranges))return false;
    uint64_t previous=p.console_exclusion;
    for(uint32_t i=0;i<p.reserved_count;++i) {
        const auto &r=p.reserved_ranges[i];
        if(!r.bytes || r.offset<previous || r.offset>m.vram_bytes || r.bytes>m.vram_bytes-r.offset)return false;
        previous=r.offset+r.bytes;
    }
    return true;
}
template<class Arena> static inline bool phxExcludeProfileReservations(Arena &arena,uint64_t aperture,const PhxMemoryProfile &p) {
    if(!p.console_exclusion || p.console_exclusion>aperture || p.reserved_count>16 ||
        (p.reserved_count && !p.reserved_ranges) || !arena.exclude(0,p.console_exclusion))return false;
    uint64_t previous=p.console_exclusion;
    for(uint32_t i=0;i<p.reserved_count;++i) {
        const auto &r=p.reserved_ranges[i];
        if(!r.bytes || r.offset<previous || r.offset>p.vram_bytes || r.bytes>p.vram_bytes-r.offset)return false;
        previous=r.offset+r.bytes;
        if(r.offset<aperture && !arena.exclude(r.offset,r.bytes<aperture-r.offset?r.bytes:aperture-r.offset))return false;
    }
    return true;
}
#endif
