#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate the compiled registry. Reports/proposed profiles never enable writes.

Adding a native backend requires code review of its memory/firmware/display
contract; retail GPU names and PCI subsystem vendors are not such a contract.
"""
import argparse
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
KEYS=('vendor','device','revision','subvendor','subdevice')
BACKENDS={'diagnostic':'PhxDiagnostic','captured-native':'PhxCapturedNative','reference-native':'PhxReferenceNative'}

def validate(data):
    if type(data.get('format')) is not int or data['format']!=1: raise ValueError('registry format')
    names=set();identities=set()
    for p in data['profiles']:
        name=p['name']
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',name) or name in names: raise ValueError('duplicate/invalid profile name')
        names.add(name)
        if not re.fullmatch(r'[A-Za-z0-9 ()_.-]{1,96}',p.get('model','AMD GPU')):raise ValueError('invalid model label')
        identity=tuple(p['pci'][k] for k in KEYS)
        for k,v in zip(KEYS,identity):
            if type(v) is not int or not 0<=v<=(255 if k=='revision' else 65535): raise ValueError('invalid PCI identity')
        if identity[0]!=0x1002 or identity in identities: raise ValueError('duplicate/non-AMD identity')
        identities.add(identity)
        if p['backend'] not in BACKENDS: raise ValueError('unknown backend')
        if p['backend']=='captured-native':
            contract(p)
        elif p.get('topology') is not None: raise ValueError('unexpected topology backend')
        if p['backend']=='reference-native':
            capture=json.loads((ROOT/'hardware/dumps/firebat_u6c/pci_resources.json').read_text())['gpu']
            fields=('pci_vendor_id','pci_device_id','pci_revision','pci_subsys_vendor','pci_subsys_device')
            if identity!=tuple(int(capture[k],16) for k in fields):
                raise ValueError('reference backend is not portable to another board')
        if not p.get('evidence') or any(not (ROOT/x).is_file() or '..' in Path(x).parts or Path(x).is_absolute() for x in p['evidence']):
            raise ValueError('missing repository evidence')
    return data

def contract(p):
    name=p.get('contract','')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',name):raise ValueError('native contract required')
    c=json.loads((ROOT/'hardware/devices/contracts'/f'{name}.json').read_text())
    if c.get('format')!=1 or c.get('backend')!='phoenix-native39' or c.get('gc_ip')!=[11,0,1] or c.get('dcn_ip')!=[3,1,4]:
        raise ValueError('unsupported initialization/IP contract')
    from phx_profile import load
    path=Path(c['topology_source'])
    if path.is_absolute() or '..' in path.parts:raise ValueError('invalid topology source')
    topology=load(ROOT/path)
    if topology['pci']!=p['pci']:raise ValueError('topology and PCI identity disagree')
    for h in c['headers']:
        if not re.fullmatch(r'[a-zA-Z0-9_]+\.h',h) or not (ROOT/'src/amd'/h).is_file():raise ValueError('missing reviewed configuration header')
    for key in ('topology_symbol','memory_symbol','display_symbol'):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',c[key]):raise ValueError('invalid configuration symbol')
    source=Path(c['device_info_source'])
    if source.is_absolute() or '..' in source.parts:raise ValueError('invalid capabilities source')
    measured=json.loads((ROOT/source).read_text())
    if measured['pci']!=p['pci'] or measured['profile']!=topology:raise ValueError('capabilities/topology evidence disagrees')
    from phx_device_profile import FIELDS
    from phx_profile import integer
    for k in FIELDS:integer(measured['device_info'][k],0,(1<<64)-1 if k in ('max_engine_clock','max_memory_clock','tcc_disabled_mask','mall_size') else (1<<32)-1,k)
    for k in ('gpu_counter_freq','max_engine_clock','max_memory_clock'):
        if not measured['device_info'][k]:raise ValueError('missing measured clock caps')
    return c

def render_radv(data):
    from phx_device_profile import FIELDS
    lines=['#ifndef PHX_RADV_PROFILES_H','#define PHX_RADV_PROFILES_H','#include "phx_topology.h"',
        'static inline int phx_apply_profile_device_info(const struct phx_topology *p, struct drm_amdgpu_info_device *di) {',
        '    if (!di || !phx_topology_valid(p)) return 0;']
    for entry in validate(data)['profiles']:
        if entry['backend']!='captured-native':continue
        c=contract(entry);capture=json.loads((ROOT/c['device_info_source']).read_text());t=capture['profile'];di=capture['device_info']
        identity=', '.join(hex(entry['pci'][k])+'u' for k in KEYS)
        lines.append('    if (phx_topology_matches(p, '+identity+')) {')
        for k in ('num_shader_engines','num_shader_arrays_per_engine','num_cu_per_sh','num_rb_pipes','enabled_rb_pipes_mask','cu_active_number'):
            lines.append(f'        if (p->{k} != {t[k]}u) return 0;')
        for se in range(4):
            for sa in range(4):lines.append(f'        if (p->cu_bitmap[{se}][{sa}] != {t["cu_bitmap"][se][sa]}u) return 0;')
        for k in FIELDS:lines.append(f'        di->{k} = {di[k]}ull;')
        lines.extend(['        return 1;','    }'])
    return '\n'.join(lines+['    return 0;','}','#endif',''])

def render(data):
    rows=[];headers=set()
    for p in validate(data)['profiles']:
        pci=', '.join(hex(p['pci'][k])+'u' for k in KEYS)
        if p['backend']=='captured-native':
            c=contract(p);headers.update(c['headers'])
            symbols=['&'+c[k] for k in ('topology_symbol','memory_symbol','display_symbol')]
        else:symbols=['nullptr']*3
        rows.append('    {"%s", %s, %s, %s, %s},'%(p['name'],json.dumps(p.get('model','AMD GPU')),pci,BACKENDS[p['backend']],', '.join(symbols)))
    return '/* Generated by tools/phx_hardware_registry.py; do not edit. */\n'+''.join('#include "'+h+'"\n' for h in sorted(headers))+\
        'static const PhxHardwareProfile phx_hardware_profiles[]={\n'+'\n'.join(rows)+'\n};\n'

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    data=json.loads((ROOT/'hardware/devices/registry.json').read_text())
    for name,expected in (('phx_hardware_registry.inc',render(data)),('phx_radv_profiles.h',render_radv(data))):
        path=ROOT/'src/amd'/name
        if a.write:path.write_text(expected)
        elif path.read_text()!=expected:ap.exit(1,'compiled registry is stale; use --write after review\n')
