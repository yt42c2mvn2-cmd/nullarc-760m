#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install the pinned, offscreen-tested cache candidate and arm one HP display boot."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
INPUT_CANDIDATE = '51ca6330c4110cd0078e95bd39ec4bb8a18f97d7f2204db430f6b7935ec6ee7d'
CANDIDATE = 'e77818d5d29dc3cd985ed9e2b798bc5eb3d1346568aaeec6033c1a38dec18dcb'
OLD = 'ffa5c3368d69a0f28e13095c594852cdcf14d551a8f9e92ce8cbd032207483c2'
EXE = 'Contents/MacOS/NVMTLDriver'


def stage(source, old, parent, state, daemon, original, config, target):
    from package_manifest import verify, inventory, digest
    from install_diagnostics import atomic_write
    from recover_hp_boot import NATIVE
    verify(source); verify(old)
    for name in NATIVE:
        if name in ('PhxGPU/NVMTLDriver.bundle','validation'): continue
        a = old/name; b = source/name
        if (inventory(a) != inventory(b) if a.is_dir() else a.read_bytes() != b.read_bytes()):
            raise ValueError('unreviewed native change: '+name)
    for name in ('store.spv','vertex.spv','fragment.spv'):
        if (old/'validation'/name).read_bytes() != (source/'validation'/name).read_bytes():
            raise ValueError('authored readback shader changed')
    before = inventory(old/'PhxGPU/NVMTLDriver.bundle'); after = inventory(source/'PhxGPU/NVMTLDriver.bundle')
    if set(before) != set(after) or {p for p in before if before[p] != after[p]} != {EXE}:
        raise ValueError('only the reviewed plugin executable may change')
    if before[EXE] != OLD or after[EXE] != CANDIDATE or inventory(target) != before:
        raise ValueError('installed/old/candidate binary differs from pinned test')
    backup = Path(tempfile.mkdtemp(prefix='cache50-update-',dir=state))
    (backup/'daemon.plist').write_bytes(original)
    shutil.copy2(target/EXE,backup/'NVMTLDriver')
    destination = Path(tempfile.mkdtemp(prefix='package-cache50-',dir=parent)); destination.rmdir()
    updated = dict(config)
    updated['ProgramArguments'] = ['/usr/bin/python3','-B',str(destination/'gpu/phxctl/hp_boot.py'),'--package',str(destination)]
    encoded = plistlib.dumps(updated)
    changed = False
    try:
        shutil.copytree(source,destination); verify(destination)
        for p in [destination]+list(destination.rglob('*')):
            if p.is_symlink(): raise ValueError('symlink in staged package')
            os.chown(p,0,0); p.chmod(p.stat().st_mode & 0o755)
        if daemon.read_bytes() != original or inventory(target) != before:
            raise ValueError('installed service/plugin changed during staging')
        with tempfile.TemporaryDirectory(prefix='.nullarc-cache50-',dir=(target/EXE).parent) as tmp:
            binary = Path(tmp)/'NVMTLDriver'
            shutil.copy2(destination/'PhxGPU/NVMTLDriver.bundle'/EXE,binary)
            os.chown(binary,0,0); binary.chmod(0o755)
            os.replace(binary,target/EXE); changed = True
        atomic_write(daemon,encoded); daemon.chmod(0o644)
        if inventory(target) != after or daemon.read_bytes() != encoded:
            raise ValueError('plugin/service readback mismatch')
    except BaseException:
        if changed and digest(target/EXE) == CANDIDATE:
            with tempfile.TemporaryDirectory(prefix='.nullarc-restore-',dir=(target/EXE).parent) as tmp:
                binary = Path(tmp)/'NVMTLDriver'; shutil.copy2(backup/'NVMTLDriver',binary)
                os.replace(binary,target/EXE)
        if daemon.read_bytes() == encoded: atomic_write(daemon,original)
        if destination.exists(): shutil.rmtree(destination)
        raise
    return backup,destination,encoded


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',type=Path,required=True); ap.add_argument('--sha256',required=True)
    ap.add_argument('--test-report',type=Path,required=True)
    a = ap.parse_args()
    if os.geteuid() != 0 or int(os.environ.get('SUDO_UID','0')) <= 0:
        raise ValueError('local desktop-user sudo required')
    if not re.fullmatch('[a-f0-9]{64}',a.sha256): raise ValueError('invalid archive digest')
    state = Path('/private/var/db/nullarc-760m'); parent = Path('/Library/Application Support/NullArc760M')
    daemon = Path('/Library/LaunchDaemons/local.nullarc.hp-native.plist')
    target = Path('/Library/GPUBundles/NVMTLDriver.bundle')
    for p in (state,parent,daemon,target):
        for q in (p,*p.parents):
            st = q.lstat()
            if q.is_symlink() or st.st_uid != 0 or st.st_mode & 0o022: raise ValueError('unsafe installed path: '+str(q))
    if any((state/n).exists() for n in ('pending','disabled','windowserver-next-boot.json')):
        raise ValueError('existing boot/failure/request marker; review before updating')
    with (state/'cache50-install.lock').open('a') as lock, tempfile.TemporaryDirectory(prefix='cache50-import-',dir=state) as temporary:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        tmp = Path(temporary); archive = tmp/'candidate.zip'; shutil.copyfile(a.archive,archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != a.sha256: raise ValueError('archive differs')
        subprocess.run(['/usr/bin/ditto','-x','-k',str(archive),str(tmp)],check=True,timeout=90)
        packages = [p for p in tmp.iterdir() if p.is_dir() and (p/'package-manifest.json').is_file()]
        if len(packages) != 1: raise ValueError('one verified package required')
        source = packages[0]; sys.path[:0] = [str(source),str(source/'gpu/phxctl')]
        from package_manifest import verify, inventory
        from install_diagnostics import atomic_write
        from install_hp_windowserver import configured_package, validate_current_apps
        from hp_boot import verify_existing_native, user_prefix, console_user
        import hp_windowserver as display
        verify(source)
        original,config,old = configured_package(daemon,parent)
        verify_existing_native(old); display.require_library_policy(); display.validated_accelerator()
        if not display.framebuffer(): raise ValueError('current healthy accelerated HP desktop required')
        boot = display.boot_uuid()
        status = json.loads(Path('/Users/Shared/nullarc-hp-native-status.json').read_text())
        validate_current_apps(status,boot)
        if status.get('desktop_present_verified') is not True: raise ValueError('missing live desktop evidence')
        result = json.loads(a.test_report.read_text())
        if (result.get('boot_session_uuid') != boot or result.get('candidate_sha256') != INPUT_CANDIDATE or
            not all(result.get(k) is True for k in ('passed','mixed_credentials_logged','installed_driver_unchanged')) or
            [s.get('mode') for s in result.get('stages',[])] != ['render','render','fetch','surface','lifetime'] or
            any(s.get('returncode') != 0 for s in result.get('stages',[]))): raise ValueError('matching mixed-credential readbacks required')
        nv = plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp']))
        if 'phxfb-boot' in nv: raise ValueError('existing framebuffer NVRAM request')
        backup,destination,encoded = stage(source,old,parent,state,daemon,original,config,target)
        report = {'boot_session_uuid':boot,'backup':str(backup),'package':str(destination),'stages':[],'armed':False}
        try:
            subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(target)],check=True,timeout=20)
            verify_existing_native(destination)
            user = console_user(timeout=5)
            work = Path(tempfile.mkdtemp(prefix='nullarc-cache50-check-',dir='/Users/Shared'))
            for p in (work,work/'cache',work/'aircache'):
                if p != work: p.mkdir()
                p.chmod(0o700); os.chown(p,user.pw_uid,user.pw_gid)
            prefix = user_prefix(user,work)
            for mode in ('render','fetch','surface','lifetime'):
                if display.boot_uuid() != boot or os.stat('/dev/console').st_uid != user.pw_uid:
                    raise ValueError('boot/console changed; stop without arming')
                p = subprocess.run(prefix+[str(destination/'gpu/phxctl/mtlprobe'),'--hp',mode],capture_output=True,text=True,timeout=120)
                report['stages'].append({'mode':mode,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
                if p.returncode: raise ValueError('installed '+mode+' readback failed; no GPU retry or abort requested')
            from install_hp_windowserver import main as arm
            sys.argv = ['install_hp_windowserver','--package',str(destination),'--install']
            arm()
            report['armed'] = True
            print('READY FOR GUARDED CACHE DISPLAY TEST')
        except BaseException:
            # Restore only our unchanged staged files, preserving any concurrent edit.
            from package_manifest import digest
            if digest(target/EXE) == CANDIDATE:
                with tempfile.TemporaryDirectory(prefix='.nullarc-cache50-rollback-',dir=(target/EXE).parent) as d:
                    f = Path(d)/'NVMTLDriver'; shutil.copy2(backup/'NVMTLDriver',f); os.replace(f,target/EXE)
            if daemon.read_bytes() == encoded: atomic_write(daemon,original)
            raise
        finally:
            report_path = backup/'install-result.json'; report_path.write_text(json.dumps(report,indent=2)+'\n')
            public = Path('/Users/Shared/nullarc-760m-sequoia-test/hp50-install-result.json')
            atomic_write(public,json.dumps(report,indent=2)+'\n'); public.chmod(0o600)
            os.chown(public,int(os.environ['SUDO_UID']),int(os.environ['SUDO_GID']))
            print('REPORT: '+str(public))


if __name__ == '__main__':
    main()
