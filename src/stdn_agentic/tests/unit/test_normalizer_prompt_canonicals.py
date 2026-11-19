from scripts.normalize_outputs_global_granularity import (
    build_granularity_prompt,
    make_vocab_key,
    tech_canonicals,
)

SENTINEL = "__NON_PRIMARY__"


def test_tech_canonicals_uses_only_this_technologys_mapped_names():
    mapping = {
        make_vocab_key("li-ion battery", "Phone", "global"): "Lithium-ion Battery",
        make_vocab_key("box", "Phone", "global"): SENTINEL,
        make_vocab_key("aardvark pump", "Bioreactor", "global"): "Aardvark Pump",
    }
    got = tech_canonicals(["Li-ion Battery", "Box", "Unseen Part"], "Phone", mapping, "global", SENTINEL)
    assert got == ["Lithium-ion Battery"]


def test_prompt_shows_every_canonical_not_an_alphabetical_prefix():
    canon = [f"Zeta Component {i:03d}" for i in range(150)] + ["Aardvark Pump"]
    prompt = build_granularity_prompt(["Display Panel"], SENTINEL, existing_canonicals=canon, technology="Phone")
    assert all(c in prompt for c in canon)


def test_prompt_never_offers_the_sentinel_as_a_canonical_example():
    prompt = build_granularity_prompt(["Display Panel"], SENTINEL, existing_canonicals=[SENTINEL, "Display"])
    examples = prompt.split("EXISTING CANONICAL PRIMARY COMPONENT NAMES")[1].split("RAW NAMES")[0]
    assert SENTINEL not in examples and "Display" in examples
