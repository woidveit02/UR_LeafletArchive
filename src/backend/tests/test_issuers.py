from backend.app.database.fillDatabase import issuer_org_ids

VARIANTS = {"rcds": "rcds"}
KNOWN = {"rcds", "lsd", "shb", "sds"}


# Tests if org_ids from the pipeline are used, including joint issuers.
def test_org_ids_from_metadata():
    issuer = {"surface": "LSD, SHB und SDS Regensburg", "org_ids": ["lsd", "sds", "shb"]}
    assert issuer_org_ids(issuer, VARIANTS, KNOWN) == ["lsd", "sds", "shb"]


# Tests if unknown or missing org_ids leave the issuer unresolved.
def test_unknown_org_ids_stay_unresolved():
    assert issuer_org_ids({"surface": "ND-Hochschulring", "org_ids": []}, VARIANTS, KNOWN) == [None]
    assert issuer_org_ids({"surface": "X", "org_ids": ["gibt_es_nicht"]}, VARIANTS, KNOWN) == [None]


# Tests if older metadata without org_ids falls back to the variant lookup.
def test_variant_lookup_for_older_metadata():
    assert issuer_org_ids({"surface": " RCDS "}, VARIANTS, KNOWN) == ["rcds"]
    assert issuer_org_ids({"surface": "Hans Heimerl"}, VARIANTS, KNOWN) == [None]
