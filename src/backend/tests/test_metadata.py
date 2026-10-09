import json

from backend.app import metadata


class Answer:
    def __init__(self, status, body):
        self.ok, self.status_code, self.body = status == 200, status, body
        self.text = json.dumps(body)

    def raise_for_status(self):
        assert self.ok

    def json(self):
        return self.body


PAGES = [[("Text", "AStA informiert"), ("Text", "Mensa-Preise steigen"), ("Picture", "Stempel: eingelaufen am 3. FEB. 1973")],
         [("Text", "Verantwortlich: Hans Huber")],
         [("Text", "RCDS"), ("Text", "Wahlaufruf")]]
SEGS = [{"id": 1, "start_page": 1, "end_page": 2}, {"id": 2, "start_page": 3, "end_page": 3}]
RECORD = {"id": 1, "title_evidence": "Mensa-Preise steigen", "title_blocks": ["1-2"], "title": "Mensa-Preise steigen",
          "title_type": "original", "series": "", "issue": "", "date_evidence": "", "date_blocks": [], "date_text": "",
          "date_iso": "", "date_type": "undated", "doc_type": "flugblatt", "confidence": 0.9,
          "issuers": [{"evidence": "AStA informiert", "blocks": ["1-1"], "surface": "AStA", "role": "issuer",
                       "function": "", "marker": ""},
                      {"evidence": "Verantwortlich: Hans Huber", "blocks": ["2-1"], "surface": "Hans Huber",
                       "role": "signatory", "function": "", "marker": "Verantwortlich"}]}


# Tests a volume end to end: the strict format falls back when no provider takes it, the answers are kept, a second
# run asks for nothing, a leaflet missing from the answer is asked again alone, and the stamp and group ids are filled.
def test_run(tmp_path, monkeypatch):
    calls = []

    def post(url, **kw):
        body = kw["json"]
        calls.append(body)
        if body["response_format"]["type"] == "json_schema" and body["response_format"]["json_schema"]["strict"]:
            return Answer(404, {"error": {"message": "No endpoints found that can handle the requested parameters"}})
        ids = [int(i) for i in body["messages"][0]["content"].rsplit("Erwartete ids in dieser Antwort: ", 1)[1]
               .split(".")[0].split(", ")]
        results = [RECORD] if ids != [2] else [{**RECORD, "id": 2, "title": "Wahlaufruf", "title_evidence": "Wahlaufruf",
                                                "title_blocks": ["3-2"], "issuers": []}]
        return Answer(200, {"choices": [{"message": {"content": json.dumps({"results": results})}}],
                            "usage": {"cost": 0.01}})

    monkeypatch.setattr(metadata.requests, "post", post)
    forms = metadata.registry([("asta", "AStA", "Allgemeiner Studentenausschuss"), ("rcds", "RCDS", "")])
    checkpoint, job = tmp_path / "antworten.jsonl", {}
    doc = metadata.run(SEGS, PAGES, 1973, "key", "some/model", ["AStA"], forms, checkpoint, job, template="AUFGABE")
    first, second = doc["segments"]
    assert [c["response_format"]["type"] for c in calls][:2] == ["json_schema", "json_schema"]
    assert first["title"] == "Mensa-Preise steigen" and first["received_date"] == "1973-02-03"
    assert first["issuers"][0]["org_ids"] == ["asta"] and first["_grounding"] == []
    assert second["title"] == "Wahlaufruf" and second["_retried_missing"] and job["cost"] > 0
    asked = len(calls)
    assert metadata.run(SEGS, PAGES, 1973, "key", "some/model", [], forms, checkpoint)["segments"][0]["title"]
    assert len(calls) == asked


# Tests if a model OpenRouter no longer lists is not offered, also not the default.
def test_top_models(monkeypatch):
    monkeypatch.setattr(metadata, "models", lambda: [("x/a", "A", 0, 0), ("x/b", "B", 0, 0)])
    assert metadata.top_models([("x/a", 2), ("x/gone", 1)], n=2) == [
        ("Bisher verwendet", [("x/a", "A · 2 Bände")]), ("Weitere Modelle", [("x/b", "B")])]
    monkeypatch.setattr(metadata, "models", lambda: [])  # offline: what was used stays
    assert metadata.top_models([]) == [("Bisher verwendet", [(metadata.DEFAULT_MODEL, metadata.DEFAULT_MODEL)])]


# Tests the edited instructions: kept in their own file, the shipped text (or nothing) removes it, batches follow the size.
def test_prompt_and_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(metadata, "custom_prompt_file", lambda: tmp_path / "p.txt")
    assert metadata.prompt_text() == metadata.default_prompt()
    metadata.save_prompt("Eigene Regeln\r\nzwei")
    assert metadata.prompt_text() == "Eigene Regeln\nzwei\n"
    metadata.save_prompt(metadata.default_prompt())
    assert not (tmp_path / "p.txt").exists()
    job = {}
    monkeypatch.setattr(metadata, "extract", lambda *a: (_ for _ in ()).throw(RuntimeError("stop")))
    try:
        metadata.run(SEGS, PAGES, 1973, "key", "m/x", [], {}, tmp_path / "c.jsonl", job, batch_size=1)
    except RuntimeError:
        pass
    assert len(job["parts"]) == 2
