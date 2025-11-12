"""Quick test of agent initialization"""
from stdn_agentic.agents import (
    get_component_agent,
    get_materials_agent, 
    get_country_data_agent,
    AgentFactory
)

print("Testing agent initialization...")

# Test individual agents
component_agent = get_component_agent()
print(f"✓ Component agent: {type(component_agent)}")

materials_agent = get_materials_agent()
print(f"✓ Materials agent: {type(materials_agent)}")

country_agent = get_country_data_agent()
print(f"✓ Country agent: {type(country_agent)}")

# Test factory
factory = AgentFactory()
print(f"✓ Factory created: {factory}")

agents = factory.create_all_agents()
print(f"✓ Factory created {len(agents)} agents: {list(agents.keys())}")

print("\n✓ All agents initialized successfully!")
