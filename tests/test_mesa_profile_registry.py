#!/usr/bin/env python3
"""Host-only profile dispatch and patch/generator agreement; no GPU access."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from phx_device_profile import FIELDS
from phx_hardware_registry import render_radv
from mesa_phoenix_profiles import apply

def dispatch():
    header=ROOT/'src/amd/phx_radv_profiles.h'
    assert header.read_text()==render_radv(json.loads((ROOT/'hardware/devices/registry.json').read_text()))
    code='#include <stdint.h>\n#include <assert.h>\nstruct drm_amdgpu_info_device {\n'+''.join('uint64_t '+k+';\n' for k in FIELDS)+'};\n'
    code+='''#include "phx_hp_760m.h"
#include "phx_radv_profiles.h"
int main(void) {
    struct drm_amdgpu_info_device di={0};struct phx_topology p=phx_hp_760m;
    assert(phx_apply_profile_device_info(&p,&di));
    assert(di.family==148 && di.gpu_counter_freq==100000 && di.max_engine_clock==2600000);
    p.subvendor=0x1028;assert(!phx_apply_profile_device_info(&p,&di));
    p=phx_hp_760m;p.cu_bitmap[0][0]=0x33;assert(!phx_apply_profile_device_info(&p,&di));
    p=phx_hp_760m;p.cu_bitmap[0][0]=0x30;assert(!phx_apply_profile_device_info(&p,&di));
    p=phx_hp_760m;p.device=0x731f;assert(!phx_apply_profile_device_info(&p,&di));
    assert(!phx_apply_profile_device_info(0,&di));return 0;
}
'''
    with tempfile.TemporaryDirectory() as d:
        src=Path(d)/'test.c';src.write_text(code);binary=Path(d)/'test'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src/amd'),str(src),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)

def roundtrip(mesa):
    path='src/amd/common/darwin/ac_darwin_drm.c'
    baseline=subprocess.check_output(['git','-C',str(mesa),'show','HEAD:'+path])
    with tempfile.TemporaryDirectory() as d:
        generated=Path(d)/'generated';patched=Path(d)/'patched'
        for root in (generated,patched):
            p=root/path;p.parent.mkdir(parents=True);p.write_bytes(baseline)
        apply(generated)
        subprocess.run(['git','apply','--no-index',str(ROOT/'mesa-patches-phoenix/0014-radv-darwin-validated-device-profiles.patch')],cwd=patched,check=True)
        for p in (path,'src/amd/common/darwin/phx_radv_profiles.h'):
            assert (generated/p).read_bytes()==(patched/p).read_bytes()
        before=(generated/path).read_bytes()
        try:apply(generated)
        except ValueError:pass
        else:raise AssertionError('repeat application must be refused')
        assert before==(generated/path).read_bytes()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--mesa',type=Path);a=ap.parse_args();dispatch()
    if a.mesa:roundtrip(a.mesa.resolve())
    print('[PASS] C profile dispatch, measured caps, unknown/topology rejection'+('; patch roundtrip' if a.mesa else ''))
