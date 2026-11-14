/* SPDX-License-Identifier: MIT
 * Native IODisplayParameterHandler over validated ACPI video methods.
 * No AMD MMIO or AUX writes. No NVIDIA code. No guessed panel paths/ranges.
 */
#include <IOKit/IOLib.h>
#include <IOKit/IOLocks.h>
#include <IOKit/pci/IOPCIDevice.h>
#include <IOKit/acpi/IOACPIPlatformDevice.h>
#include <IOKit/graphics/IODisplay.h>
#include <IOKit/graphics/IOFramebuffer.h>
#include <IOKit/IODeviceTreeSupport.h>
#include <kern/thread_call.h>
#include <pexpert/pexpert.h>
#include "../../amd/phx_backlight_policy.h"
#include "phxbacklight.h"

static bool panelEdid(IOACPIPlatformDevice *p,unsigned w,unsigned h,uint8_t out[128]) {
    OSNumber *size=OSNumber::withNumber(128,32);if(!size)return false;
    OSObject *args[]={size},*reply=nullptr;
    IOReturn rc=p->evaluateObject("_DDC",&reply,args,1);size->release();
    OSData *data=OSDynamicCast(OSData,reply);bool valid=false;
    if(rc==kIOReturnSuccess && data && data->getLength()==128) {
        const uint8_t *b=(const uint8_t *)data->getBytesNoCopy();uint8_t sum=0;
        for(unsigned i=0;i<128;++i)sum+=b[i];
        const uint8_t magic[]={0,255,255,255,255,255,255,0};
        const uint8_t *d=b+54;
        valid=!sum && !memcmp(b,magic,8) && b[18]==1 && (d[0]||d[1]) && !(d[17]&128) &&
            (d[2]+((d[4]&240)<<4))==w && (d[5]+((d[7]&240)<<4))==h;
    }
    if(valid)memcpy(out,data->getBytesNoCopy(),128);
    OSSafeReleaseNULL(reply);return valid;
}

class PhxBacklight : public IODisplayParameterHandler {
    OSDeclareDefaultStructors(PhxBacklight)
    IOACPIPlatformDevice *panel=nullptr;
    PhxBrightnessLevels levels{};
    IOLock *lock=nullptr,*firmwareLock=nullptr;
    thread_call_t apply=nullptr;
    uint32_t target=0,userTarget=0;
    PhxBrightnessRecord record{};
    bool savePending=false;
    uint64_t saveDeadline=0;
    bool awake=true,failed=false,stopping=false;
    static void fire(thread_call_param_t self,thread_call_param_t);
public:
    static PhxBacklight *discover(IOPCIDevice *pci,IOService *fb,unsigned w,unsigned h);
    bool setDisplay(IODisplay *display) override;
    bool doIntegerSet(OSDictionary *,const OSSymbol *,UInt32) override;
    bool doDataSet(const OSSymbol *,OSData *) override {return false;}
    bool doUpdate() override {
        if(!lock)return false;IOLockLock(lock);bool ok=!failed && !stopping;IOLockUnlock(lock);return ok;
    }
    const uint8_t *edid() const {return record.edid;}
    void power(bool on);
    void shutdown();
    void free() override;
};
OSDefineMetaClassAndStructors(PhxBacklight,IODisplayParameterHandler)

PhxBacklight *PhxBacklight::discover(IOPCIDevice *pci,IOService *fb,unsigned w,unsigned h) {
    int off=0;
    if(PE_parse_boot_argn("-phxbacklightoff",&off,sizeof(off))){fb->setProperty("PhxBacklightStatus","disabled-by-boot-argument");return nullptr;}
    const OSSymbol *baseName=OSSymbol::withCStringNoCopy("IODisplayParameterHandler");
    const OSMetaClass *base=baseName?OSMetaClass::getMetaClassWithName(baseName):nullptr;
    const bool abi=base && base->getClassSize()==sizeof(IODisplayParameterHandler);OSSafeReleaseNULL(baseName);
    if(!abi){fb->setProperty("PhxBacklightStatus","parameter-handler-ABI-unverified");return nullptr;}
    // Follow only this PCI device's ACPI peer, never the first global PNLF.
    IOACPIPlatformDevice *gpu=OSDynamicCast(IOACPIPlatformDevice,pci->getProperty("acpi-device"));
    for(IORegistryEntry *e=pci;!gpu && e;e=e->getParentEntry(gIOACPIPlane))
        if((gpu=OSDynamicCast(IOACPIPlatformDevice,e)))break;
    if(!gpu) {fb->setProperty("PhxBacklightStatus","no-ACPI-GPU-peer");return nullptr;}
    OSObject *obj=nullptr;
    if(gpu->evaluateObject("_DOD",&obj)!=kIOReturnSuccess) {OSSafeReleaseNULL(obj);return nullptr;}
    OSArray *outputs=OSDynamicCast(OSArray,obj);IOACPIPlatformDevice *candidate=nullptr;
    unsigned matches=0;
    OSIterator *children=gpu->getChildIterator(gIOACPIPlane);
    if(outputs && outputs->getCount()<=64 && children) while(OSObject *o=children->getNextObject()) {
        auto *p=OSDynamicCast(IOACPIPlatformDevice,o);UInt64 adr=0;
        if(!p || p->evaluateInteger("_ADR",&adr)!=kIOReturnSuccess)continue;
        for(unsigned i=0;i<outputs->getCount();++i) {
            auto *id=OSDynamicCast(OSNumber,outputs->getObject(i));
            if(!id || !phxAcpiInternalPanel(id->unsigned64BitValue(),adr))continue;
            // A duplicate route is ambiguous, including duplicate _DOD entries.
            ++matches;candidate=p;
        }
    }
    if(candidate && matches==1)candidate->retain();else candidate=nullptr;
    OSSafeReleaseNULL(children);obj->release();
    if(!candidate) {fb->setProperty("PhxBacklightStatus","internal-route-unverified");return nullptr;}
    const char *methods[]={"_BCL","_BQC","_BCM","_DDC","_DCS"};bool valid=true;
    for(auto name:methods)if(candidate->validateObject(name)!=kIOReturnSuccess)valid=false;
    UInt32 dcs=0,current=0;uint8_t panelBytes[128]{};
    if(!valid || candidate->evaluateInteger("_DCS",&dcs)!=kIOReturnSuccess || (dcs&3)!=3 ||
        !panelEdid(candidate,w,h,panelBytes) || candidate->evaluateInteger("_BQC",&current)!=kIOReturnSuccess) {
        fb->setProperty("PhxBacklightStatus","ACPI-capabilities-or-active-panel-unverified");candidate->release();return nullptr;
    }
    OSObject *bcl=nullptr;const IOReturn bclStatus=candidate->evaluateObject("_BCL",&bcl);
    OSArray *a=OSDynamicCast(OSArray,bcl);uint32_t values[258]{};PhxBrightnessLevels decoded{};
    valid=bclStatus==kIOReturnSuccess && a && a->getCount()>=4 && a->getCount()<=258;
    if(valid)for(unsigned i=0;i<a->getCount();++i) {
        auto *n=OSDynamicCast(OSNumber,a->getObject(i));
        if(!n || n->unsigned64BitValue()>100){valid=false;break;}values[i]=n->unsigned32BitValue();
    }
    if(valid)valid=decoded.decode(values,a->getCount(),current);
    OSSafeReleaseNULL(bcl);
    if(!valid){fb->setProperty("PhxBacklightStatus","ACPI-levels-unverified");candidate->release();return nullptr;}
    auto *me=OSTypeAlloc(PhxBacklight);
    if(!me || !me->init()){OSSafeReleaseNULL(me);candidate->release();return nullptr;}
    me->panel=candidate;me->levels=decoded;me->target=me->userTarget=decoded.current;
    me->record.version=1;memcpy(me->record.edid,panelBytes,128);
    const uint32_t pciIdentity[]={pci->configRead16(0),pci->configRead16(2),pci->configRead8(8),pci->configRead16(0x2c),pci->configRead16(0x2e)};
    memcpy(me->record.pci,pciIdentity,sizeof(pciIdentity));
    if(IORegistryEntry *options=IORegistryEntry::fromPath("/options",gIODTPlane)) {
        if(auto *data=OSDynamicCast(OSData,options->getProperty("nullarc-backlight"))) {
            PhxBrightnessRecord saved{};
            if(data->getLength()==sizeof(saved)) {
                memcpy(&saved,data->getBytesNoCopy(),sizeof(saved));
                if(phxBrightnessRecordMatches(saved,pciIdentity,panelBytes,decoded))
                    for(unsigned i=0;i<decoded.count;++i)if(decoded.values[i]==saved.level)me->target=me->userTarget=i;
            }
        }
        options->release();
    }
    me->lock=IOLockAlloc();me->firmwareLock=IOLockAlloc();me->apply=thread_call_allocate(fire,me);
    if(!me->lock || !me->firmwareLock || !me->apply || !me->attach(fb)){me->release();return nullptr;}
    me->setName("backlight");me->registerService();
    if(me->target!=me->levels.current)thread_call_enter(me->apply);
    fb->setProperty("PhxBacklightStatus","ACPI-validated-not-hardware-tested");
    fb->setProperty("PhxBacklightMethod","ACPI-video");
    fb->setProperty("PhxBacklightLevels",decoded.count,32);fb->setProperty("PhxBacklightCurrent",current,32);
    return me;
}

bool PhxBacklight::setDisplay(IODisplay *display) {
    // Only the IOBacklightDisplay on this framebuffer may own these parameters.
    if(!OSDynamicCast(IOBacklightDisplay,display) || !display->getConnection() ||
        display->getConnection()->getFramebuffer()!=getProvider())return false;
    OSDictionary *params=OSDynamicCast(OSDictionary,display->getProperty(kIODisplayParametersKey));
    if(!params) {
        params=OSDictionary::withCapacity(1);if(!params)return false;
        display->setProperty(kIODisplayParametersKey,params);params->release();
        params=OSDynamicCast(OSDictionary,display->getProperty(kIODisplayParametersKey));
    }
    return params && IODisplay::addParameter(params,gIODisplayBrightnessKey,0,(SInt32)(levels.count-1)) &&
        IODisplay::setParameter(params,gIODisplayBrightnessKey,(SInt32)userTarget);
}

bool PhxBacklight::doIntegerSet(OSDictionary *params,const OSSymbol *name,UInt32 value) {
    if(name==gIODisplayParametersCommitKey || name==gIODisplayParametersFlushKey)return doUpdate();
    if(name!=gIODisplayBrightnessKey || !lock)return false;
    const bool user=params && params->getObject(gIODisplayValueKey);
    if(user && value>=levels.count)return false;
    if(value>=levels.count)value=levels.count-1; // Apple's power restore uses a default 255.

    IOLockLock(lock);bool ok=!failed && !stopping;
    if(ok){
        if(user){userTarget=value;savePending=true;clock_interval_to_deadline(2,kSecondScale,&saveDeadline);}
        target=user?value:(value<userTarget?value:userTarget);
        if(awake)thread_call_enter(apply);
    }
    IOLockUnlock(lock);return ok;
}

void PhxBacklight::fire(thread_call_param_t self,thread_call_param_t) {
    auto *me=(PhxBacklight *)self;
    IOLockLock(me->firmwareLock); // Serialize possible overlapping thread-call activations.
    IOLockLock(me->lock);
    if(me->stopping || me->failed || !me->awake){IOLockUnlock(me->lock);IOLockUnlock(me->firmwareLock);return;}
    PhxBrightnessLevels current=me->levels;const unsigned requested=me->target;
    IOLockUnlock(me->lock); // Never hold the UI-facing lock across firmware evaluation.
    struct AcpiTransport {
        IOACPIPlatformDevice *p;
        bool read(uint32_t &value){return p->evaluateInteger("_BQC",&value)==kIOReturnSuccess;}
        bool write(uint32_t value){
            OSNumber *n=OSNumber::withNumber(value,32);if(!n)return false;OSObject *args[]={n};
            IOReturn rc=p->evaluateObject("_BCM",nullptr,args,1);n->release();return rc==kIOReturnSuccess;
        }
    } transport{me->panel};
    const bool acknowledged=phxBrightnessTransition(current,requested,transport);
    IOLockLock(me->lock);
    me->failed=!acknowledged;me->levels.current=current.current;
    me->setProperty("PhxBacklightStatus",me->failed?"failed-no-further-writes":"ACPI-readback-matched");
    me->setProperty("PhxBacklightCurrent",me->levels.values[me->levels.current],32);
    if(!me->failed && me->savePending && me->levels.current==me->userTarget && mach_absolute_time()>=me->saveDeadline) {
        me->record.level=me->levels.values[me->userTarget];
        if(IORegistryEntry *options=IORegistryEntry::fromPath("/options",gIODTPlane)) {
            auto *data=OSData::withBytes(&me->record,sizeof(me->record));
            bool saved=data && options->setProperty("nullarc-backlight",data);
            me->setProperty("PhxBacklightPersistence",saved?"record-staged":"NVRAM-unavailable");
            OSSafeReleaseNULL(data);options->release();
        }
        me->savePending=false;
    }
    if(!me->failed && !me->stopping && me->awake && me->levels.current!=me->target) {
        uint64_t deadline;clock_interval_to_deadline(16,kMillisecondScale,&deadline);thread_call_enter_delayed(me->apply,deadline);
    } else if(!me->failed && !me->stopping && me->awake && me->savePending && mach_absolute_time()<me->saveDeadline) {
        thread_call_enter_delayed(me->apply,me->saveDeadline);
    }
    IOLockUnlock(me->lock);IOLockUnlock(me->firmwareLock);
}
void PhxBacklight::power(bool on) {
    IOLockLock(lock);awake=on;if(on)target=userTarget;
    if(on && !failed && !stopping)thread_call_enter(apply);
    IOLockUnlock(lock);
    if(!on && apply)thread_call_cancel_wait(apply);
}
void PhxBacklight::shutdown() {
    if(lock){IOLockLock(lock);stopping=true;IOLockUnlock(lock);}
    if(apply){thread_call_cancel_wait(apply);while(!thread_call_free(apply)){thread_call_cancel_wait(apply);IOSleep(1);}apply=nullptr;}
}
void PhxBacklight::free() {
    shutdown();OSSafeReleaseNULL(panel);if(firmwareLock){IOLockFree(firmwareLock);firmwareLock=nullptr;}if(lock){IOLockFree(lock);lock=nullptr;}IODisplayParameterHandler::free();
}
IOService *phxBacklightCreate(IOPCIDevice *pci,IOService *fb,unsigned w,unsigned h) {return PhxBacklight::discover(pci,fb,w,h);}
void phxBacklightPower(IOService *h,bool on){if(auto *b=OSDynamicCast(PhxBacklight,h))b->power(on);}
void phxBacklightDestroy(IOService *h,IOService *fb){if(auto *b=OSDynamicCast(PhxBacklight,h)){b->shutdown();b->terminate(kIOServiceRequired|kIOServiceSynchronous);b->detach(fb);b->release();}}

bool phxBacklightEdid(IOService *h,uint8_t out[128]) {
    auto *b=OSDynamicCast(PhxBacklight,h);if(!b || !out)return false;memcpy(out,b->edid(),128);return true;
}
