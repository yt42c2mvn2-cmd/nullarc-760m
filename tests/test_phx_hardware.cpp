#include "amd/phx_hardware_profile.h"
#include "amd/phx_backlight_policy.h"
#include "amd/phx_vram_arena.h"
#include <cassert>
#include <initializer_list>
#include <cstdio>
struct Transport {
    uint32_t value=50,reads=0,writes=0;bool readOK=true,writeOK=true,ack=true;
    bool read(uint32_t &v){++reads;v=value;return readOK;}
    bool write(uint32_t v){++writes;if(ack)value=v;return writeOK;}
};
int main(){
    auto *hp=phxFindHardwareProfile(0x1002,0x1900,0xca,0x103c,0x8c6a);
    assert(phxProfileCanInitialize(hp) && hp->topology->cu_active_number==8);
    assert(hp->memory==&phx_hp_memory_profile && hp->display->width==1920);
    assert(phxProfileCanInitialize(phxFindHardwareProfile(0x1002,0x1900,0xba,0x8001,0x2014)));
    // Synthetic Dell, ASUS, Lenovo and unknown HP subsystems: identity is not capability.
    for(auto maker:{0x1028,0x1043,0x17aa,0x103c,0xffff})
        assert(!phxProfileCanInitialize(phxFindHardwareProfile(0x1002,0x1900,0xca,maker,0x1234)));
    assert(!phxFindHardwareProfile(0x1002,0x1900,0xcb,0x103c,0x8c6a));
    assert(!phxFindHardwareProfile(0x1002,0x731f,0xca,0x103c,0x8c6a));
    assert(!phxFindHardwareProfile(0x10de,0x1900,0xca,0x103c,0x8c6a));
    PhxHardwareProfile captured=*hp;captured.topology=nullptr;assert(!phxProfileCanInitialize(&captured));
    captured=*hp;captured.memory=nullptr;assert(!phxProfileCanInitialize(&captured));
    PhxDisplayProfile badDisplay=*hp->display;badDisplay.addresses=nullptr;
    captured=*hp;captured.display=&badDisplay;assert(!phxProfileCanInitialize(&captured));
    PhxMemoryProfile memory=phx_hp_memory_profile;
    PhxReservedRange holes[]={{32ull<<20,8ull<<20},{240ull<<20,32ull<<20}};
    memory.reserved_ranges=holes;memory.reserved_count=2;
    PhxVramArena<32> arena;assert(arena.begin(256ull<<20));
    assert(phxExcludeProfileReservations(arena,256ull<<20,memory) && arena.seal());
    PhxVramLease lease;assert(!arena.allocateAt(32ull<<20,4096,lease));
    assert(!arena.allocateAt(255ull<<20,4096,lease));
    assert(arena.allocateAt(48ull<<20,4096,lease));
    assert(phxAcpiInternalPanel(0x80000400,0x400));
    assert(phxAcpiInternalPanel(0x110,0x110));
    assert(!phxAcpiInternalPanel(0x100,0x100));
    assert(!phxAcpiInternalPanel(0x400,0x400)); // no standard-ID declaration
    assert(!phxAcpiInternalPanel(0x80000300,0x300)); // external DVI
    assert(!phxAcpiInternalPanel(0x80000401,0x400));
    assert(!phxAcpiInternalPanel(0x180000400ull,0x400));
    const uint32_t bcl[]={50,25,0,100,75,50,25,10};
    PhxBrightnessLevels levels{};assert(levels.decode(bcl,8,50));
    assert(levels.count==5 && levels.values[0]==10 && levels.values[4]==100);
    Transport t;assert(phxBrightnessTransition(levels,4,t));assert(t.value==75 && t.writes==1);
    assert(phxBrightnessTransition(levels,4,t));assert(t.value==100);
    assert(phxBrightnessTransition(levels,4,t) && t.writes==2); // no redundant write
    t.ack=false;assert(!phxBrightnessTransition(levels,0,t) && levels.current==4);
    t.readOK=false;auto writes=t.writes;assert(!phxBrightnessTransition(levels,0,t) && t.writes==writes);
    t.readOK=true;t.value=101;assert(!phxBrightnessTransition(levels,0,t) && t.writes==writes);
    assert(!phxBrightnessTransition(levels,5,t) && t.writes==writes);
    const uint32_t indexBqc[]={50,25,10,25,50,100};PhxBrightnessLevels bad{};
    assert(!bad.decode(indexBqc,6,2)); // never guess index-valued firmware quirks
    assert(!bad.decode(indexBqc,6,0)); // no blackout default
    uint32_t duplicate[]={50,50,10,50,50,100};assert(!bad.decode(duplicate,6,50));
    uint32_t range[]={50,50,10,50,101};assert(!bad.decode(range,5,50));
    assert(!bad.decode(nullptr,6,50));assert(!bad.decode(bcl,259,50));
    PhxBrightnessRecord r{};r.version=1;r.level=50;uint32_t pci[]={0x1002,0x1900,0xca,0x103c,0x8c6a};uint8_t edid[128]{};
    for(unsigned i=0;i<5;++i)r.pci[i]=pci[i];
    assert(phxBrightnessRecordMatches(r,pci,edid,levels));
    edid[42]=1;assert(!phxBrightnessRecordMatches(r,pci,edid,levels));edid[42]=0;
    pci[4]++;assert(!phxBrightnessRecordMatches(r,pci,edid,levels));pci[4]--;
    r.level=0;assert(!phxBrightnessRecordMatches(r,pci,edid,levels));
    puts("[PASS] board gates, physical topology, internal-panel routing, bounded brightness, readback and panel-bound persistence");
}
