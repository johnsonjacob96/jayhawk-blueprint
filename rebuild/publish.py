"""Copy verified static output to the existing GitHub Pages root; retain legacy app."""
from pathlib import Path
import shutil,gzip
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent
legacy=REPO/'legacy/index.html'
if not legacy.exists():
 legacy.parent.mkdir(exist_ok=True);shutil.copy2(REPO/'index.html',legacy)
for name in ['index.html','styles.css','app.js','data.js']:
 shutil.copy2(ROOT/'web'/name,REPO/name)
shutil.copytree(ROOT/'web/assets',REPO/'assets',dirs_exist_ok=True)
# Dated model grades are durable even when CI caches and source artifacts expire.
archive=ROOT/'history';archive.mkdir(exist_ok=True)
for p in (ROOT/'data/grades').glob('*.json'):
 target=archive/(p.name+'.gz')
 if not target.exists():target.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
print('Static output copied to Pages root; original retained in legacy/.')
