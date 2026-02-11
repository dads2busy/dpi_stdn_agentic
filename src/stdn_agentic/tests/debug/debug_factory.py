"""Test AgentFactory functionality"""

from stdn_agentic.agents import AgentFactory
from stdn_agentic.dependencies import initialize_dependencies
from stdn_agentic.models import ConfigModel

# Build dependencies so AgentFactory can consistently use per-agent models
config = ConfigModel(
    import_tech_list="./data/tech_list.csv",
    model="openai:gpt-4.1-mini",
)
deps = initialize_dependencies(config)

# Test without caching
print("Testing factory without caching...")
factory = AgentFactory(deps)
assert not factory.is_caching_enabled()
print("✓ Caching disabled by default")

# Test with caching
print("\nTesting factory with caching...")
factory_cached = AgentFactory(deps, {"enable_caching": True})
assert factory_cached.is_caching_enabled()
print("✓ Caching enabled when configured")

# Test agent creation
agents = factory_cached.create_all_agents()
print(f"✓ Created {len(agents)} agents")

# Test cache count
count = factory_cached.get_cached_agent_count()
print(f"✓ Cached {count} agents")

# Test status
factory_cached.print_status()

print("\n✓ Factory tests passed!")
