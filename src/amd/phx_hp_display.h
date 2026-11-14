/*
 * Copyright 2022 Advanced Micro Devices, Inc.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
 * THE COPYRIGHT HOLDER(S) OR AUTHOR(S) BE LIABLE FOR ANY CLAIM, DAMAGES OR
 * OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
 * ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 * OTHER DEALINGS IN THE SOFTWARE.
 *
 */
/* Captured HP timing, read-only: sequoia-build39-display-timing.json.
 * Clock is nominal, derived from captured totals and the measured 60 Hz mode.
 * No display registers are programmed by this helper. */
#ifndef PHX_HP_DISPLAY_H
#define PHX_HP_DISPLAY_H
#include "phx_hp_memory.h"
#define PHX_HP_DISPLAY_REG_COUNT 14u
struct phx_hp_display_plan {
    uint32_t version, flags, width, height, pitch, refresh_millihz;
    uint32_t htotal, hsync_start, hsync_end, vtotal, vsync_start, vsync_end, sync_polarity, reserved;
    uint64_t aperture_physical, backing_physical, scanout_mc, scanout_offset, scanout_bytes, nominal_pixel_clock_hz;
};
static_assert(sizeof(phx_hp_display_plan)==104,"display plan layout");
static const struct phx_scanout_register phx_hp_display_registers[]={
    {"regOTG0_OTG_H_TOTAL",0x4feau},
    {"regOTG0_OTG_H_BLANK_START_END",0x4febu},
    {"regOTG0_OTG_H_SYNC_A",0x4fecu},
    {"regOTG0_OTG_H_SYNC_A_CNTL",0x4fedu},
    {"regOTG0_OTG_V_TOTAL",0x4fefu},
    {"regOTG0_OTG_V_TOTAL_MIN",0x4ff0u},
    {"regOTG0_OTG_V_TOTAL_MAX",0x4ff1u},
    {"regOTG0_OTG_V_TOTAL_CONTROL",0x4ff3u},
    {"regOTG0_OTG_V_BLANK_START_END",0x4ff6u},
    {"regOTG0_OTG_V_SYNC_A",0x4ff7u},
    {"regOTG0_OTG_V_SYNC_A_CNTL",0x4ff8u},
    {"regOTG0_OTG_CONTROL",0x5001u},
    {"regOTG0_OTG_INTERLACE_CONTROL",0x5004u},
    {"regOTG0_OTG_STATUS_FRAME_COUNT",0x500cu},
};
using PhxDisplayExpected=PhxRegisterExpected;
static const PhxDisplayExpected phx_hp_display_expected[]={
    {0x8d3u,0x7fffu}, // regOTG0_OTG_H_TOTAL
    {0x12408a4u,0x7fff7fffu}, // regOTG0_OTG_H_BLANK_START_END
    {0x200000u,0x7fff7fffu}, // regOTG0_OTG_H_SYNC_A
    {0x0u,0x1u}, // regOTG0_OTG_H_SYNC_A_CNTL
    {0x4d7u,0x7fffu}, // regOTG0_OTG_V_TOTAL
    {0x0u,0x7fffu}, // regOTG0_OTG_V_TOTAL_MIN
    {0x0u,0x7fffu}, // regOTG0_OTG_V_TOTAL_MAX
    {0x0u,0xffffffffu}, // regOTG0_OTG_V_TOTAL_CONTROL
    {0x2504d5u,0x7fff7fffu}, // regOTG0_OTG_V_BLANK_START_END
    {0x60000u,0x7fff7fffu}, // regOTG0_OTG_V_SYNC_A
    {0x1u,0x1u}, // regOTG0_OTG_V_SYNC_A_CNTL
    {0x11201u,0x1u}, // regOTG0_OTG_CONTROL
    {0x0u,0x1u}, // regOTG0_OTG_INTERLACE_CONTROL
    {0x146a0u,0x0u}, // regOTG0_OTG_STATUS_FRAME_COUNT
};
struct PhxDisplayProfile {
    const PhxMemoryProfile *memory;
    const PhxRegisterExpected *registers;
    const phx_scanout_register *addresses;
    uint64_t scanout_offset;
    uint32_t count,width,height,pitch,refresh_millihz,htotal,hsync_start,hsync_end,vtotal,vsync_start,vsync_end,polarity;
};
static const PhxDisplayProfile phx_hp_display_profile={&phx_hp_memory_profile,phx_hp_display_expected,phx_hp_display_registers,0,
    PHX_HP_DISPLAY_REG_COUNT,1920,1200,7680,60000,2260,1968,2000,1240,1203,1209,1};
static inline bool phxDisplayProfilePlan(const phx_memory_layout &memory,const PhxVbiosInfo &firmware,
        const uint32_t *reservation_a,const uint32_t *reservation_b,const uint32_t *timing_a,const uint32_t *timing_b,
        uint64_t width,uint64_t height,uint64_t pitch,uint64_t depth,const PhxDisplayProfile &p,phx_hp_display_plan &out) {
    out={};
    if (!p.memory || !p.registers || !p.addresses || p.count!=PHX_HP_DISPLAY_REG_COUNT || !timing_a || !timing_b ||
        !p.width || p.width>16384 || !p.height || p.height>16384 || p.pitch<p.width*4 ||
        !p.refresh_millihz || p.refresh_millihz>1000000 || p.htotal>32768 || p.vtotal>32768 || p.polarity>3 ||
        !(p.width<p.hsync_start && p.hsync_start<p.hsync_end && p.hsync_end<p.htotal &&
          p.height<p.vsync_start && p.vsync_start<p.vsync_end && p.vsync_end<p.vtotal) ||
        width!=p.width || height!=p.height || pitch!=p.pitch || depth!=32 ||
        !phxMemoryProfileMatches(memory,firmware,reservation_a,reservation_b,PHX_RESERVATION_REG_COUNT,*p.memory)) return false;
    for (unsigned i=0;i<p.count;++i) {
        const auto &e=p.registers[i];
        if (((timing_a[i]^e.value)&e.mask) || ((timing_b[i]^e.value)&e.mask)) return false;
    }
    out.version=1;out.flags=3;
    out.width=p.width;out.height=p.height;out.pitch=p.pitch;out.refresh_millihz=p.refresh_millihz;
    out.htotal=p.htotal;out.hsync_start=p.hsync_start;out.hsync_end=p.hsync_end;
    out.vtotal=p.vtotal;out.vsync_start=p.vsync_start;out.vsync_end=p.vsync_end;out.sync_polarity=p.polarity;
    const uint64_t bytes=(uint64_t)out.pitch*out.height;
    if(p.scanout_offset>memory.cpu_aperture_bytes || bytes>memory.cpu_aperture_bytes-p.scanout_offset ||
       p.scanout_offset>memory.vram_bytes || bytes>memory.vram_bytes-p.scanout_offset ||
       p.scanout_offset>p.memory->console_exclusion || bytes>p.memory->console_exclusion-p.scanout_offset) {out={};return false;}
    out.aperture_physical=memory.cpu_aperture_base+p.scanout_offset;out.backing_physical=memory.physical_base+p.scanout_offset;
    out.scanout_mc=memory.mc_base+p.scanout_offset;out.scanout_offset=p.scanout_offset;out.scanout_bytes=bytes;
    out.nominal_pixel_clock_hz=(uint64_t)out.htotal*out.vtotal*out.refresh_millihz/1000;
    if(out.nominal_pixel_clock_hz>UINT32_MAX){out={};return false;}
    return out.scanout_bytes<=memory.cpu_aperture_bytes && out.scanout_bytes<=p.memory->console_exclusion;
}
static inline bool phxHpDisplayPlan(const phx_memory_layout &memory,const PhxVbiosInfo &firmware,
        const uint32_t *reservation_a,const uint32_t *reservation_b,const uint32_t *timing_a,const uint32_t *timing_b,
        uint64_t width,uint64_t height,uint64_t pitch,uint64_t depth,phx_hp_display_plan &out) {
    return phxDisplayProfilePlan(memory,firmware,reservation_a,reservation_b,timing_a,timing_b,
        width,height,pitch,depth,phx_hp_display_profile,out);
}
#endif
