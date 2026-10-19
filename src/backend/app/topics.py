"""Topics in the app. Step 7 gives a volume's leaflets the nearest existing topic; "Themen neu berechnen" runs the
model of pipelines/04_topic/leaflet_topics.py again (bge-m3 via OpenRouter, BERTopic, UMAP, HDBSCAN) and leaves a
candidate next to topics.json that is only taken over after its titles were reviewed."""
import hashlib
import json
import logging
import re
import threading
import time
from datetime import datetime

import numpy as np
import requests

from . import copy_search, importer, keys
from .database import fillDatabase
from .database.models import RELEASED, Leaflet, Organization, Topic, Volume

logger = logging.getLogger(__name__)

API = "https://openrouter.ai/api/v1"
EMBED_MODEL = "baai/bge-m3"
LABEL_MODEL = "openai/gpt-4.1-mini"  # the model of the titles of the first run
LEMMA_MODEL = "de_core_news_lg"
ASSIGN, RECOMPUTE = "themen", "themen-neu"  # keys of importer.JOBS
TOPICS, MAP = "topics.json", "topic_map.json"
CANDIDATE, CANDIDATE_MAP = "topics.kandidat.json", "topic_map.kandidat.json"
CACHE = "embeddings.bge-m3.npz"
MAX_CHARS = 16000  # stays below the 8k tokens of bge-m3
MIN_CHARS = 50
BATCH = 32
SEED, MIN_TOPIC_SIZE = 42, 10
NEIGHBOURS = 5  # a new leaflet takes topic and map point from its nearest leaflets
MAJORITY = 0.6  # share of the neighbours' weight its topic needs, else the leaflet is uncertain
UNCERTAIN_BELOW = 10  # percentile: a nearest neighbour less similar than that is for most leaflets makes it uncertain
MAX_TITLE = 120

# not content: archive and imprint words, dates, filler nouns, short forms of election lists (leaflet_topics.py)
EXTRA_STOPWORDS = {
    "daß", "dass", "wurde", "worden", "sowie", "bzw", "xxx", "student", "studenten", "studentin", "kommilitone",
    "universität", "uni", "regensburg", "studentenschaft", "herr", "zeit", "jahr", "frage", "seite", "fall", "punkt",
    "teil", "art", "weise", "grund", "beispiel", "uhr", "januar", "februar", "märz", "april", "mai", "juni", "juli",
    "august", "september", "oktober", "november", "dezember", "montag", "dienstag", "mittwoch", "donnerstag",
    "freitag", "samstag", "sonntag", "ablage", "anlage", "eigendruck", "selbstverlag", "druck", "presserecht", "sem",
    "gesch", "soz", "mitgl", "theol", "phil", "päd", "stud", "abs"}
NOT_ORG_ACRONYMS = {"bhg", "dm", "liste", "mitte"}

# the guidelines the titles of the first run were reviewed by (docs/analyse/themen-titel-vorschlaege.md)
LABEL_PROMPT = """Gib diesem Cluster historischer deutscher Flugblätter (Universität Regensburg, 1967–1973) einen Themenbezeichner.
Regeln:
- 2 bis 6 Wörter, ein Nominalausdruck, nach dem Muster „Gegenstand“ oder „Gegenstand: Aspekt“.
- Den Inhalt benennen, nicht die Textsorte („Diskussion“, „Informationen“, „Proteste und Aktionen“ sagen nichts).
- Nichts, was für fast alle Blätter gilt („an der Universität Regensburg“, „in den 1970er Jahren“).
- Ein Jahr nur, wenn das Thema an ein Ereignis gebunden ist.
- Ein Gegenstand, nicht zwei mit „und“ verbunden.
- Neutral formulieren; Wertungen der Quellen nicht übernehmen.
- Nur die Belege unten nutzen; keine Akteure, Orte, Daten oder Ereignisse erfinden.
Antworte ausschließlich als JSON-Objekt im Format {{"label":"..."}}.

Schlüsselwörter: {words}

{excerpts}"""


def data(name):
    return fillDatabase.DATA_DIR / name


def load(name):
    path = data(name)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def save(name, value):
    tmp = data(name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(data(name))


def is_main(leaflet):
    return leaflet.canonical_leaflet_id in (None, leaflet.id)


def anchor(stem, leaflet):
    return stem, leaflet.start_page, leaflet.end_page


def leaflets(volume=None):
    """anchor -> leaflet: the released volumes, or one volume."""
    query = fillDatabase.session.query(Leaflet, Volume.stem).join(Volume)
    query = query.filter(Volume.id == volume.id) if volume else query.filter(Volume.status == RELEASED)
    return {anchor(stem, lf): lf for lf, stem in query}


def texts(by_anchor):
    """anchor -> the text the topics are computed from, as in leaflet_topics.py; too short ones are left out."""
    return {a: t[:MAX_CHARS] for a, t in copy_search.texts(by_anchor).items() if len(t) >= MIN_CHARS}


def openrouter(key, path, body, attempts=4):
    for attempt in range(attempts):
        try:
            response = requests.post(f"{API}/{path}", json=body, headers={"Authorization": f"Bearer {key}"}, timeout=300)
            if response.status_code in (401, 402, 403, 404) or attempt == attempts - 1:
                response.raise_for_status()
            if response.ok:
                answer = response.json()
                if "error" not in answer:
                    return answer
                if attempt == attempts - 1:
                    raise RuntimeError(answer["error"].get("message", answer["error"]))
        except requests.ConnectionError:
            if attempt == attempts - 1:
                raise
        time.sleep(5 * 2 ** attempt)


def load_cache():
    path = data(CACHE)
    if not path.is_file():
        return {}
    stored = np.load(path)
    return dict(zip(stored["keys"].tolist(), stored["vectors"]))


def save_cache(cache):
    with open(data(CACHE + ".tmp"), "wb") as f:
        np.savez(f, keys=np.array(list(cache)), vectors=np.stack(list(cache.values())))
    data(CACHE + ".tmp").replace(data(CACHE))


def embed(key, values, job):
    """Unit vectors of the texts; known texts come from the cache, the rest from OpenRouter (a few cents a volume)."""
    cache = load_cache()
    ids = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in values]
    missing = [(i, t) for i, t in dict(zip(ids, values)).items() if i not in cache]
    job.update(done=0, total=len(missing), unit="Texte eingebettet")
    for start in range(0, len(missing), BATCH):
        batch = missing[start:start + BATCH]
        answer = openrouter(key, "embeddings", {"model": EMBED_MODEL, "input": [t for _, t in batch]})
        for (i, _), item in zip(batch, sorted(answer["data"], key=lambda d: d["index"])):
            cache[i] = np.asarray(item["embedding"], dtype=np.float32)
        save_cache(cache)
        job["done"] = start + len(batch)
    vectors = np.stack([cache[i] for i in ids]) if ids else np.zeros((0, 1024), dtype=np.float32)
    return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)


def neighbour_topics(known, topics, new):
    """Per new vector: (topic, uncertain), voted by its nearest known leaflets, weighted by similarity. The topics come
    from HDBSCAN, whose clusters are not round, so a topic's centre says little; a near copy takes its twin's topic.
    Uncertain: the neighbours disagree, or even the nearest is less similar than nearest neighbours usually are."""
    nearest = []  # each known leaflet's similarity to its nearest other one, in slices: all pairs at once is n² floats
    for start in range(0, len(known), 2000):
        part = known[start:start + 2000] @ known.T
        part[np.arange(len(part)), np.arange(start, start + len(part))] = -1
        nearest.append(part.max(axis=1))
    floor = np.percentile(np.concatenate(nearest), UNCERTAIN_BELOW) if len(known) > 1 else -1
    sims = new @ known.T
    out = []
    for row in sims:
        near = np.argsort(-row)[:NEIGHBOURS]
        votes = {}
        for i in near:
            votes[topics[i]] = votes.get(topics[i], 0) + max(float(row[i]), 0)
        best = max(votes, key=votes.get)
        out.append((best, bool(votes[best] < MAJORITY * sum(votes.values()) or row[near[0]] < floor)))
    return out


def map_points(known, points, new):
    """Per new vector: the mean map point of its nearest known leaflets."""
    near = np.argsort(-(new @ known.T), axis=1)[:, :NEIGHBOURS]
    return [tuple(round(float(v), 3) for v in np.asarray(points)[n].mean(axis=0)) for n in near]


def spread(by_anchor, values):
    """Gives each copy whose main copy has a value that value: copies are counted once and belong to one topic."""
    by_id = {lf.id: a for a, lf in by_anchor.items()}
    out = dict(values)
    for a, lf in by_anchor.items():
        main = by_id.get(lf.canonical_leaflet_id)
        if a not in out and main in out:
            out[a] = out[main]
    return out


def write_volume(stem, assigned, points):
    """Replaces the volume's rows in topics.json and topic_map.json, then the database follows."""
    doc = load(TOPICS)
    doc.setdefault("assigned_later", {})[stem] = f"{datetime.now():%Y-%m-%d}"  # not part of the run, see Verwaltung > Themen
    doc["leaflets"] = [r for r in doc["leaflets"] if r["volume"] != stem] + [
        {"volume": s, "start_page": a, "end_page": b, "topic": t, "uncertain": u} for (s, a, b), (t, u) in assigned.items()]
    save(TOPICS, doc)
    points_doc = [r for r in load(MAP) or [] if r["stem"] != stem] + [
        {"stem": s, "start_page": a, "end_page": b, "x": x, "y": y} for (s, a, b), (x, y) in points.items()]
    save(MAP, points_doc)
    fillDatabase.fill_topics()
    fillDatabase.fill_topic_map()


def status(volume):
    """What step 7 shows: how many of the volume's leaflets have a topic, and how many of those are uncertain."""
    rows = sorted((lf for lf in leaflets(volume=volume).values() if is_main(lf)), key=lambda lf: lf.start_page)
    with_topic = [lf for lf in rows if lf.topic_id is not None]
    counts = {}
    for lf in with_topic:
        n, unsure = counts.get(lf.topic_id, (0, 0))
        counts[lf.topic_id] = (n + 1, unsure + bool(lf.topic_uncertain))
    titles = {t.id: t.title for t in fillDatabase.session.query(Topic).filter(Topic.id.in_(counts))}
    return {"leaflets": len(rows), "assigned": len(with_topic),
            "uncertain": [(lf, titles.get(lf.topic_id)) for lf in with_topic if lf.topic_uncertain],
            "topics": sorted(((t, titles.get(t, t), n, unsure) for t, (n, unsure) in counts.items()), key=lambda r: (-r[2], r[1])),
            "ready": load(TOPICS) is not None}


def start_assign(volume):
    key = keys.get("openrouter")
    if not key:
        raise ValueError("Es fehlt der Zugang zu OpenRouter. Bitte unten den API-Key eintragen.")
    if not importer.n_leaflets(volume):
        raise ValueError("Zuerst die Flugblätter in Schritt 6 vorbereiten.")
    if load(TOPICS) is None:
        raise ValueError("Es gibt noch keine Themen. Sie werden einmal unter „Themen neu berechnen“ erzeugt.")
    if importer.running(volume, ASSIGN):
        raise ValueError("Die Themen werden gerade zugeordnet. Bitte warten.")
    if importer.JOBS.get((0, RECOMPUTE), {}).get("state") == "running":
        raise ValueError("Die Themen werden gerade neu berechnet. Bitte warten.")
    job = importer.JOBS[(volume.vz, ASSIGN)] = {"state": "running", "done": 0, "total": 0, "error": "",
                                               "started": time.time(), "parts": [], "unit": "Texte eingebettet"}

    def go():
        try:
            mine = leaflets(volume=volume)
            others = {a: lf for a, lf in leaflets().items() if a[0] != volume.stem and lf.topic_id is not None and is_main(lf)}
            new, known = texts({a: lf for a, lf in mine.items() if is_main(lf)}), texts(others)
            vectors = embed(key, list(known.values()) + list(new.values()), job)
            old, fresh = vectors[:len(known)], vectors[len(known):]
            topics = dict(zip(new, neighbour_topics(old, [others[a].topic_id for a in known], fresh)))
            placed = [i for i, a in enumerate(known) if others[a].x is not None]
            known_xy = [(others[a].x, others[a].y) for a in known]
            points = dict(zip(new, map_points(old[placed], [known_xy[i] for i in placed], fresh))) if placed else {}
            # a copy whose main copy is in another volume takes that leaflet's topic and point
            everything = {**others, **mine}
            topics = spread(everything, {**{a: (lf.topic_id, bool(lf.topic_uncertain)) for a, lf in others.items()}, **topics})
            points = spread(everything, {**{a: (lf.x, lf.y) for a, lf in others.items() if lf.x is not None}, **points})
            write_volume(volume.stem, {a: v for a, v in topics.items() if a in mine}, {a: v for a, v in points.items() if a in mine})
            job["state"] = "done"
        except Exception as error:
            job.update(state="error", error=explain(error))

    threading.Thread(target=go, daemon=True).start()


def explain(error):
    code = getattr(getattr(error, "response", None), "status_code", None)
    if code in (401, 403):
        return "OpenRouter hat den API-Key abgelehnt. Bitte einen anderen eintragen."
    if code == 402:
        return "Das Guthaben bei OpenRouter ist aufgebraucht. Schon geholte Embeddings bleiben gespeichert."
    if code in (400, 404):
        return "OpenRouter kennt das gewählte Sprachmodell nicht (mehr), oder es kann so nicht antworten. Bitte ein anderes wählen."
    logger.exception("topics failed")
    return f"Die Themen wurden unterbrochen ({error}). Schon geholte Embeddings bleiben gespeichert; ein neuer Start setzt fort."


# --- "Themen neu berechnen" ---------------------------------------------------------------------------------------

def stopwords():
    """German stopwords, the words above and short forms of organizations (RCDS, SHB ...): they would make topics of
    senders instead of subjects. Names written out stay, else words like "Studentenwerk" went with them."""
    import stop_words
    words = {w.lower() for w in stop_words.get_stop_words("german")} | EXTRA_STOPWORDS
    for org in fillDatabase.session.query(Organization):
        for name in [org.name or "", *(org.variants or [])]:
            words |= {t.lower() for t in re.findall(r"[^\W\d_]+", name) if len(t) <= 5 and sum(c.isupper() for c in t) >= 2}
    return words - NOT_ORG_ACRONYMS


def nouns(values):
    import spacy
    nlp = spacy.load(LEMMA_MODEL, disable=["ner", "parser"])
    nlp.max_length = MAX_CHARS * 2
    return [" ".join(t.lemma_.lower() for t in doc if t.pos_ == "NOUN" and t.is_alpha and len(t) >= 3)
            for doc in nlp.pipe(values, batch_size=16)]


def topic_words(terms, stop, limit=10):
    return [term for term, _ in terms if (tokens := re.findall(r"(?u)[^\W\d_]{3,}", term.lower()))
            and not any(t in stop for t in tokens)][:limit]


def central(vectors, members, limit=5):
    """The members nearest the topic's centre, nearest first."""
    own = vectors[members]
    centre = own.mean(axis=0)
    return [int(i) for i in np.asarray(members)[np.argsort(-(own @ (centre / np.linalg.norm(centre))))[:limit]]]


def excerpts(values, vectors, members, limit=3):
    """The texts nearest the topic's centre, for its title."""
    return [re.sub(r"\s+", " ", values[i])[:700] for i in central(vectors, members, limit)]


def label(key, model, words, texts_):
    prompt = LABEL_PROMPT.format(words=", ".join(words),
                                 excerpts="\n\n".join(f"Auszug {i}: {t}" for i, t in enumerate(texts_, 1)))
    answer = openrouter(key, "chat/completions", {"model": model, "temperature": 0,
                                                  "messages": [{"role": "user", "content": prompt}]})
    content = answer["choices"][0]["message"]["content"] or ""
    match = re.search(r"\{.*\}", content, re.S)
    title = re.sub(r"\s+", " ", (json.loads(match.group()) if match else {}).get("label", "")).strip()
    return title[:MAX_TITLE]


def compute(key, values, vectors, n_topics, label_model, job):
    """The run of leaflet_topics.py --num-topics N --reduce-outliers --label-model M, for the given texts.
    -> (topics [{id, title, llm_label, words}], per text (topic, uncertain), per text map point)."""
    from bertopic import BERTopic
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    job.update(done=0, total=0, unit="", phase="Themenwörter vorbereiten")
    docs = nouns(values)
    stop = stopwords()
    job["phase"] = "Themen berechnen"
    model = BERTopic(umap_model=UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=SEED),
                     vectorizer_model=CountVectorizer(stop_words=sorted(stop), token_pattern=r"(?u)\b[^\W\d_]{3,}\b",
                                                      ngram_range=(1, 2), min_df=3, max_df=0.9),
                     min_topic_size=MIN_TOPIC_SIZE, nr_topics=n_topics,
                     language="multilingual")  # else BERTopic strips everything but A-Z: "universität" -> "universitt"
    found, _ = model.fit_transform(docs, embeddings=vectors)
    placed = model.reduce_outliers(docs, found, strategy="distributions", embeddings=vectors) if -1 in found else found
    uncertain = [bool(old == -1 and new != -1) for old, new in zip(found, placed)]
    placed = [int(t) for t in placed]
    model.update_topics(docs, topics=placed)

    ids = sorted({t for t in placed if t != -1})
    job.update(phase="Titel vorschlagen", done=0, total=len(ids), unit="Titel")
    topics, failed = [], 0
    for t in ids:
        words = topic_words(model.get_topic(t), stop)
        own = [i for i, p in enumerate(placed) if p == t]
        try:
            title = label(key, label_model, words, excerpts(values, vectors, own))
        except Exception as error:
            if getattr(getattr(error, "response", None), "status_code", None) in (400, 401, 402, 403, 404):
                raise  # model gone, key refused, no credit: every title would fail
            failed += 1
            logger.warning("topic title %s failed: %s", t, error)
            if failed > len(ids) // 4:  # a run with keyword titles is no proposal worth reviewing
                raise RuntimeError(f"{failed} Titelvorschläge sind fehlgeschlagen, zuletzt: {error}") from error
            title = ""  # a few missing titles are filled in by hand on the review page
        topics.append({"id": t, "title": title or " / ".join(w.capitalize() for w in words[:3]),
                       "title_source": "llm_label", "llm_label": title, "words": words[:7]})
        job["done"] += 1
    job.update(phase="Karte berechnen", done=0, total=0, unit="")
    xy = UMAP(n_neighbors=15, n_components=2, min_dist=0.1, metric="cosine", random_state=SEED).fit_transform(vectors)
    return topics, list(zip(placed, uncertain)), [(round(float(x), 3), round(float(y), 3)) for x, y in xy]


def label_model_used():
    """The model of the current titles' proposals: named in the run of the app, else the one of the first run."""
    doc = load(TOPICS)
    match = re.search(r"Titel (\S+)$", doc["run"]) if doc else None
    return match.group(1) if match else LABEL_MODEL


def label_costs(n_topics):
    """{model id: estimated dollars for the titles}, strongest first: per topic the prompt with three excerpts, a short answer."""
    from . import metadata
    prompt_tokens = (len(LABEL_PROMPT) + 3 * 700 + 150) / metadata.CHARS_PER_TOKEN
    return {m: n_topics * (prompt_tokens * p_in + 40 * p_out) for m, _, p_in, p_out in metadata.models()}


def label_prices(n_topics):
    from . import ocr
    return {m: "etwa " + ocr.dollar(cost) for m, cost in label_costs(n_topics).items()}


def label_model_choice(n_topics, budget=0.10):
    """(model to preselect, whether the model of the current titles is gone from OpenRouter). Instead of a model that is
    gone: the strongest one within the budget, else the cheapest; not the strongest of all, which can cost dollars."""
    used, costs = label_model_used(), label_costs(n_topics)
    if not costs or used in costs:
        return used, False
    within = [m for m, c in costs.items() if c <= budget]
    return (within[0] if within else min(costs, key=costs.get)), True


def start_recompute(n_topics, label_model):
    key = keys.get("openrouter")
    if not key:
        raise ValueError("Es fehlt der Zugang zu OpenRouter. Den API-Key unter Verwaltung › API-Keys eintragen.")
    if not 5 <= n_topics <= 100:
        raise ValueError("Die Zahl der Themen muss zwischen 5 und 100 liegen.")
    if not re.match(r"^[\w.-]+/[\w.:-]+$", label_model or ""):
        raise ValueError("Bitte ein Modell für die Titel angeben, etwa „openai/gpt-4.1-mini“.")
    from . import metadata
    known = [m[0] for m in metadata.models()]  # empty when OpenRouter cannot be reached; then the run finds out
    if known and label_model not in known:
        raise ValueError(f"OpenRouter kennt das Modell „{label_model}“ nicht (mehr). Bitte ein anderes wählen.")
    if any(j.get("state") == "running" for (_, kind), j in importer.JOBS.items() if kind in (ASSIGN, RECOMPUTE)):
        raise ValueError("Die Themen werden gerade berechnet. Bitte warten.")
    job = importer.JOBS[(0, RECOMPUTE)] = {"state": "running", "done": 0, "total": 0, "error": "", "phase": "Embeddings holen",
                                           "started": time.time(), "parts": [], "unit": "Texte eingebettet"}

    def go():
        try:
            everything = leaflets()
            main = texts({a: lf for a, lf in everything.items() if is_main(lf)})
            vectors = embed(key, list(main.values()), job)
            topics, placed, xy = compute(key, list(main.values()), vectors, n_topics, label_model, job)
            assigned = spread(everything, {a: (t, u) for a, (t, u) in zip(main, placed) if t != -1})
            points = spread(everything, dict(zip(main, xy)))
            save(CANDIDATE, {"run": f"{EMBED_MODEL}, {len(topics)} Themen, seed {SEED}, {datetime.now():%Y-%m-%d}, Titel {label_model}",
                             "topics": topics,
                             "leaflets": [{"volume": s, "start_page": a, "end_page": b, "topic": t, "uncertain": u}
                                          for (s, a, b), (t, u) in assigned.items()]})
            save(CANDIDATE_MAP, [{"stem": s, "start_page": a, "end_page": b, "x": x, "y": y} for (s, a, b), (x, y) in points.items()])
            job["state"] = "done"
        except Exception as error:
            job.update(state="error", error=explain(error))

    threading.Thread(target=go, daemon=True).start()


def members(doc):
    out = {}
    for r in doc["leaflets"]:
        if r["topic"] is None or r["topic"] == -1:  # no topic
            continue
        out.setdefault(r["topic"], set()).add((r["volume"], r["start_page"], r["end_page"]))
    return out


def review():
    """Per topic of the candidate, titled by the model: the old topic most of its leaflets come from, and the old
    topics that came apart. Titles start from scratch; the old ones are only shown."""
    candidate, current = load(CANDIDATE), load(TOPICS)
    if candidate is None:
        return None
    found = leaflets()
    main = {a for a, lf in found.items() if is_main(lf)}  # counted like everywhere else: each leaflet once
    new = {t: m & main for t, m in members(candidate).items()}
    old = {t: m & main for t, m in members(current).items()} if current else {}
    old_titles = {t["id"]: t["title"] for t in current["topics"]} if current else {}
    rows = []
    for topic in candidate["topics"]:
        mine = new.get(topic["id"], set())
        source = max(old, key=lambda t: len(mine & old[t]), default=None)  # where most of its leaflets come from
        rows.append({**topic, "count": len(mine), "old": old_titles.get(source), "old_count": len(old.get(source, ())),
                     "stay": len(mine & old.get(source, set()))})
    rows.sort(key=lambda r: -r["count"])
    split = []  # old topics of which no new topic holds more than half: they came apart
    for t, m in old.items():
        heir = max(rows, key=lambda r: len(m & new.get(r["id"], set())), default=None)
        most = len(m & new.get(heir["id"], set())) if heir else 0
        if m and most <= len(m) / 2:
            split.append({"title": old_titles[t], "count": len(m), "heir": heir["title"] if heir else None, "most": most})
    split.sort(key=lambda d: -d["count"])
    titles_by = re.search(r"Titel (\S+)$", candidate.get("run", ""))
    return {"topics": rows, "split": split, "leaflets": sum(len(m) for m in new.values()),
            "label_model": titles_by.group(1) if titles_by else None}


def candidate_leaflets(topic_id):
    """(topic of the candidate, its leaflets once each, by volume and page), for the list on the review page."""
    candidate = load(CANDIDATE)
    topic = next((t for t in candidate["topics"] if t["id"] == topic_id), None) if candidate else None
    if topic is None:
        return None, []
    found = leaflets()
    return topic, [found[a] for a in sorted(members(candidate).get(topic_id, set())) if a in found and is_main(found[a])]


def accept(titles):
    """titles: topic id -> title from the review page. The current files are kept as topics.bis-<time>.json."""
    candidate, map_ = load(CANDIDATE), load(CANDIDATE_MAP)
    if candidate is None:
        raise ValueError("Es gibt kein neu berechnetes Ergebnis.")
    for topic in candidate["topics"]:
        title = re.sub(r"\s+", " ", titles.get(topic["id"], "")).strip()[:MAX_TITLE]
        if title and title != topic["title"]:
            topic["title"], topic["title_source"] = title, "manual"
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    for name in (TOPICS, MAP):
        if data(name).is_file():
            data(name).replace(data(name.replace(".json", f".bis-{stamp}.json")))
    save(TOPICS, candidate)
    save(MAP, map_)
    discard()
    fillDatabase.fill_topics()
    fillDatabase.fill_topic_map()


def discard():
    for name in (CANDIDATE, CANDIDATE_MAP):
        data(name).unlink(missing_ok=True)


def rename(topic_id, title):
    title = re.sub(r"\s+", " ", title).strip()
    if not title or len(title) > MAX_TITLE:
        raise ValueError(f"Der Titel muss zwischen 1 und {MAX_TITLE} Zeichen lang sein.")
    doc = load(TOPICS)
    topic = next((t for t in doc["topics"] if t["id"] == topic_id), None) if doc else None
    if topic is None:
        raise ValueError("Dieses Thema gibt es nicht.")
    topic["title"], topic["title_source"] = title, "manual"
    save(TOPICS, doc)
    row = fillDatabase.session.get(Topic, topic_id)
    row.title, row.source = title, "manual"
    fillDatabase.session.commit()
