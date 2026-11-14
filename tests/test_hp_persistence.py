"""State-machine regressions with synthetic hardware and in-memory NVRAM only."""
import json
import fcntl
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools/phxctl')]
import hp_boot as b
import hp_windowserver as d

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.state=self.root/'state';self.state.mkdir()
        self.allow=self.root/'allow';self.status=self.root/'status';self.nv={};self.uuid='A';self.panics={}
        patches=[patch.object(d,'boot_uuid',side_effect=lambda:self.uuid),
                 patch.object(d,'_nvram',side_effect=lambda:dict(self.nv)),
                 patch.object(d,'macho_uuid',return_value='ACCEL'),
                 patch.object(d,'panic_snapshot',side_effect=lambda:dict(self.panics)),
                 patch.object(d,'_read_root_record',side_effect=lambda p:json.loads(p.read_text())),
                 patch.object(d,'wait_for_framebuffer'),patch.object(d,'require_library_policy'),
                 patch.object(d,'nodes',return_value=[]),patch.object(d,'check_crashes'),
                 patch.object(d,'fallback'),patch.object(d.subprocess,'run',side_effect=self.nvcommand),
                 patch.object(b.subprocess,'Popen',side_effect=self.process),
                 patch.object(d,'arm',side_effect=lambda r,*args:r.update(desktop_armed=True,desktop_crash_baseline=[])),
                 patch.object(d,'verify_present',side_effect=lambda r,*args:r.update(desktop_present_verified=True,desktop_present_count=9,desktop_present_delta=9,desktop_failed_transactions=0)),
                 patch.object(b,'verify_console_metal',side_effect=lambda p,r,s:r.update(metal_verified=True,metal_readbacks_verified=True))]
        for p in patches:p.start();self.addCleanup(p.stop)
        self.code=0
    def nvcommand(self,args,**kwargs):
        if 'phxfb-boot=1' in args:self.nv['phxfb-boot']=b'1'
        if '-d' in args:self.nv.pop('phxfb-boot',None)
        return subprocess.CompletedProcess(args,0)
    def process(self,args,**kwargs):
        folder=Path(args[args.index('--output')+1]);folder.mkdir()
        (folder/'result.json').write_text(json.dumps(dict(executed=True,native_compute_verified=True,
            native_render_verified=True,accelerator_claimed=True,metal_verified=False)))
        from types import SimpleNamespace
        return SimpleNamespace(returncode=self.code,communicate=lambda **kwargs:('',''))
    def boot(self,uuid):
        self.uuid=uuid
        self.nv.pop('phxfb-boot',None)  # Existing kext consumes/commits the one-shot before userspace.
        return b.boot(self.root,self.state,self.allow,self.status)
    def authorize(self):d.authorize_persistent(self.state,'ACCEL')
    def test_consecutive_verified_boots_schedule_successors(self):
        self.authorize()
        for uuid in ('B','C','D'):
            self.boot(uuid)
            r=json.loads(self.status.read_text());self.assertTrue(r['desktop_persistent_rearmed'])
            self.assertEqual(json.loads((self.state/d.REQUEST).read_text())['armed_from_boot'],uuid)
            self.assertEqual(self.nv['phxfb-boot'],b'1');self.assertFalse((self.state/'pending').exists())
    def test_duplicate_supervisor_does_not_replace_live_status_or_allow_list(self):
        self.allow.write_text('live desktop');self.status.write_text('live status')
        with (self.state/'boot.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with patch.object(b.subprocess,'Popen') as spawn:b.boot(self.root,self.state,self.allow,self.status)
        spawn.assert_not_called();self.assertEqual(self.allow.read_text(),'live desktop')
        self.assertEqual(self.status.read_text(),'live status')
    def test_explicit_enable_is_idempotent_and_legacy_authorization_can_be_renewed(self):
        self.authorize();before=(self.state/d.REQUEST).read_bytes();self.authorize()
        self.assertEqual((self.state/d.REQUEST).read_bytes(),before)
        (self.state/d.PERSISTENT).write_text(json.dumps({'format':1,'accelerator_uuid':'ACCEL'}))
        self.authorize();self.assertIn('panic_files',json.loads((self.state/d.PERSISTENT).read_text()))
    def test_rearm_error_does_not_disable_or_reboot_verified_desktop(self):
        self.authorize()
        with patch.object(d,'arm_next_boot',side_effect=OSError('NVRAM unavailable')):
            self.boot('B')
        r=json.loads(self.status.read_text());self.assertTrue(r['apps_enabled']);self.assertTrue(r['desktop_present_verified'])
        self.assertIn('desktop_rearm_error',r);self.assertNotIn('error',r)
        self.assertFalse((self.state/'disabled').exists());d.fallback.assert_not_called()
        self.assertNotIn('phxfb-boot',self.nv)
    def test_genuine_native_failure_cancels_successor(self):
        self.authorize();self.code=1
        with self.assertRaises(ValueError):self.boot('B')
        self.assertTrue((self.state/'pending').exists());self.assertTrue((self.state/'disabled').exists())
        self.assertFalse((self.state/d.PERSISTENT).exists());self.assertNotIn('phxfb-boot',self.nv)
        d.fallback.assert_called_once()
    def test_interruption_before_gui_validation_blocks_retry_and_explicit_recovery(self):
        self.authorize()
        with patch.object(b,'verify_console_metal',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):self.boot('B')
        with patch.object(b.subprocess,'Popen') as spawn,self.assertRaises(ValueError):self.boot('C')
        spawn.assert_not_called();r=json.loads(self.status.read_text())
        self.assertEqual(r['startup_blocked_by'],'previous-boot-incomplete')
        self.assertTrue(r['previous_boot']['native_initialization_verified']);self.assertFalse(r['apps_enabled'])
        # Model an explicitly reviewed, backed-up recovery on an idle boot, not automatic marker clearing.
        backup=self.root/'backup';backup.mkdir()
        for name in ('pending','disabled'):(self.state/name).rename(backup/name)
        self.authorize();self.boot('D');self.assertTrue(json.loads(self.status.read_text())['desktop_persistent_rearmed'])
    def test_new_panic_stops_before_native_submission(self):
        self.authorize();self.panics['Kernel-new.panic']=[123,456]
        with patch.object(b.subprocess,'Popen') as spawn,self.assertRaisesRegex(ValueError,'panic'):self.boot('B')
        spawn.assert_not_called();self.assertNotIn('phxfb-boot',self.nv);self.assertFalse((self.state/d.PERSISTENT).exists())
    def test_nvram_clear_failure_retains_authorization_evidence(self):
        self.authorize()
        with patch.object(d.subprocess,'run',side_effect=subprocess.TimeoutExpired('nvram',5)),self.assertRaises(subprocess.TimeoutExpired):d.cancel_persistence(self.state)
        self.assertTrue((self.state/d.REQUEST).exists());self.assertTrue((self.state/d.PERSISTENT).exists())
    def test_package_accelerator_mismatch_and_unverified_takeover_never_rearm(self):
        self.authorize();self.nv.clear();(self.state/d.REQUEST).unlink()
        with patch.object(d,'macho_uuid',return_value='OTHER'),self.assertRaisesRegex(ValueError,'accelerator'):d.rearm_if_permanent(self.root,self.state,{})
        with self.assertRaisesRegex(ValueError,'success required'):d.rearm_if_permanent(self.root,self.state,{'native_initialization_verified':True})
        self.assertNotIn('phxfb-boot',self.nv)
    def test_idle_but_presented_desktop_passes_without_forcing_a_frame(self):
        report={'desktop_present_baseline':0}
        with patch.object(d,'verify_present',new=REAL_PRESENT),patch.object(d,'sysctl',side_effect=lambda n:0 if n.endswith('fail') else 12),patch.object(d,'framebuffer',return_value={'IORegistryEntryChildren':[{'IOObjectClass':'IOFramebufferUserClient'}]}):
            d.verify_present(report,lambda:None)
        self.assertTrue(report['desktop_present_verified']);self.assertEqual(report['desktop_present_delta'],12)
    def test_console_transition_retries_validation_without_reinitializing(self):
        self.authorize();count=[]
        def metal(package,report,save):
            count.append(1)
            if len(count)==1:raise b.ConsoleSessionChanged('login transition')
            report.update(metal_verified=True,metal_readbacks_verified=True)
        with patch.object(b,'verify_console_metal',side_effect=metal),patch.object(b.subprocess,'Popen',side_effect=self.process) as native:
            self.boot('B')
        self.assertEqual(native.call_count,1);self.assertEqual(len(count),2)
        self.assertTrue(json.loads(self.status.read_text())['desktop_persistent_rearmed'])

REAL_PRESENT=d.verify_present
if __name__=='__main__':unittest.main()
