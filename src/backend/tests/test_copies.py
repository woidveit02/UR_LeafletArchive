from backend.app.database import fillDatabase


# Tests if copy groups are keyed by volume label and first page.
def test_copy_groups(tmp_path, monkeypatch):
    (tmp_path / "copies.tsv").write_text(
        "gruppe\tkanonisch\tband\tseiten\n"
        "7\tja\tNr. 003 (1969)\t12-13\n"
        "7\tnein\tNr. 004 (1970)\t5\n", encoding="utf-8")
    monkeypatch.setattr(fillDatabase, "DATA_DIR", tmp_path)
    assert fillDatabase.copy_groups() == {("Nr. 003 (1969)", 12): 7, ("Nr. 004 (1970)", 5): 7}
    assert fillDatabase.copy_groups("missing.tsv") == {}
