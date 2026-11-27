# SPDX-License-Identifier: MIT
"""Install a verified, portable Blender LTS copy without changing system settings."""
from pathlib import Path
import hashlib
import re
import shutil
import sys
import zipfile
import requests


def install():
    if sys.platform!='win32':raise SystemExit('Install Blender from blender.org and set BLENDER_PATH on this operating system.')
    root=Path(__file__).resolve().parents[1]/'.tools'/'blender';root.mkdir(parents=True,exist_ok=True)
    base='https://download.blender.org/release/Blender4.5/'
    response=requests.get(base,timeout=30);response.raise_for_status()
    matches=re.findall(r'href="(blender-4\.5\.(\d+)-windows-x64\.zip)"',response.text)
    if not matches:raise RuntimeError('No supported Blender LTS package is listed')
    name=max(matches,key=lambda p:int(p[1]))[0];version=name.removesuffix('-windows-x64.zip')
    executable=root/(version+'-windows-x64')/'blender.exe'
    if executable.is_file():print('Blender is already installed:',executable);return executable
    if shutil.disk_usage(root).free<2_000_000_000:raise RuntimeError('Blender installation needs at least 2 GB of free disk space')
    checksum=requests.get(base+version+'.sha256',timeout=30);checksum.raise_for_status()
    expected=next(line.split()[0] for line in checksum.text.splitlines() if line.strip().endswith(name))
    archive=root/name
    print('Downloading',name,flush=True)
    if not archive.exists():
        with requests.get(base+name,stream=True,timeout=(15,90)) as response:
            response.raise_for_status()
            with archive.open('wb') as output:
                size=0;reported=0
                for chunk in response.iter_content(1024*1024):
                    output.write(chunk);size+=len(chunk)
                    if size-reported>40*1024*1024:print(round(size/1024/1024),'MB',flush=True);reported=size
    with archive.open('rb') as source:actual=hashlib.file_digest(source,'sha256').hexdigest()
    if actual!=expected:raise RuntimeError('Checksum failed. Remove the downloaded ZIP and retry; nothing was extracted.')
    print('Verified official checksum; extracting',flush=True)
    with zipfile.ZipFile(archive) as package:
        target=root.resolve()
        for member in package.infolist():
            if not (target/member.filename).resolve().is_relative_to(target):raise RuntimeError('Unsafe archive member')
        package.extractall(root)
    if not executable.is_file():raise RuntimeError('The Blender executable was not found after extraction')
    print('Installed:',executable,flush=True)
    return executable


if __name__=='__main__':install()
