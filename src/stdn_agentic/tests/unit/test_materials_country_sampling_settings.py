"""Materials- and country-stage sampling settings must reach the model call (see
test_component_sampling_settings.py for the component stage)."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from stdn_agentic.data.repository import CountryDataRepository
from stdn_agentic.models import STDNDependencies
from stdn_agentic.orchestrator.materials_extractor import MaterialsExtractor

SRC = Path(__file__).resolve().parents[2]


def _deps(**kw):
    base = dict(material_ontology="", material_ontology_dict={}, material_ontology_list=[], years_to_query=[2024],
                client=None, model="openai:gpt-4.1-mini", top_p=1.0, temperature=None)
    base.update(kw)
    return STDNDependencies(**base)


@pytest.mark.asyncio
async def test_materials_single_agent_passes_sampling_settings():
    ex = MaterialsExtractor.__new__(MaterialsExtractor)
    ex.deps = _deps()
    ex.max_retries = 1
    ex.material_no_debate_top_p = 0.0001
    ex.material_no_debate_temperature = 0.03
    ex.materials_agent = MagicMock(run=AsyncMock(return_value=MagicMock(output=MagicMock())))
    await ex._run_materials_agent_with_retries("prompt")
    assert ex.materials_agent.run.call_args.kwargs["model_settings"] == {"top_p": 0.0001, "temperature": 0.03}


@pytest.mark.asyncio
async def test_country_single_agent_passes_sampling_settings():
    repo = CountryDataRepository.__new__(CountryDataRepository)
    repo.deps = _deps()
    repo.top_n = 5
    repo.country_no_debate_top_p = 0.0001
    repo.country_no_debate_temperature = 0.03
    repo.country_agent = MagicMock(run=AsyncMock(return_value=MagicMock(output=None)))
    try:
        await repo.query_llm("Cobalt", 2024)
    except Exception:
        pass
    assert repo.country_agent.run.call_args.kwargs["model_settings"] == {"top_p": 0.0001, "temperature": 0.03}


@pytest.mark.parametrize("rel", ["debate/material_debater.py", "debate/material_country_debater.py"])
def test_debater_agent_runs_pass_model_settings(rel):
    """Every `<agent>.run(prompt, deps=debate_deps...)` in the debaters passes model_settings."""
    tree = ast.parse((SRC / rel).read_text())
    runs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "run"
            and any(k.arg == "deps" and getattr(k.value, "id", "") == "debate_deps" for k in n.keywords)]
    assert runs, f"no debate agent.run calls found in {rel}"
    for call in runs:
        assert any(k.arg == "model_settings" for k in call.keywords), f"{rel}:{call.lineno} lacks model_settings"
