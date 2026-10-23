"""Figure for chapter 12.2 from the dates in the report.

    python scripts/report_figures.py

Writes docs/abbildungen/zeitverlauf.png.
"""
from datetime import date
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / 'docs/abbildungen'
GREEN, RED, INK, GREY, GRID = '#237a50', '#a83535', '#3f4854', '#68707c', '#ddd9d1'
plt.rcParams.update({
    'font.family': 'Segoe UI', 'font.size': 14, 'savefig.dpi': 200, 'savefig.bbox': 'tight',
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.spines.left': False, 'axes.edgecolor': GREY,
    'xtick.color': INK, 'ytick.color': INK, 'text.color': INK, 'axes.labelcolor': INK,
})

# (Zeile, Beginn, Ende, Beschriftung); alle Daten 2026
LANES = [('Anwendung', [(date(2026, 9, 24), date(2026, 10, 23))]),
         ('Mehrfachexemplare', [(date(2026, 10, 5), date(2026, 10, 11))]),
         ('Themen', [(date(2026, 9, 17), date(2026, 10, 3))]),
         ('Metadaten', [(date(2026, 9, 22), date(2026, 10, 2))]),
         ('Trennen', [(date(2026, 7, 23), date(2026, 8, 22)), (date(2026, 9, 29), date(2026, 9, 29))]),
         ('Texterkennung', [(date(2026, 6, 23), date(2026, 8, 4)), (date(2026, 8, 17), date(2026, 8, 19))])]
PHASES = [('Vorbereitung', date(2026, 5, 12), date(2026, 6, 22)),
          ('Rohdaten', date(2026, 6, 23), date(2026, 8, 24)),
          ('Erschließung und Anwendung', date(2026, 8, 25), date(2026, 10, 23))]
EVENTS = [('Antrittsvortrag', date(2026, 6, 9), 'center'), ('Zwischenpräsentation', date(2026, 7, 14), 'center'),
          ('Vorführung', date(2026, 10, 7), 'right'), ('Abschlusspräsentation', date(2026, 10, 14), 'left')]


def timeline():
    fig, ax = plt.subplots(figsize=(12, 5))
    for k, (name, a, b) in enumerate(PHASES):
        ax.axvspan(a, b, color=('#f1efe9', '#e8e5dc')[k % 2], zorder=0)
        ax.text(a + (b - a) / 2, len(LANES) + 0.35, name, ha='center', va='bottom', fontsize=12, fontweight='bold')
    for i, (name, spans) in enumerate(LANES):
        for a, b in spans:
            ax.barh(i, max((b - a).days, 1), left=mdates.date2num(a), height=0.5, color=GREEN)
    for label, d, align in EVENTS:
        ax.axvline(d, color=RED, lw=1.2, ymax=0.88)
        ax.text(d, -0.9, label, color=RED, ha=align, va='top', fontsize=10)
    ax.set_yticks(range(len(LANES)), [n for n, _ in LANES])
    ax.set_ylim(-0.6, len(LANES) + 0.9)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax.set_xlim(date(2026, 5, 10), date(2026, 11, 8))
    ax.xaxis.tick_top()
    ax.tick_params(left=False, top=False)
    ax.set_title('Wann welcher Arbeitsschritt lief (2026)', loc='left', fontweight='bold', fontsize=18, pad=34)
    fig.savefig(OUT / 'zeitverlauf.png')


if __name__ == '__main__':
    timeline()
