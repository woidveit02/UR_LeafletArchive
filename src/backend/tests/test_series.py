from backend.app.database.fillDatabase import series_key
from backend.app.database.models import Leaflet


# Tests if spelling variants of a series map to the same key.
def test_series_key_variants():
    assert series_key("AStA-Info") == series_key("ASTA INFO") == series_key("ASTA-Info")
    assert series_key("AStA-Info") != series_key("AStA-Information")


# Tests if a leaflet without its own heading is titled by series and issue.
def test_display_title_falls_back_to_series():
    assert Leaflet(title="", series="AStA-Info", issue="Nr. 5").display_title == "AStA-Info, Nr. 5"
    assert Leaflet(title="", series="AStA-Info", issue="").display_title == "AStA-Info"
    assert Leaflet(title="Streik!", series="AStA-Info", issue="").display_title == "Streik!"
    assert Leaflet(title="", series="", issue="").display_title == ""
