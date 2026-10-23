"""The report as PDF (pandoc and a LaTeX installation with xelatex needed).

    python scripts/build_report.py [ausgabe.pdf]      (default: bericht.pdf in the repository)
"""
import datetime
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'bericht.pdf'

# the summary lives on the start page of the website, under "Kurzfassung"
start = (DOCS / 'README.md').read_text(encoding='utf-8')
summary = Path(tempfile.gettempdir()) / 'kurzfassung.md'
summary.write_text('# Kurzfassung\n' + start.split('## Kurzfassung', 1)[1].split('\n## ', 1)[0], encoding='utf-8')

subprocess.run([
    'pandoc', str(summary), *sorted(str(p) for p in (DOCS / 'bericht').glob('*.md')), str(DOCS / 'glossar.md'),
    # images stay where they are; the italic line below each image is its caption
    '-f', 'markdown-implicit_figures',
    '--citeproc', '--bibliography', str(DOCS / 'literatur.bib'),
    '--resource-path', f"{DOCS / 'bericht'}{';' if sys.platform == 'win32' else ':'}{DOCS}",
    '--pdf-engine=xelatex', '--toc', '--toc-depth=2',
    '-V', 'lang=de', '-V', 'mainfont=Segoe UI' if sys.platform == 'win32' else 'mainfont=DejaVu Sans',
    '-V', 'geometry:margin=2.2cm', '-V', 'fontsize=10pt', '-V', 'colorlinks=true',
    '-M', 'title=Flugblattsammlung Rep. 118: Projektbericht', '-M', f'date=Stand {datetime.date.today():%d.%m.%Y}',
    '-o', str(out),
], check=True)
print(out)
