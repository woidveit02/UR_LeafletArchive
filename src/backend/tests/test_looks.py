import pymupdf

from backend.app import looks

MM = 72 / 25.4
YELLOW, BLUE = (0.95, 0.92, 0.8), (0.25, 0.3, 0.8)


def scan(path):
    """Three pages: a front with typed lines, a punch hole on the left, the archive's stamp and its blue "F";
    a back with a white hole on the right; an empty page."""
    doc = pymupdf.open()
    for number in range(3):
        page = doc.new_page(width=210 * MM, height=297 * MM)
        page.draw_rect(page.rect, color=None, fill=YELLOW if number < 2 else (1, 1, 1))
        if number < 2:
            for y in range(60, 260, 6):
                page.draw_line((30 * MM, y * MM), (180 * MM, y * MM), color=(0.1, 0.1, 0.1), width=1.2,
                               dashes="[4 2] 0")
    front, back = doc[0], doc[1]
    for y in (110, 190):
        front.draw_circle((14 * MM, y * MM), 3 * MM, color=None, fill=(0, 0, 0))
        back.draw_circle((196 * MM, y * MM), 3 * MM, color=(0.6, 0.6, 0.6), fill=(1, 1, 1))
    front.draw_rect(pymupdf.Rect(100 * MM, 15 * MM, 140 * MM, 35 * MM), color=BLUE, width=2)
    front.insert_text((104 * MM, 27 * MM), "UB eingelaufen", fontsize=11, color=BLUE)
    front.draw_polyline([(170 * MM, 30 * MM), (170 * MM, 18 * MM), (178 * MM, 18 * MM)], color=BLUE, width=2.5)
    front.draw_line((170 * MM, 24 * MM), (176 * MM, 24 * MM), color=BLUE, width=2.5)
    doc.save(path)
    return path


# Tests if a page shows its punch holes (black or white), the archive's blue stamp and mark, and if an empty page
# is blank.
def test_looks_of_a_scan(tmp_path):
    front, back, empty = looks.measure_scan(scan(tmp_path / "scan.pdf"), workers=2)
    assert (front["holes"], back["holes"], empty["holes"]) == ("left", "right", "none")
    assert len(front["spots"]["holes"]) == 2 and all(x < 0.13 for x, y, w, h in front["spots"]["holes"])
    assert len(front["spots"]["blue"]) == 2 and back["spots"]["blue"] == []  # the stamp and the "F"
    assert front["stamp"] and front["sign"] and not back["stamp"] and not back["sign"]
    assert (front["blank"], back["blank"], empty["blank"]) == (False, False, True)
    assert front["paper"][2] < front["paper"][0] and empty["paper"] == [255, 255, 255]
    assert front["size"] == [595, 842]
