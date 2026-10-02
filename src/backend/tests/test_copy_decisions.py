from backend.app.database import copy_decisions

A, B, C, E = ("0118_0002", 9, 10), ("0118_0003", 210, 210), ("0118_0004", 31, 31), ("0118_0004", 50, 51)
KNOWN = {A, B, C, E}


def ref(a):
    return {"volume": a[0], "start_page": a[1], "end_page": a[2]}


def review(at, members, rejected=(), canonical=None):
    return {"members": [ref(a) for a in members], "rejected": [ref(a) for a in rejected],
            "canonical": ref(canonical or members[0]), "at": at}


def groups(auto, lines, known=KNOWN):
    return copy_decisions.resolve(auto, lines, known)[0]


# Tests if unreviewed groups follow the TSV, whatever its group numbers are.
def test_tsv_numbers_do_not_matter():
    first = groups({A: (1, False), B: (1, True)}, [])
    assert first == groups({A: (99, False), B: (99, True)}, [])
    assert first == [{"members": [A, B], "canonical": B, "checked": False, "candidates": []}]


# Tests if a rejected member leaves the group, although the TSV still joins it.
def test_rejected_member():
    auto = {A: (1, True), B: (1, False), C: (1, False)}
    assert groups(auto, [review("2026-10-01T10:00:00", [A, B], [C])]) == [
        {"members": [A, B], "canonical": A, "checked": True, "candidates": []}]


# Tests if the newer review wins, also for the main copy, and a revert brings back the older one.
def test_newer_review_and_revert():
    auto = {A: (1, True), B: (1, False), C: (1, False)}
    old = review("2026-10-01T10:00:00", [A, B], [C])
    new = review("2026-10-01T11:00:00", [A, B, C], canonical=C)
    for lines in ([old, new], [new, old]):
        assert groups(auto, lines)[0]["members"] == [A, B, C]
        assert groups(auto, lines)[0]["canonical"] == C
    undo = {"revert": new["at"], "at": "2026-10-01T12:00:00"}
    assert groups(auto, [old, new, undo])[0]["members"] == [A, B]


# Tests if a review is not applied after a boundary change, and the TSV group shows instead.
def test_changed_boundary():
    moved = ("0118_0002", 9, 11)
    auto = {moved: (1, True), B: (1, False)}
    result, unresolved = copy_decisions.resolve(
        auto, [review("2026-10-01T10:00:00", [A, B])], {moved, B})
    assert len(unresolved) == 1
    assert result == [{"members": [moved, B], "canonical": moved, "checked": False, "candidates": []}]


# Tests if a new automatic hit for a reviewed group is offered, not added.
def test_new_hit_is_candidate():
    auto = {A: (1, True), B: (1, False), E: (1, False)}
    assert groups(auto, [review("2026-10-01T10:00:00", [A, B])]) == [
        {"members": [A, B], "canonical": A, "checked": True, "candidates": [E]}]


# Tests if two reviews sharing a member join, and a split group stays as a suggestion.
def test_join_and_split():
    lines = [review("2026-10-01T10:00:00", [A, B]), review("2026-10-01T10:00:00", [B, C])]
    assert groups({}, lines)[0]["members"] == [A, B, C]
    auto = {A: (1, True), B: (1, False), C: (1, False), E: (1, False)}
    result = groups(auto, [review("2026-10-01T10:00:00", [A, B], [C, E])])
    assert [g["members"] for g in result] == [[C, E], [A, B]]
