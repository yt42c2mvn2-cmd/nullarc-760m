import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import collect_hardware as c
import collect_macos_evidence as m
import phx_hardware_registry as registry
class DiscoveryTests(unittest.TestCase):
    def pci(self,maker=0x103c,device=0x1900):
        return dict(zip(c.MAC_KEYS,(0x1002,device,0xca,maker,0x8c6a)),**{'class-code':0x030000})
    def test_all_manufacturers_collected_without_authorization(self):
        for maker in (0x103c,0x1028,0x1043,0x17aa,0xffff):
            p=self.pci(maker);p['IOPlatformSerialNumber']='excluded'
            report=c.mac_capture([p])[0]
            self.assertEqual(report['pci']['subvendor'],maker)
            self.assertIsNone(report['topology']);self.assertIsNone(report['firmware_reservations'])
            self.assertFalse(report['initialization_authorized']);self.assertNotIn('excluded',str(report))
            self.assertEqual(m.target_policy([p]),'hp-diagnostic-only' if maker==0x103c else 'unreviewed-amd-diagnostic-only')
    def test_multiple_gpus_and_unsupported_identity(self):
        self.assertEqual(m.target_policy([self.pci(),self.pci(0x1028)]),'unreviewed-amd-diagnostic-only')
        self.assertEqual(len(c.mac_capture([self.pci(device=0x731f)])),1) # diagnostic facts only
        self.assertEqual(c.mac_capture([dict(self.pci(),**{'class-code':0x040300})]),[])
        self.assertEqual(m.target_policy([dict(zip(c.MAC_KEYS,(0x1002,0x1900,0xba,0x8001,0x2014)))]),'reference-profile')
    def test_edid_geometry_not_assumed(self):
        for w,h in ((1920,1200),(2560,1600),(3840,2160)):
            b=bytearray(128);b[:8]=bytes.fromhex('00ffffffffffff00');b[18]=1
            d=54;b[d:d+2]=(16814).to_bytes(2,'little');b[d+2]=w&255;b[d+3]=160;b[d+4]=(w>>8)<<4
            b[d+5]=h&255;b[d+6]=40;b[d+7]=(h>>8)<<4;b[127]=(-sum(b))&255
            result=c.edid(bytes(b));self.assertTrue(result['valid']);self.assertEqual(result['preferred_timing']['width'],w)
            self.assertEqual(result['preferred_timing']['height'],h)
            b[20]^=1;self.assertFalse(c.edid(bytes(b))['valid'])
        self.assertIsNone(c.edid(bytes(128))['preferred_timing'])
    def test_registry_and_no_whitelist_escape(self):
        data=json.loads((ROOT/'hardware/devices/registry.json').read_text());registry.validate(data)
        self.assertEqual(registry.render(data),(ROOT/'src/amd/phx_hardware_registry.inc').read_text())
        p=copy.deepcopy(data);p['profiles'].append(copy.deepcopy(p['profiles'][0]))
        with self.assertRaises(ValueError):registry.validate(p)
        p=copy.deepcopy(data);p['profiles'][0]['pci']['subvendor']=0x1028
        with self.assertRaises(ValueError):registry.validate(p)
        p=copy.deepcopy(data);p['profiles'][0]['pci']['revision']=True
        with self.assertRaises(ValueError):registry.validate(p)
    def test_linux_without_privileged_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dev=root/'bus/pci/devices/0000:03:00.0';dev.mkdir(parents=True)
            for k,v in {'vendor':'0x1002','class':'0x030000','device':'0x1900','revision':'0xca','subsystem_vendor':'0x17aa','subsystem_device':'0x1234'}.items():(dev/k).write_text(v)
            devices,errors=c.linux_capture(root);self.assertEqual(len(devices),1)
            self.assertEqual(devices[0]['pci']['subvendor'],0x17aa);self.assertTrue(errors)
            self.assertIsNone(devices[0]['bars']);self.assertFalse(devices[0]['initialization_authorized'])
if __name__=='__main__':unittest.main()
