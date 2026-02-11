"""Quick test of agent initialization"""

from stdn_agentic.agents import (
    AgentFactory,
    get_component_agent,
    get_country_data_agent,
    get_materials_agent,
)
from stdn_agentic.dependencies import initialize_dependencies
from stdn_agentic.models import ConfigModel

print("Testing agent initialization...")

# Build dependencies so AgentFactory can consistently use per-agent models
config = ConfigModel(
    import_tech_list="./data/tech_list.csv",
    model="openai:gpt-4.1-mini",
)
deps = initialize_dependencies(config)

# Test individual agents (still allowed to use defaults/env)
component_agent = get_component_agent()
print(f"✓ Component agent: {type(component_agent)}")

materials_agent = get_materials_agent()
print(f"✓ Materials agent: {type(materials_agent)}")

country_agent = get_country_data_agent()
print(f"✓ Country agent: {type(country_agent)}")

# Test factory (requires deps)
factory = AgentFactory(deps)
print(f"✓ Factory created: {factory}")

agents = factory.create_all_agents()
print(f"✓ Factory created {len(agents)} agents: {list(agents.keys())}")

print("\n✓ All agents initialized successfully!")
