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

# links in the blue of the documentation (the pandoc defaults are magenta, red and cyan)
colors = Path(tempfile.gettempdir()) / 'linkfarben.tex'
colors.write_text(r'\definecolor{doku}{HTML}{1E5AA8}' + '\n'
                  + r'\usepackage{titlesec}\newcommand{\sectionbreak}{\clearpage}' + '\n', encoding='utf-8')  # every chapter on a new page

# inline code (paths, file names) may break after / . = _ instead of running into the margin
code_filter = Path(tempfile.gettempdir()) / 'codeumbruch.lua'
code_filter.write_text(r'''
local esc = {['\\']='\\textbackslash{}', ['{']='\\{', ['}']='\\}', ['$']='\\$', ['&']='\\&', ['#']='\\#',
              ['^']='\\textasciicircum{}', ['_']='\\_\\allowbreak{}', ['%']='\\%', ['~']='\\textasciitilde{}'}
function Code(el)
  local t = el.text:gsub('[\\{}$&#^_%%~]', esc):gsub('([/.=])', '%1\\allowbreak{}')
  return pandoc.RawInline('latex', '\\texttt{' .. t .. '}')
end
''', encoding='utf-8')

# the bibliography is the last chapter, after the glossary
sources = Path(tempfile.gettempdir()) / 'quellen.md'
sources.write_text('# Quellen\n\n::: {#refs}\n:::\n', encoding='utf-8')

subprocess.run([
    'pandoc', str(summary), *sorted(str(p) for p in (DOCS / 'bericht').glob('*.md')), str(DOCS / 'glossar.md'), str(sources),
    # images stay where they are; the italic line below each image is its caption
    '-f', 'markdown-implicit_figures', '--lua-filter', str(code_filter),
    '--citeproc', '--bibliography', str(DOCS / 'literatur.bib'),
    '--resource-path', f"{DOCS / 'bericht'}{';' if sys.platform == 'win32' else ':'}{DOCS}",
    '--pdf-engine=xelatex', '--toc', '--toc-depth=2',
    '-V', 'lang=de', '-V', 'mainfont=Segoe UI' if sys.platform == 'win32' else 'mainfont=DejaVu Sans',
    '-V', 'geometry:margin=2.2cm', '-V', 'fontsize=10pt', '-V', 'colorlinks=true',
    '-V', 'linkcolor=doku', '-V', 'citecolor=doku', '-V', 'urlcolor=doku', '-V', 'toccolor=doku', '-H', str(colors),
    '-M', 'title=Flugblattsammlung Rep. 118: Projektbericht',
    '-M', 'subtitle=Praxisseminar Medieninformatik, Sommersemester 2026, Universität Regensburg',
    '-M', 'author=Veit Korpies, Felix Lindner, Sebastian Simbeck',
    '-M', f'date=Stand {datetime.date.today():%d.%m.%Y}',
    '-o', str(out),
], check=True)
print(out)
