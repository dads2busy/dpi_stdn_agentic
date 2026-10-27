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


def test_steel_ingots_kept_as_usgs_commodity_with_elements():
    mapping = load_map(MAP)
    rows = [{"technology": "x", "component": "Frame", "material": "Steel Ingots", "country": "CHINA", "percentage": "54"}]
    out = resolve_rows(rows, mapping)
    assert len(out) == 1 and out[0]["resolution_provenance"] == "identity" and out[0]["country"] == "CHINA"
    assert out[0]["material_elements"] == "Iron|Carbon|Manganese"


def test_glass_resolves_to_supply_feedstocks():
    mapping = load_map(MAP)
    rows = [{"technology": "x", "component": "Display", "material": "Glass", "country": "CHINA", "percentage": "40"}]
    assert {r["material_resolved"] for r in resolve_rows(rows, mapping)} == {
        "Silicon dioxide", "Soda ash", "Calcium carbonate", "Boron"}


def test_mapped_rows_take_constituent_hs_code_exactly():
    mapping = load_map(MAP)
    rows = [{"technology": "5G", "component": "Antenna", "material": "Ceramic", "hs_code": "690990", "country": "CHINA", "percentage": "60"}]
    out = {r["material_resolved"]: r for r in resolve_rows(rows, mapping, hs_codes={"Barium titanate": "284190"})}
    assert out["Barium titanate"]["hs_code"] == "284190"
    assert out["Aluminum oxide"]["hs_code"] == ""


def test_fill_countries_records_country_source():
    rows = [
        {"material_resolved": "Tin", "resolution_provenance": "map", "country": "", "percentage": ""},
        {"material_resolved": "Barium titanate", "resolution_provenance": "map", "country": "", "percentage": ""},
        {"material_resolved": "Potassium", "resolution_provenance": "map", "country": "", "percentage": ""},
        {"material_resolved": "Copper", "resolution_provenance": "identity", "country": "CHILE", "percentage": "24"},
    ]
    data = {"Tin": [{"country": "CHINA", "percentage": 23.4, "source": "usgs"}],
            "Barium titanate": [{"country": "China", "percentage": 70.0, "source": "llm_cache"}]}
    out = {r["material_resolved"]: r["country_source"] for r in fill_countries(rows, lambda m: data.get(m, []))}
    assert out == {"Tin": "usgs", "Barium titanate": "llm_cache", "Potassium": "", "Copper": "original"}


def test_node_shares_count_each_material_node_once():
    from scripts.material_resolution_report import node_shares
    src_level = {"glass": "generic", "epoxy resins": "generic", "copper": "element"}
    resolved = [
        {"technology": "t", "component": "c", "material": "Glass", "material_resolved": n, "material_level": "compound"}
        for n in ["Silicon dioxide", "Soda ash", "Calcium carbonate"]
    ] + [{"technology": "t", "component": "c", "material": "Glass", "material_resolved": "Boron", "material_level": "element"},
         {"technology": "t", "component": "c", "material": "Epoxy resins", "material_resolved": "Epoxy resins", "material_level": "generic"},
         {"technology": "t", "component": "c", "material": "Copper", "material_resolved": "Copper", "material_level": "element"}]
    before, after = node_shares(resolved, src_level)
    assert before == 1 / 3   # only Copper is element/compound as extracted
    assert after == 2 / 3    # Glass now fully resolves; Epoxy stays generic
