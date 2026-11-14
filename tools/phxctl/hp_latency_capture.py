#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only HP startup/cache/WindowServer diagnostics; never initialize or install."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import pwd
import re
import subprocess
import tempfile


def run(args, timeout=20):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return {'command': args, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}


def read(path, limit=4*1024*1024):
    if path.is_symlink() or not path.is_file():
        raise ValueError('expected regular diagnostic file: '+str(path))
    with path.open('rb') as f:
        data = f.read(limit+1)
    if len(data) > limit:
        raise ValueError('diagnostic file exceeds bound: '+str(path))
    return data


def cache_inventory(root):
    result = {'path': str(root), 'files': 0, 'bytes': 0, 'newest_mtime': None}
    if not root.is_dir() or root.is_symlink():
        result['missing_or_symlink'] = True
        return result
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(base)/d).is_symlink()]
        for name in files:
            p = Path(base)/name
            if p.is_symlink():
                continue
            s = p.stat()
            result['files'] += 1; result['bytes'] += s.st_size
            result['newest_mtime'] = max(result['newest_mtime'] or 0, s.st_mtime)
            if result['files'] >= 10000:
                result['truncated'] = True
                return result
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seconds', type=int, default=10, choices=range(1,16))
    a = ap.parse_args()
    if os.geteuid() != 0:
        ap.error('local sudo is required to read protected reports and sample WindowServer')
    uid = int(os.environ.get('SUDO_UID', '0'))
    if uid == 0 or os.stat('/dev/console').st_uid != uid:
        raise ValueError('run through sudo from the active desktop user')
    user = pwd.getpwuid(uid)
    boot = subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'], text=True).strip()
    status = json.loads(read(Path('/Users/Shared/nullarc-hp-native-status.json')))
    if status.get('boot_session_uuid') != boot or status.get('desktop_present_verified') is not True:
        raise ValueError('current-boot verified desktop required; no recovery attempted')
    report = {'boot_session_uuid': boot, 'status': status, 'gpu_commands_submitted': 0}
    folder = Path(tempfile.mkdtemp(prefix='nullarc-latency49-', dir='/Users/Shared'))
    try:
        daemon = plistlib.loads(read(Path('/Library/LaunchDaemons/local.nullarc.hp-native.plist')))
        package = Path(daemon['ProgramArguments'][-1])
        if package.parent != Path('/Library/Application Support/NullArc760M'):
            raise ValueError('unexpected immutable package directory')
        report['package'] = str(package)
        for p in sorted(Path('/var/db/nullarc-760m').glob('boot-*/boot-result.json')):
            data = json.loads(read(p))
            if data.get('boot_session_uuid') == boot:
                report.setdefault('boot_reports', []).append({'path':str(p), 'report':data})
                native = p.parent/'execution/result.json'
                if native.is_file():
                    report['native_report'] = json.loads(read(native))
        log = Path('/tmp/nvmtl.log')
        text = read(log).decode(errors='replace')
        (folder/'driver.log').write_text(text)
        roots = set(re.findall(r'Mesa shader disk cache at (/var/folders/[^\n]+)', text))
        report['mesa_caches'] = [cache_inventory(Path(p)) for p in sorted(roots)]
        tool = package/'gpu/phxctl/phxprofile'
        manifest = json.loads(read(package/'package-manifest.json'))
        if hashlib.sha256(read(tool)).hexdigest() != manifest['files']['gpu/phxctl/phxprofile']:
            raise ValueError('reservation reader differs from installed package')
        report['reservations'] = run([str(tool),'--reservations'])
        report['display_counters'] = run(['/usr/sbin/sysctl','debug.phxfb_alias','debug.nvaccel_iop_sse',
            'debug.nvaccel_iop_fail','debug.nvaccel_iop_copy_us','debug.nvaccel_iop_gap1',
            'debug.nvaccel_iop_gap2','debug.nvaccel_iop_gap3','debug.nvaccel_iop_gap4'])
        pids = subprocess.check_output(['/usr/bin/pgrep','-x','WindowServer'], text=True).split()
        if len(pids) != 1:
            raise ValueError('one active WindowServer required')
        owner = subprocess.check_output(['/bin/ps','-p',pids[0],'-o','uid='], text=True).strip()
        if int(owner) != pwd.getpwnam('_windowserver').pw_uid:
            raise ValueError('unexpected WindowServer owner')
        print('Capturing for '+str(a.seconds)+' seconds; reproduce the fullscreen transition now.', flush=True)
        report['sample'] = run(['/usr/bin/sample',pids[0],str(a.seconds),'10','-file',
                                str(folder/'WindowServer.sample')], timeout=a.seconds+30)
        report['boot_unchanged'] = subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'], text=True).strip() == boot
    finally:
        (folder/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        for p in folder.iterdir():
            p.chmod(0o600); os.chown(p,uid,user.pw_gid)
        folder.chmod(0o700); os.chown(folder,uid,user.pw_gid)
        print('REPORT: '+str(folder/'result.json'))


if __name__ == '__main__':
    main()
