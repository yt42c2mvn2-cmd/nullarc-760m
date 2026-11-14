#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only, vendor-neutral AMD PCI/display/backlight evidence (no driver needed).

No MMIO, ACPI method execution, GPU submissions, module loading or state changes.
Missing topology/firmware reservations remain unknown. This is not authorization.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import subprocess

PCI_KEYS=('vendor','device','revision','subvendor','subdevice')
MAC_KEYS=('vendor-id','device-id','revision-id','subsystem-vendor-id','subsystem-id')
SELECT=('assigned-addresses','IODeviceMemory','reg','model','built-in','AAPL,boot-display',
        'phx-profile','phx-stage','phx-memory-status','phx-vbios-status','phx-bringup-blocker',
        'phx-fb-mc-base','phx-fb-size','phx-fb-phys','phx-fb-aper-phys','phx-fb-aper-len',
        'PhxBacklightStatus','PhxBacklightMethod','PhxBacklightLevels','PhxBacklightCurrent',
        'PhxFBWidth','PhxFBHeight','PhxFBRowBytes','PhxFBRefreshMilliHz',
        'PhxFBHTotal','PhxFBVTotal','PhxFBTimingCaptured','PhxFBProfile')

def safe(v):
    if isinstance(v,bytes):return {'hex':v.hex(),'bytes':len(v)}
    if isinstance(v,dict):return {str(k):safe(x) for k,x in v.items()}
    if isinstance(v,list):return [safe(x) for x in v]
    return v

def walk(nodes):
    for n in nodes:
        yield n
        yield from walk(n.get('IORegistryEntryChildren',[]))

def number(v):
    return int.from_bytes(v,'little') if isinstance(v,bytes) and len(v)<=8 else v if type(v) is int else None

def edid(data):
    valid=isinstance(data,bytes) and 128<=len(data)<=32768 and len(data)%128==0 and data[:8]==bytes.fromhex('00ffffffffffff00') and len(data)==128*(data[126]+1) and all(sum(data[i:i+128])%256==0 for i in range(0,len(data),128))
    result={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'valid':bool(valid),'preferred_timing':None}
    if valid:
        # First base-block detailed timing only; other descriptors are not modes.
        d=data[54:72];clock=int.from_bytes(d[:2],'little')*10000
        if clock:
            w=d[2]+((d[4]&240)<<4);hb=d[3]+((d[4]&15)<<8)
            h=d[5]+((d[7]&240)<<4);vb=d[6]+((d[7]&15)<<8)
            if w and h and hb and vb:
                result['preferred_timing']={'width':w,'height':h,'htotal':w+hb,'vtotal':h+vb,'pixel_clock_hz':clock,
                    'interlaced':bool(d[17]&128),'source':'EDID detailed timing; not proof of active scanout'}
    return result

def mac_capture(nodes):
    devices=[]
    for n in walk(nodes):
        if number(n.get('vendor-id'))!=0x1002:continue
        cls=number(n.get('class-code'))
        if cls is not None and (cls>>16)!=3:continue
        props={k:number(n.get(m)) for k,m in zip(PCI_KEYS,MAC_KEYS)}
        entry={'pci':props,'runtime':{},'displays':[], 'topology':None,'firmware_reservations':None,
               'initialization_authorized':False}
        for child in walk([n]):
            selected={k:safe(child[k]) for k in SELECT if k in child}
            if selected:entry['runtime'].setdefault(child.get('IOObjectClass','unknown'),[]).append(selected)
            if isinstance(child.get('IODisplayEDID'),bytes):
                entry['displays'].append({'edid':edid(child['IODisplayEDID']),
                    'connection_flags':safe(child.get('IODisplayConnectFlags')),
                    'backlight_parameters':safe(child.get('IODisplayParameters',{}))})
        devices.append(entry)
    return devices

def read(path,errors,binary=False):
    try:
        with path.open('rb') as f:data=f.read(1024*1024+1)
        if len(data)>1024*1024:raise ValueError('capture limit exceeded')
        return data if binary else data.decode().strip()
    except (OSError,ValueError,UnicodeError) as e:
        errors.append({'attribute':path.name,'error':str(e)});return None

def query_drm(collector,node,pci):
    result={}
    for key,args in (('topology',[]),('device_info',['--device-info'])):
        p=subprocess.run([str(collector),*args,str(node)],capture_output=True,timeout=20)
        if p.returncode:raise ValueError('DRM query failed: '+p.stderr.decode(errors='replace')[:1000])
        result[key]=json.loads(p.stdout)
    if result['topology'].get('pci')!=pci:raise ValueError('DRM/sysfs PCI identities disagree')
    return result

def linux_capture(root=Path('/sys'),collector=None):
    devices=[];errors=[]
    for dev in sorted((root/'bus/pci/devices').glob('*')):
        try:
            if int((dev/'vendor').read_text(),16)!=0x1002 or int((dev/'class').read_text(),16)>>16!=3:continue
        except (OSError,ValueError):continue
        pci={k:read(dev/f,errors) for k,f in zip(PCI_KEYS,('vendor','device','revision','subsystem_vendor','subsystem_device'))}
        pci={k:int(v,16) if v else None for k,v in pci.items()}
        entry={'pci':pci,'bdf':dev.name,'bars':read(dev/'resource',errors), 'ip_discovery':{},'memory':{},
            'firmware':{},'topology':None,'firmware_reservations':None,'displays':[],'backlights':[],
            'initialization_authorized':False}
        for key in ('mem_info_vram_total','mem_info_vis_vram_total','mem_info_gtt_total'):
            entry['memory'][key]=read(dev/key,errors)
        entry['firmware']['vbios_version']=read(dev/'vbios_version',errors)
        ip=dev/'ip_discovery'
        if ip.is_dir():
            for p in sorted(ip.rglob('*')):
                if p.is_file() and p.resolve().is_relative_to(ip.resolve()):entry['ip_discovery'][str(p.relative_to(ip))]=read(p,errors)
        for connector in sorted((root/'class/drm').glob('card*-*')):
            link=connector/'device'
            # DRM connector's device can be the card directory, not the PCI device.
            card=connector.name.split('-')[0];carddev=root/'class/drm'/card/'device'
            if not carddev.exists() or carddev.resolve()!=dev.resolve():continue
            disp={'connector':connector.name,'status':read(connector/'status',errors),'modes':read(connector/'modes',errors)}
            raw=read(connector/'edid',errors,True)
            if raw:disp['edid']=edid(raw)
            entry['displays'].append(disp)
        for light in sorted((root/'class/backlight').glob('*')):
            if dev.resolve() not in (light.resolve(),*light.resolve().parents) and (not (light/'device').exists() or dev.resolve() not in ((light/'device').resolve(),*(light/'device').resolve().parents)):continue
            entry['backlights'].append({'name':light.name,**{k:read(light/k,errors) for k in ('type','brightness','actual_brightness','max_brightness','bl_power')}})
        if collector:
            render=[p for p in (root/'class/drm').glob('renderD*') if (p/'device').exists() and (p/'device').resolve()==dev.resolve()]
            if len(render)==1:
                try:
                    drm=query_drm(collector,Path('/dev/dri')/render[0].name,pci)
                    entry['topology']=drm['topology'];entry['drm_device_info']=drm['device_info']
                except (ValueError,OSError,subprocess.TimeoutExpired) as e:errors.append({'attribute':'DRM INFO','error':str(e)})
            else:errors.append({'attribute':'DRM INFO','error':'no unique render node'})
        devices.append(entry)
    return devices,errors

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--drm-collector',type=Path,help='Linux: compiled tools/linux-profile/collect.c (optional DRM INFO topology and capabilities)');a=ap.parse_args()
    errors=[];osname=platform.system()
    if osname=='Darwin':
        p=subprocess.run(['/usr/sbin/ioreg','-a','-l','-r','-c','IOPCIDevice'],capture_output=True,timeout=30)
        if p.returncode:raise SystemExit('ioreg failed: no capture made')
        devices=mac_capture(plistlib.loads(p.stdout))
    elif osname=='Linux':devices,errors=linux_capture(collector=a.drm_collector.resolve() if a.drm_collector else None)
    else:raise SystemExit('Supported collectors: macOS and Linux')
    report={'format':1,'os':osname,'captured_at':datetime.now(timezone.utc).isoformat(),'devices':devices,
        'errors':errors,'read_only':True,'gpu_writes':False,'initialization_authorized':False,
        'unknown':['Live firmware/display reservations and exclusive ownership require reviewed native validation',
                   'PCI identity or EDID alone does not establish GPU family, CU masks, panel routing or a backlight method']}
    # Exclusive, private output; do not overwrite reports or follow an existing symlink.
    import os
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(report,f,indent=2);f.write('\n')
    print(a.output)
if __name__=='__main__':main()
