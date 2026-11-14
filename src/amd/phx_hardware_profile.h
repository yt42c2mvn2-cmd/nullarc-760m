/* SPDX-License-Identifier: MIT
 * Identity selects a reviewed implementation, never establishes GPU readiness.
 * Unknown boards must not inherit the reference board's register/VRAM policy.
 */
#ifndef PHX_HARDWARE_PROFILE_H
#define PHX_HARDWARE_PROFILE_H
#include "phx_hp_760m.h"
#include "phx_hp_display.h"
enum PhxHardwareBackend : uint32_t { PhxDiagnostic = 0, PhxCapturedNative = 1, PhxReferenceNative = 2 };
struct PhxHardwareProfile {
    const char *name,*model;
    uint32_t vendor, device, revision, subvendor, subdevice;
    PhxHardwareBackend backend;
    const phx_topology *topology;
    const PhxMemoryProfile *memory;
    const PhxDisplayProfile *display;
};
// Configuration headers define data outside the profile structure.
#include "phx_hardware_registry.inc"
static inline const PhxHardwareProfile *phxFindHardwareProfile(uint32_t vendor,uint32_t device,
        uint32_t revision,uint32_t subvendor,uint32_t subdevice) {
    for (const auto &p : phx_hardware_profiles)
        if (p.vendor==vendor && p.device==device && p.revision==revision &&
            p.subvendor==subvendor && p.subdevice==subdevice) return &p;
    return nullptr;
}
static inline bool phxProfileCanInitialize(const PhxHardwareProfile *p) {
    return p && (p->backend==PhxReferenceNative ||
        (p->backend==PhxCapturedNative && phx_topology_valid(p->topology) && p->memory && p->display &&
         phx_topology_matches(p->topology,p->vendor,p->device,p->revision,p->subvendor,p->subdevice) &&
         p->display->memory==p->memory && p->display->addresses &&
         p->display->count==PHX_HP_DISPLAY_REG_COUNT && p->memory->registers &&
         p->memory->register_count==PHX_RESERVATION_REG_COUNT));
}
#endif
