"""Transactional cache plugin staging; fixtures never touch a live driver."""
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'install')]
from package_manifest import write,inventory
import recover_hp_boot
import install_hp_cached_plugin as i

class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.old=self.root/'old';self.source=self.root/'new';self.state=self.root/'state';self.parent=self.root/'packages'
        self.state.mkdir();self.parent.mkdir()
        for package,data in ((self.old,b'old'),(self.source,b'new')):
            p=package/'PhxGPU/NVMTLDriver.bundle'/i.EXE;p.parent.mkdir(parents=True);p.write_bytes(data)
            for name in ('store.spv','vertex.spv','fragment.spv'):
                p=package/'validation'/name;p.parent.mkdir(exist_ok=True);p.write_bytes(b'shader')
            p=package/'gpu/fw/file';p.parent.mkdir(parents=True);p.write_bytes(b'firmware')
            write(package,{'fixture':True})
        self.target=self.root/'NVMTLDriver.bundle';shutil.copytree(self.old/'PhxGPU/NVMTLDriver.bundle',self.target)
        self.daemon=self.root/'daemon';self.config={'ProgramArguments':['old']}
        self.original=plistlib.dumps(self.config);self.daemon.write_bytes(self.original)
        for p in (patch.object(i,'OLD',hashlib.sha256(b'old').hexdigest()),patch.object(i,'CANDIDATE',hashlib.sha256(b'new').hexdigest()),patch.object(i.os,'chown'),patch.object(recover_hp_boot,'NATIVE',('gpu/fw','PhxGPU/NVMTLDriver.bundle','validation'))):
            p.start();self.addCleanup(p.stop)
    def stage(self):return i.stage(self.source,self.old,self.parent,self.state,self.daemon,self.original,self.config,self.target)
    def test_update_retains_original_and_stages_service(self):
        with patch.object(i.subprocess,'run') as calls:backup,dest,encoded=self.stage()
        calls.assert_not_called();self.assertEqual((backup/'NVMTLDriver').read_bytes(),b'old')
        self.assertEqual((self.target/i.EXE).read_bytes(),b'new')
        self.assertEqual(self.daemon.read_bytes(),encoded)
        self.assertEqual(inventory(dest),inventory(self.source))
    def test_daemon_failure_rolls_back_binary(self):
        with patch('install_diagnostics.atomic_write',side_effect=OSError('injected')),self.assertRaises(OSError):self.stage()
        self.assertEqual((self.target/i.EXE).read_bytes(),b'old');self.assertEqual(self.daemon.read_bytes(),self.original)
        self.assertEqual(list(self.parent.iterdir()),[])
    def test_concurrent_daemon_preserved(self):
        self.daemon.write_bytes(b'concurrent')
        with self.assertRaisesRegex(ValueError,'changed during staging'):self.stage()
        self.assertEqual(self.daemon.read_bytes(),b'concurrent');self.assertEqual((self.target/i.EXE).read_bytes(),b'old')
    def test_other_native_change_rejected_before_backup(self):
        (self.source/'gpu/fw/file').write_bytes(b'changed');write(self.source,{'fixture':True})
        with self.assertRaisesRegex(ValueError,'native change'):self.stage()
        self.assertEqual(list(self.state.iterdir()),[]);self.assertEqual((self.target/i.EXE).read_bytes(),b'old')

if __name__=='__main__':unittest.main()
