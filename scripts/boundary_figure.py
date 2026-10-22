"""Figure for chapter 4: what speaks for and against a new leaflet, with the weights the app uses.

    python scripts/boundary_figure.py

Reads the weights from src/backend/app/boundaries.py and writes docs/abbildungen/trennmerkmale.png.
"""
import importlib.util
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/abbildungen/trennmerkmale.png'
spec = importlib.util.spec_from_file_location('boundaries', ROOT / 'src/backend/app/boundaries.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

# green for a new leaflet, red against it, as the reasons in the splitter; the rest as in corpus_figures.ipynb
CUT, KEEP, INK, GREY, GRID = '#237a50', '#a83535', '#3f4854', '#68707c', '#ddd9d1'
plt.rcParams.update({
    'font.family': 'Segoe UI', 'font.size': 14, 'savefig.dpi': 200, 'savefig.bbox': 'tight',
    'axes.titlesize': 18, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left', 'axes.titlepad': 14,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.spines.left': False, 'axes.edgecolor': GREY,
    'xtick.color': INK, 'ytick.color': INK, 'text.color': INK, 'axes.labelcolor': INK,
})


# spelled out for the report; the app's shorter labels (boundaries.LABEL) stay as they are
LABEL = {'stamp': 'Eingangsstempel im Text („eingelaufen am …“)', 'headdate': 'Datum oben auf der Seite',
         'masthead': 'Kopfleiste mit wiederholtem Namen („LSD – LSD – LSD“)',
         'prev_imprint': 'Impressum unten auf der Seite davor („Verantwortlich: …“)',
         'prev_blank': 'Seite davor ist fast leer', 'overlap_low': 'kaum gleiche Wörter wie auf der Seite davor',
         'first_heading': 'Seite beginnt mit einer Überschrift', 'blank': 'Seite ist fast leer',
         'prev_end': 'Seite davor endet mit einem Satzzeichen', 'overlap_high': 'viele gleiche Wörter wie auf der Seite davor',
         'prev_bw': '„b. w.“ (bitte wenden) auf der Seite davor', 'cont_word': 'Seite beginnt mit „Fortsetzung“',
         'pagenum': 'Seitenzahl wie „- 2 -“ auf der Seite', 'prev_hyphen': 'Seite davor endet mitten im Wort („Ab-“)',
         'sign': 'blaues „F“ des Archivs, von Hand', 'stamp_seen': 'blauer Stempel des Archivs',
         'paper_very_other': 'Papier mit deutlich anderer Farbe', 'paper_other': 'Papier mit etwas anderer Farbe',
         'ink_other': 'viel mehr oder weniger Schrift als davor', 'margins_other': 'Text mit anderen Seitenrändern',
         'size_other': 'Blatt mit anderem Format', 'paper_same': 'Papier mit gleicher Farbe',
         'back': 'Abheftlöcher nur rechts: eine Rückseite'}


PLACE = {'start': 'in den ersten 250 Zeichen', 'end': 'in den letzten 250 Zeichen davor'}  # where a word of the list counts


def spelled(label):
    """The report's wording for a reason as the app names it (boundaries.explain)."""
    by_app = {b.LABEL[k]: v for k, v in LABEL.items()}
    word = label.replace('am Seitenanfang', PLACE['start']).replace('am Ende der Seite davor', PLACE['end'])
    return by_app.get(label, word)


def de(w):
    return f'{w:+.1f}'.replace('.', ',').replace('-', '−')


if __name__ == '__main__':
    words = [(f'„{w}“ {PLACE[where]}', v)
             for where in ('start', 'end') for w, v in b.CUE_WEIGHTS[where].items()]
    words.sort(key=lambda r: -r[1])
    n_words = len({w for d in b.CUE_WEIGHTS.values() for w in d})
    groups = [('Im erkannten Text', [(LABEL[k], v) for k, v in b.WEIGHTS.items()]),
              ('Im Bild der Seite', [(LABEL[k], v) for k, v in b.IMAGE_WEIGHTS.items()]),
              (f'Einzelne Wörter (Beispiele von {n_words})', words[:3] + words[-3:])]

    rows = []  # (label, weight or None for a group heading)
    for title, items in groups:
        rows += [(title, None)] + sorted(items, key=lambda r: -r[1])
    fig, ax = plt.subplots(figsize=(10, 0.38 * len(rows) + 1))
    for y, (label, w) in enumerate(rows):
        if w is not None:
            ax.barh(y, w, height=0.62, color=CUT if w > 0 else KEEP)
            ax.text(w + (0.08 if w > 0 else -0.08), y, de(w), va='center', ha='left' if w > 0 else 'right')
    ax.set_ylim(len(rows) - 0.4, -0.8)
    ax.set_xlim(-3.4, 5)
    ax.axvline(0, color=INK, lw=1.2)
    ax.set_yticks(range(len(rows)), [label for label, _ in rows])
    ax.tick_params(axis='y', length=0, pad=10)
    for tick, (_, w) in zip(ax.get_yticklabels(), rows):
        if w is None:  # group headings
            tick.set_fontweight('bold')
    ax.set_xticks([-3, -2, -1, 0, 1, 2, 3, 4])
    ax.set_xticklabels([de(t) if t else '0' for t in [-3, -2, -1, 0, 1, 2, 3, 4]])
    ax.grid(axis='x', color=GRID)
    ax.set_axisbelow(True)
    ax.set_xlabel('Gewicht')
    ax.text(0.15, -0.75, 'spricht für ein neues Flugblatt →', color=CUT, ha='left')
    ax.text(-0.15, -0.75, '← dagegen', color=KEEP, ha='right')
    ax.set_title('Hinweise auf einen Flugblattwechsel')
    NOTE = ['Je Seitenwechsel: „Seite“ ist die Seite, mit der vielleicht ein neues Flugblatt beginnt, „Seite davor“ die vorige.',
            f'Wert = Grundwert ({de(b.PRIOR)}) + Gewichte aller Hinweise, die zutreffen. Über 0 schlägt die App eine Trennung vor.',
            'Von den einzelnen Wörtern zählt je Seitenwechsel nur das stärkste dafür und das stärkste dagegen.']
    ax.annotate('\n'.join(NOTE), xy=(0.02, 0), xycoords=('figure fraction', 'axes fraction'), xytext=(0, -62),
                textcoords='offset points', color=GREY, fontsize=12, va='top')
    fig.savefig(OUT)
    print(OUT)
