#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Test a pinned private plugin with WindowServer's mixed credentials, offscreen only."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import pwd
import shutil
import subprocess
import tempfile
import time

BASE = Path('/Users/Shared/nullarc-760m-sequoia-test')
CANDIDATE = '51ca6330c4110cd0078e95bd39ec4bb8a18f97d7f2204db430f6b7935ec6ee7d'
INSTALLED = 'ffa5c3368d69a0f28e13095c594852cdcf14d551a8f9e92ce8cbd032207483c2'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trusted(path):
    s = path.lstat()
    if path.is_symlink() or s.st_uid != 0 or s.st_mode & 0o022:
        raise ValueError('unsafe installed input: '+str(path))


def main():
    if os.getuid() != 0 or os.geteuid() != 0:
        raise ValueError('run with local sudo')
    caller = int(os.environ.get('SUDO_UID','0'))
    if not caller or os.stat('/dev/console').st_uid != caller:
        raise ValueError('active desktop sudo caller required')
    user = pwd.getpwuid(caller); ws = pwd.getpwnam('_windowserver')
    boot = subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()
    status = Path('/Users/Shared/nullarc-hp-native-status.json'); trusted(status)
    s = json.loads(status.read_text())
    if s.get('boot_session_uuid') != boot or not all(s.get(k) is True for k in ('apps_enabled','metal_verified','desktop_present_verified')):
        raise ValueError('current verified desktop required; no initialization attempted')
    binary = BASE/'hp50-plugin'
    candidate = binary.read_bytes()
    if hashlib.sha256(candidate).hexdigest() != CANDIDATE:
        raise ValueError('candidate differs')
    target = Path('/Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver')
    if digest(target) != INSTALLED:
        raise ValueError('installed plugin changed; review before testing')
    daemon = Path('/Library/LaunchDaemons/local.nullarc.hp-native.plist'); trusted(daemon)
    package = Path(plistlib.loads(daemon.read_bytes())['ProgramArguments'][-1])
    if package.parent != Path('/Library/Application Support/NullArc760M'):
        raise ValueError('unexpected package')
    trusted(package)
    manifest = json.loads((package/'package-manifest.json').read_text())
    source = package/'PhxGPU/NVMTLDriver.bundle'
    if digest(source/'Contents/MacOS/NVMTLDriver') != INSTALLED:
        raise ValueError('immutable bundle differs')
    probe = package/'gpu/phxctl/mtlprobe'
    if digest(probe) != manifest['files']['gpu/phxctl/mtlprobe']:
        raise ValueError('probe differs')
    work = Path(tempfile.mkdtemp(prefix='nullarc-mixed-cache50-',dir='/Users/Shared')); work.chmod(0o755)
    report = {'boot_session_uuid':boot,'installed_driver_changed':False,'candidate_sha256':CANDIDATE,'stages':[]}
    try:
        plugin = work/'NVMTLDriver.bundle'; shutil.copytree(source,plugin)
        (plugin/'Contents/MacOS/NVMTLDriver').write_bytes(candidate)
        for p in [plugin]+list(plugin.rglob('*')):
            if p.is_symlink():
                raise ValueError('unexpected bundle symlink')
            os.chown(p,0,0); p.chmod(p.stat().st_mode & 0o755)
        subprocess.run(['/usr/bin/codesign','--force','--sign','-',str(plugin)],check=True,capture_output=True)
        subprocess.run(['/usr/bin/codesign','--verify','--strict',str(plugin)],check=True,capture_output=True)
        logs = work/'logs'; logs.mkdir(mode=0o700); os.chown(logs,ws.pw_uid,ws.pw_gid)
        env = {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','TMPDIR':'/tmp',
               'NULLARC_PROBE_PLUGIN':str(plugin/'Contents/MacOS/NVMTLDriver'),
               'NVMTL_LOG_PATH':str(logs/'pipeline.log'),'NVMTL_PIPELINE_TIMING':'1'}
        # Match the measured credentials: real root IDs, effective WindowServer IDs.
        # No account, service, installed file or global credential change occurs.
        def credentials():
            os.setegid(ws.pw_gid); os.seteuid(ws.pw_uid)
        for mode in ('render','render','fetch','surface','lifetime'):
            if subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip() != boot:
                raise ValueError('boot changed')
            start = time.monotonic()
            p = subprocess.run([str(probe),'--hp',mode],env=env,preexec_fn=credentials,
                               capture_output=True,text=True,timeout=120)
            report['stages'].append({'mode':mode,'seconds':time.monotonic()-start,
                                     'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:
                raise ValueError(mode+' failed; later tests stopped')
        text = (logs/'pipeline.log').read_text()
        report['cache_log'] = [line for line in text.splitlines() if 'pipeline-cache:' in line or 'pipeline-time:' in line]
        if not any('loaded ' in line and 'loaded 0 bytes' not in line for line in report['cache_log']):
            raise ValueError('no persistent mixed-credential cache load observed')
        report['mixed_credentials_logged'] = any('effective UID '+str(ws.pw_uid)+', real UID 0' in line for line in report['cache_log'])
        if not report['mixed_credentials_logged']:
            raise ValueError('measured mixed credentials not logged')
        report['passed'] = True
    except Exception as e:
        report['error'] = str(e)
        raise
    finally:
        log = work/'logs/pipeline.log'
        if log.is_file():
            report['cache_log'] = [line for line in log.read_text(errors='replace').splitlines() if 'pipeline-cache:' in line or 'pipeline-time:' in line]
        report['installed_driver_unchanged'] = digest(target) == INSTALLED
        result = work/'result.json'; result.write_text(json.dumps(report,indent=2)+'\n')
        result.chmod(0o600); os.chown(result,caller,user.pw_gid)
        # Permit the caller to read the report while keeping all test binaries root-owned.
        print('REPORT: '+str(result))
        print('No installation, GPU reinitialization or reboot performed.')


if __name__ == '__main__':
    main()
