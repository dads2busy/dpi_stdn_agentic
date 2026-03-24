import pytest
from stdn_agentic.agents.process_consumables_agent import (
    ProcessConsumable,
    ProcessConsumablesList,
    JudgeAction,
    JudgeVerdict,
    JudgeOutput,
)


class TestProcessConsumableModels:
    def test_process_consumable_creation(self):
        pc = ProcessConsumable(
            name="Helium",
            confidence=0.85,
            reasoning="Carrier gas in CVD processes",
        )
        assert pc.name == "Helium"
        assert pc.confidence == 0.85

    def test_process_consumable_confidence_bounds(self):
        with pytest.raises(Exception):
            ProcessConsumable(name="X", confidence=1.5, reasoning="test")
        with pytest.raises(Exception):
            ProcessConsumable(name="X", confidence=-0.1, reasoning="test")

    def test_process_consumables_list(self):
        items = [
            ProcessConsumable(name="Helium", confidence=0.85, reasoning="CVD gas"),
            ProcessConsumable(name="Sulfuric Acid", confidence=0.7, reasoning="Etchant"),
        ]
        pcl = ProcessConsumablesList(materials=items)
        assert len(pcl.materials) == 2

    def test_judge_verdict_keep(self):
        v = JudgeVerdict(
            name="Helium",
            action=JudgeAction.KEEP,
            confidence=0.85,
            justification="Universal process gas for semiconductor fabs",
        )
        assert v.action == JudgeAction.KEEP

    def test_judge_verdict_add_caps_confidence(self):
        v = JudgeVerdict(
            name="Neon",
            action=JudgeAction.ADD,
            confidence=0.65,
            justification="Used in lithography laser gas mixtures",
        )
        assert v.action == JudgeAction.ADD
        assert v.confidence <= 0.7

    def test_judge_output(self):
        verdicts = [
            JudgeVerdict(name="Helium", action=JudgeAction.KEEP, confidence=0.85, justification="ok"),
            JudgeVerdict(name="Water", action=JudgeAction.REMOVE, confidence=0.0, justification="too generic"),
            JudgeVerdict(name="Neon", action=JudgeAction.ADD, confidence=0.6, justification="laser gas"),
        ]
        jo = JudgeOutput(verdicts=verdicts)
        assert len(jo.verdicts) == 3
        assert len(jo.kept_and_added) == 2


from stdn_agentic.agents.process_consumables_agent import (
    EXTRACTION_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    get_extraction_agent,
    get_judge_agent,
)


class TestProcessConsumablePrompts:
    def test_extraction_prompt_excludes_constituent_materials(self):
        assert "do not become part of the final product" in EXTRACTION_SYSTEM_PROMPT.lower() or \
               "do NOT include materials that physically constitute" in EXTRACTION_SYSTEM_PROMPT

    def test_extraction_prompt_mentions_process_categories(self):
        prompt_lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert "process gas" in prompt_lower or "gases" in prompt_lower
        assert "cleaning" in prompt_lower or "sterilization" in prompt_lower
        assert "solvent" in prompt_lower

    def test_judge_prompt_allows_additions(self):
        assert "add" in JUDGE_SYSTEM_PROMPT.lower()
        assert "0.7" in JUDGE_SYSTEM_PROMPT

    def test_judge_prompt_requires_justification(self):
        assert "justification" in JUDGE_SYSTEM_PROMPT.lower() or \
               "rationale" in JUDGE_SYSTEM_PROMPT.lower()


class TestAgentFactories:
    def test_get_extraction_agent_returns_agent(self):
        agent = get_extraction_agent(model_name="openai:gpt-4.1-mini")
        assert agent is not None

    def test_get_judge_agent_returns_agent(self):
        agent = get_judge_agent(model_name="openai:gpt-4.1-mini")
        assert agent is not None
