"""Package only the public export; private research data never enters hosting."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

def main():
    out = ROOT/'_site'
    if out.exists(): shutil.rmtree(out)
    out.mkdir()
    for name in ('index.html', 'styles.css', 'app.js', 'data.js'):
        shutil.copy2(ROOT/name, out/name)
    for name in ('assets', 'legacy'):
        shutil.copytree(ROOT/name, out/name)
    # Bundle names are stable, so browsers must revalidate after daily updates.
    (out/'_headers').write_text('/*\n  Cache-Control: public, max-age=0, must-revalidate\n')
    files = [p for p in out.rglob('*') if p.is_file()]
    if any(p.stat().st_size > 25*1024*1024 for p in files):
        raise ValueError('A public asset exceeds the Cloudflare Pages file limit')
    print(f'Staged {len(files)} public files in {out}')

if __name__ == '__main__': main()
