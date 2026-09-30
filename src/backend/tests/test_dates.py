from types import SimpleNamespace

from backend.app.app import iso_to_text, list_date


def leaflet(iso, date_type="issued", doc_type="flugblatt", received="", uncertain=False):
    return SimpleNamespace(date_iso=iso, date_type=date_type, doc_type=doc_type,
                           received_date=received, received_uncertain=uncertain)


# Tests if list dates keep the precision of the ISO date and label events.
def test_list_date():
    assert list_date(leaflet("1968-11-14")) == ("14. Nov. 1968", "")
    assert list_date(leaflet("1968-02")) == ("Feb. 1968", "")
    assert list_date(leaflet("1968-07-09", "event")) == ("9. Juli 1968", "Veranstaltung")
    assert list_date(leaflet("1970-06-02", "event", "protokoll")) == ("2. Juni 1970", "")
    assert iso_to_text("1968-07-09") == "9. Juli 1968"
    assert iso_to_text("") is None


# Tests if undated leaflets fall back to the archive stamp, then to the volume year.
def test_list_date_fallback():
    assert list_date(leaflet("", received="1970-06-26"), 1970) == ("26. Juni 1970", "Eingang")
    assert list_date(leaflet("", received="1978-06-22", uncertain=True), 1970) == ("1970", "")
    assert list_date(leaflet("1968-13"), 1968) == ("1968", "")
    assert list_date(leaflet("")) == ("", "")
