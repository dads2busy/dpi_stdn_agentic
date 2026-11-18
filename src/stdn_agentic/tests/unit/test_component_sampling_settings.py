"""Component-stage sampling settings (temperature, top_p) must reach the model call.

Before 2026-11-18 they were stored on STDNDependencies but never passed to pydantic-ai, so every run used the
provider defaults whatever the config said.
"""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from stdn_agentic.models import STDNDependencies
from stdn_agentic.orchestrator.component_extractor import ComponentExtractor


def _deps(**kw):
    base = dict(material_ontology="", material_ontology_dict={}, material_ontology_list=[], years_to_query=[2024],
                client=None, model="openai:gpt-4.1-mini", top_p=1.0, temperature=None)
    base.update(kw)
    return STDNDependencies(**base)


def test_sampling_settings_includes_set_values():
    assert _deps(top_p=0.0001, temperature=0.03).sampling_settings() == {"top_p": 0.0001, "temperature": 0.03}


def test_sampling_settings_omits_unset_temperature():
    assert _deps(top_p=0.5, temperature=None).sampling_settings() == {"top_p": 0.5}


@pytest.mark.asyncio
async def test_single_agent_extraction_passes_sampling_settings():
    ex = ComponentExtractor.__new__(ComponentExtractor)
    ex.deps = _deps()
    ex.component_no_debate_top_p = 0.0001
    ex.component_no_debate_temperature = 0.03
    out = SimpleNamespace(component_list=[], technology_specification="", technology_reasoning="")
    result = MagicMock(output=out)
    result.usage.return_value = None
    ex.component_agent = MagicMock(run=AsyncMock(return_value=result))
    ex.reporter = None
    try:
        await ex.extract_components_simple("Widget", MagicMock())
    except Exception:
        pass
    kwargs = ex.component_agent.run.call_args.kwargs
    assert kwargs["model_settings"] == {"top_p": 0.0001, "temperature": 0.03}
