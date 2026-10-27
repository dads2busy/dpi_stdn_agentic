import csv

from scripts.resolve_materials import fill_countries, load_map, resolve_rows

MAP = "data/material_resolution_map.csv"


def test_map_covers_entire_ontology():
    onto = {r["Elements_Compounds"] for r in csv.DictReader(open("data/hs_codes_and_usgs_names.csv"))}
    mapping = load_map(MAP)
    assert onto - set(mapping) == set()


def test_generic_row_expands_and_keeps_provenance():
    mapping = load_map(MAP)
    rows = [{"technology": "5G", "component": "Antenna", "material": "ceramic", "country": "CHINA", "percentage": "60"}]
    out = resolve_rows(rows, mapping)
    assert {r["material_resolved"] for r in out} == {"Aluminum oxide", "Barium titanate", "Zirconium dioxide"}
    assert all(r["resolution_provenance"] == "map" for r in out)
    assert all(r["country"] == "" for r in out)  # country shares do NOT carry over; refetched in Step 5


def test_identity_row_untouched():
    mapping = load_map(MAP)
    rows = [{"technology": "x", "component": "c", "material": "copper", "country": "CHILE", "percentage": "24"}]
    out = resolve_rows(rows, mapping)
    assert len(out) == 1 and out[0]["resolution_provenance"] == "identity" and out[0]["country"] == "CHILE"


def test_not_material_without_constituent_is_flagged_not_dropped():
    mapping = load_map(MAP)
    rows = [{"technology": "x", "component": "Load cell", "material": "Strain gauge", "country": "JAPAN", "percentage": "50"}]
    out = resolve_rows(rows, mapping)
    assert len(out) == 1
    assert out[0]["material_level"] == "not_material" and out[0]["material_resolved"] == ""
    assert out[0]["country"] == ""


def test_compound_carries_element_constituents():
    mapping = load_map(MAP)
    rows = [{"technology": "5G", "component": "Antenna", "material": "Ceramic", "country": "CHINA", "percentage": "60"}]
    out = {r["material_resolved"]: r for r in resolve_rows(rows, mapping)}
    assert out["Barium titanate"]["material_elements"] == "Barium|Titanium|Oxygen"


def test_expanded_rows_collapse_across_original_country_rows():
    mapping = load_map(MAP)
    rows = [{"technology": "5G", "component": "Antenna", "material": "Ceramic", "country": c, "percentage": p}
            for c, p in [("CHINA", "60"), ("JAPAN", "20")]]
    out = resolve_rows(rows, mapping)
    assert sorted(r["material_resolved"] for r in out) == ["Aluminum oxide", "Barium titanate", "Zirconium dioxide"]


def test_fill_countries_explodes_mapped_rows_and_keeps_misses_blank():
    rows = [
        {"material": "Ceramic", "material_resolved": "Zirconium dioxide", "resolution_provenance": "map", "country": "", "percentage": ""},
        {"material": "Ceramic", "material_resolved": "Barium titanate", "resolution_provenance": "map", "country": "", "percentage": ""},
        {"material": "Copper", "material_resolved": "Copper", "resolution_provenance": "identity", "country": "CHILE", "percentage": "24"},
    ]
    lookup = {"Zirconium dioxide": [{"country": "AUSTRALIA", "percentage": 37.5, "confidence": 0.95, "reasoning": "USGS"},
                                    {"country": "SOUTH AFRICA", "percentage": 26.0, "confidence": 0.95, "reasoning": "USGS"}]}
    out = fill_countries(rows, lambda m: lookup.get(m, []))
    zr = [r for r in out if r["material_resolved"] == "Zirconium dioxide"]
    assert [(r["country"], r["percentage"]) for r in zr] == [("AUSTRALIA", 37.5), ("SOUTH AFRICA", 26.0)]
    assert [r["country"] for r in out if r["material_resolved"] == "Barium titanate"] == [""]
    assert [r["country"] for r in out if r["material_resolved"] == "Copper"] == ["CHILE"]
