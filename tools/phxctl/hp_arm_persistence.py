#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Authorize the approved display test after fresh app-only validation; no native/EFI writes."""
import hashlib,json,os,plistlib,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
need=lambda ok,message:None if ok else (_ for _ in ()).throw(ValueError(message))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def publish_receipt(output,result,uid,gid):
    from install_diagnostics import atomic_write
    atomic_write(output,(json.dumps(result,indent=2)+'\n').encode('utf-8'))
    output.chmod(0o600);os.chown(output,uid,gid)

def main():
    need(os.geteuid()==0 and int(os.environ.get('SUDO_UID','0'))>0,'local desktop-user sudo required')
    daemon=Path('/Library/LaunchDaemons/local.nullarc.hp-native.plist')
    c=plistlib.loads(daemon.read_bytes());package=Path(c['ProgramArguments'][-1])
    need(package.parent==Path('/Library/Application Support/NullArc760M'),'unexpected package path')
    for p in (package,daemon):
        st=p.lstat();need(not p.is_symlink() and st.st_uid==0 and not st.st_mode&0o022,'unsafe installed input')
    approved=json.loads((Path(__file__).parent/'approved-patch.json').read_text())
    need(approved['source_commit']=='010610d5d80da11f16663ffbda1bd6fb6d0cb7f1','unexpected approved patch')
    for name,item in approved['files'].items():need(digest(package/name)==item['patched_sha256'],'installed patch differs: '+name)
    sys.path[:0]=[str(package),str(package/'gpu/phxctl')]
    import hp_windowserver as d
    from hp_boot import verify_existing_native
    from install_hp_windowserver import validate_current_apps
    from package_manifest import inventory,verify
    from recover_hp_boot import NATIVE
    state=Path('/private/var/db/nullarc-760m');boot=d.boot_uuid()
    need(not any((state/n).exists() or (state/n).is_symlink() for n in ('pending','disabled',d.REQUEST,d.PERSISTENT)),'existing failure/request/consent requires review')
    status=Path('/Users/Shared/nullarc-hp-native-status.json');st=status.lstat()
    need(not status.is_symlink() and st.st_uid==0 and not st.st_mode&0o022,'unsafe status report')
    r=json.loads(status.read_text());validate_current_apps(r,boot)
    need(r.get('metal_readbacks_verified') is True and r.get('startup_stage')=='complete' and r.get('desktop_armed') is False,'fresh app-only Metal readbacks required')
    need(os.stat('/dev/console').st_uid==r.get('metal_validation_uid')==int(os.environ['SUDO_UID']),'console user changed')
    old=package.parent/'package-update-xr9x0hih';verify(old);verify(package)
    for name in NATIVE:
        a=old/name;b=package/name
        need(inventory(a)==inventory(b) if a.is_dir() else a.read_bytes()==b.read_bytes(),'native group differs: '+name)
    verify_existing_native(package);d.require_library_policy();d.validated_accelerator()
    need(not d.nodes('PhxAMDFB'),'expected firmware framebuffer before first display test')
    # Check injected metadata when the existing boot USB is mounted; never modify/mount it.
    info=Path('/Volumes/EFI/EFI/OC/Kexts/PhxBringup.kext/Contents/Info.plist')
    early=False
    if info.is_file():
        from install_early_fb import derive
        before=plistlib.loads(info.read_bytes());accel=plistlib.loads((package/'Library/Extensions/PhxAccel.kext/Contents/Info.plist').read_bytes())
        need(derive(before,accel)==before,'early framebuffer metadata needs review; no EFI changes made');early=True
    need(d.boot_uuid()==boot,'boot changed during checks')
    d.authorize_persistent(state,d.macho_uuid(package/'Library/Extensions/PhxAccel.kext/Contents/MacOS/PhxAccel'))
    result={'boot_session_uuid':boot,'package':str(package),'native_groups_unchanged':len(NATIVE),'early_metadata_checked_without_writes':early,'persistent_authorized':True,'nvram_verified':d.validate_schedule(state,d.macho_uuid(package/'Library/Extensions/PhxAccel.kext/Contents/MacOS/PhxAccel')),'reboot_performed':False}
    (state/'persistence-authorization-result.json').write_text(json.dumps(result,indent=2)+'\n')
    publish_receipt(Path('/Users/Shared/nullarc-persistence-arm-result.json'),result,int(os.environ['SUDO_UID']),int(os.environ['SUDO_GID']))
    print('READY FOR PERSISTENT DISPLAY REBOOT')
if __name__=='__main__':main()
