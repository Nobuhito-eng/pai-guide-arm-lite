"""Build a clean directory for public GitHub upload. Does not upload anything.
Only an allowlist is copied. Local logs, recordings, account names and .git
history are excluded. Review the generated folder before publishing.
"""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
ALLOW_DIRS=['guide_lite','config','data','model','scripts','tests','docs','evidence']
ALLOW_FILES=['guide.py','run.ps1','README.md','START_HERE_JA.md','TODO.md','LICENSE','THIRD_PARTY.md','.gitignore','.gitattributes','requirements-training.txt']

def main():
    out=ROOT/'dist/pai-guide-arm-lite'
    if out.exists():
        raise SystemExit('dist/pai-guide-arm-lite already exists. Review/rename it before making a new copy; nothing was overwritten.')
    out.mkdir(parents=True)
    for folder in ALLOW_DIRS:
        shutil.copytree(ROOT/folder,out/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ALLOW_FILES:
        shutil.copy2(ROOT/name,out/name)
    for f in ROOT.glob('*.cmd'):
        shutil.copy2(f,out/f.name)
    print('Created: dist/pai-guide-arm-lite (local only; not uploaded).')
    print('Included: application, model, data, documentation and licenses. Excluded: local logs, recordings and Git history.')

if __name__=='__main__': main()
