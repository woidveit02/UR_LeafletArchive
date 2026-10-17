"""Schreibt die Kennzahlen des Korpus in docs/kennzahlen.md (nur den Bereich zwischen den Markern).

    python scripts/kennzahlen.py

Liest die Datenbank nur lesend und zählt mit den Funktionen der App.
"""
import datetime
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import event, func

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from backend.app.database import session as database  # noqa: E402

import backend.app.app as app  # noqa: E402
from backend.app.database.models import RELEASED, Page, Volume  # noqa: E402

DOC = ROOT / "docs" / "kennzahlen.md"
BEGIN, END = "<!-- BEGIN generiert -->", "<!-- END generiert -->"
FIRST_HEADING, NEXT_HEADING = "## Seiten und Token je Jahr", "## OCR-Qualität"
UNDATED = "undatiert"


def number(n):
    return f"{n:,}".replace(",", " ")


def percent(part, whole):
    return f"{100 * part / whole:.2f}".replace(".", ",") + " %" if whole else "–"


def dated(item):
    return (item["leaflet"].date_iso or "")[:4].isdigit()


def compute():
    """Alle Zahlen als Dictionary; gezählt wird mit den Funktionen der App."""
    volumes = list(app.session.query(Volume).filter_by(status=RELEASED).order_by(Volume.vz))
    pages = dict(app.session.query(Page.volume_id, func.count()).group_by(Page.volume_id))
    copies = app.faceted_items([("duplikate", "1")])[0]  # jedes Segment
    documents = app.unique(app.faceted_items([])[0])  # Exemplare zusammengefasst, Hauptexemplar
    vz_year = {v.vz: v.year for v in volumes}
    segments = Counter(i["vz"] for i in copies)
    docs = Counter(i["vz"] for i in documents)
    by_band_year, by_date_year = Counter(), Counter()
    for kind, items in (("segments", copies), ("documents", documents)):
        for i in items:
            by_band_year[kind, str(vz_year[i["vz"]])] += 1
            by_date_year[kind, i["year"] if dated(i) else UNDATED] += 1
    band_pages = Counter()
    for v in volumes:
        band_pages[str(v.year)] += pages.get(v.id, 0)
    issuers = app.issuer_years(documents)
    return {
        "volumes": [{"vz": v.vz, "year": v.year, "pages": pages.get(v.id, 0), "segments": segments[v.vz],
                     "documents": docs[v.vz]} for v in volumes],
        "band_year": by_band_year, "date_year": by_date_year, "band_pages": band_pages,
        "segments": len(copies), "documents": len(documents),
        "pages": sum(pages.get(v.id, 0) for v in volumes),
        "issuers": sum(1 for org, years in issuers.items() if org not in app.SPECIAL and sum(years.values())),
        "no_issuer": sum(issuers[app.NO_ORG].values()), "unregistered": sum(issuers[app.NOT_IN_REGISTER].values()),
        "types": Counter(i["leaflet"].doc_type or "unklar" for i in documents),
        "stamp": datetime.datetime.fromtimestamp(app.database_stamp()[0] / 1e9).strftime("%d.%m.%Y %H:%M"),
    }


def table(header, rows, total):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    lines.append("| " + " | ".join(f"**{c}**" if c != "" else "" for c in total) + " |")
    return "\n".join(lines)


def render(data, today=None):
    today = (today or datetime.date.today()).strftime("%d.%m.%Y")
    volumes = data["volumes"]
    bands = table(["Band", "Jahr", "Seiten", "Segmente", "Exemplare", "Flugblätter"],
                  [(f"{v['vz']:03d}", v["year"], number(v["pages"]), number(v["segments"]), number(v["segments"]),
                    number(v["documents"])) for v in volumes],
                  ["Summe", "", number(data["pages"]), number(data["segments"]), number(data["segments"]),
                   number(data["documents"])])
    years = sorted({y for _, y in data["band_year"]})
    def further(segments, documents):
        return number(segments - documents), percent(segments - documents, segments)

    by_band = table(["Bandjahr", "Bände", "Seiten", "Segmente", "Exemplare", "Flugblätter", "weitere Exemplare",
                     "Anteil"],
                    [(y, sum(str(v["year"]) == y for v in volumes), number(data["band_pages"][y]),
                      number(data["band_year"]["segments", y]), number(data["band_year"]["segments", y]),
                      number(data["band_year"]["documents", y]),
                      *further(data["band_year"]["segments", y], data["band_year"]["documents", y])) for y in years],
                    ["Summe", len(volumes), number(data["pages"]), number(data["segments"]),
                     number(data["segments"]), number(data["documents"]),
                     *further(data["segments"], data["documents"])])
    labels = sorted({y for _, y in data["date_year"] if y != UNDATED}) + [UNDATED]
    by_date = table(["Datierungsjahr", "Segmente", "Exemplare", "Flugblätter"],
                    [(y, number(data["date_year"]["segments", y]), number(data["date_year"]["segments", y]),
                      number(data["date_year"]["documents", y])) for y in labels],
                    ["Summe", number(data["segments"]), number(data["segments"]), number(data["documents"])])
    types = table(["Textsorte", "Flugblätter", "Anteil"],
                  [(app.DOC_TYPES.get(t, t), number(n), percent(n, data["documents"]))
                   for t, n in data["types"].most_common()],
                  ["Summe", number(data["documents"]), percent(data["documents"], data["documents"])])
    return f"""{BEGIN}
## Korpus nach Band und Jahr

Stand: {today}, Datenbank vom {data['stamp']}. Erzeugt von scripts/kennzahlen.py – nicht von Hand bearbeiten.

### Je Band

{bands}

Seiten: Seiten des Bands in der Datenbank, mit Trennblättern. Segmente: alle Stücke, die beim Trennen entstanden sind. Exemplare: jedes Segment ist ein Exemplar eines Flugblatts, deshalb dieselbe Zahl wie Segmente. Flugblätter: Exemplare zusammengefasst, nur das Hauptexemplar jeder Gruppe, ohne Trennblätter und leere Seiten (sie gehören zu keinem Segment). Nur freigegebene Bände; ein Band ohne Seiten ist angelegt, aber nicht eingelesen.

### Je Bandjahr

{by_band}

Bandjahr: das Jahr, das der Band im Findmittel trägt. Weitere Exemplare: Segmente, die nicht Hauptexemplar ihrer Gruppe sind (Segmente minus Flugblätter), Anteil an den Segmenten; sie zählen im Jahr ihres eigenen Bandes, das Hauptexemplar kann in einem anderen liegen. Zählweise sonst wie oben.

### Je Datierungsjahr

{by_date}

Datierungsjahr: Jahr des Datums auf dem Flugblatt. Zeile „{UNDATED}“: Flugblätter ohne lesbares Datum (in den App-Listen zählen sie im Jahr ihres Bandes). Seiten gibt es hier nicht, sie hängen am Band. Zählweise wie oben.

## Herausgeber und Textsorten

Herausgeber mit mindestens einem Flugblatt: **{number(data['issuers'])}**. Flugblätter ohne erkannten Herausgeber: {number(data['no_issuer'])}, mit einem Herausgeber, der nicht im Register steht: {number(data['unregistered'])} (dieselben Flugblätter zählen bei mehreren Herausgebern mehrfach).

{types}

Herausgeber: Einträge des Registers, bei denen mindestens ein Flugblatt (Hauptexemplar) steht. Textsorte: Feld „Typ“ des Flugblatts (Hauptexemplar), „unklar“ ohne Angabe.

Token: nicht aufgeführt. Die Tokenisierung von pipelines/06_analysis/ngrams.py arbeitet auf den OCR-Dateien (Blocktypen, Silbentrennung), die nicht in der Datenbank liegen; eine Zahl aus den Datenbanktexten wäre anders gezählt.
{END}"""


def replace_block(text, block):
    """Ersetzt den Bereich zwischen den Markern; beim ersten Lauf den alten Block von Hand gepflegter Tabellen."""
    if BEGIN in text:
        start, end = text.index(BEGIN), text.index(END) + len(END)
    else:
        start, end = text.index(FIRST_HEADING), text.index(NEXT_HEADING)
        block += "\n\n"
    return text[:start] + block + text[end:]


def main():
    event.listen(database.engine, "connect", lambda connection, _: connection.execute("PRAGMA query_only = ON"))
    text = DOC.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    text = replace_block(text.replace("\r\n", "\n"), render(compute()))
    DOC.write_bytes(text.replace("\n", newline).encode("utf-8"))


if __name__ == "__main__":
    main()
