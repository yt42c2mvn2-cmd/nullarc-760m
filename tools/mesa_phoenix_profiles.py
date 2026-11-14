#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Replace the single-board RADV properties assignment with reviewed profiles.

Run after patches 0001..0013, instead of applying patch 0014. No GPU access.
"""
import argparse
import json
from pathlib import Path
from phx_hardware_registry import ROOT,render_radv

def apply(root):
    base=root/'src/amd/common/darwin';path=base/'ac_darwin_drm.c';text=path.read_text()
    old='''         if (phx_topology_matches(p, phx_hp_760m.vendor, phx_hp_760m.device, phx_hp_760m.revision,
                                  phx_hp_760m.subvendor, phx_hp_760m.subdevice))
            phx_hp_760m_apply_device_info(di);'''
    header=ROOT/'src/amd/phx_radv_profiles.h'
    if header.read_text()!=render_radv(json.loads((ROOT/'hardware/devices/registry.json').read_text())):
        raise ValueError('stale registry capabilities')
    include='#include "phx_hp_760m_device.h"'
    if text.count(old)!=1 or text.count(include)!=1 or (base/header.name).exists():raise ValueError('expected patch 0013 baseline')
    text=text.replace(include,include+'\n#include "phx_radv_profiles.h"').replace(old,'''         if (!phx_apply_profile_device_info(p, di))
            return -ENODEV;''')
    path.write_text(text);(base/header.name).write_bytes(header.read_bytes())
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mesa',type=Path);a=ap.parse_args();apply(a.mesa)
