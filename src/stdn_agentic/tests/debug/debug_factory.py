"""Test AgentFactory functionality"""
from stdn_agentic.agents import AgentFactory

# Test without caching
print("Testing factory without caching...")
factory = AgentFactory()
assert not factory.is_caching_enabled()
print("✓ Caching disabled by default")

# Test with caching
print("\nTesting factory with caching...")
factory_cached = AgentFactory({"enable_caching": True})
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
