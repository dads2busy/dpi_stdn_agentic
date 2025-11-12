"""
Agent factory for STDN (Supply Technology Dependency Network)

This module provides a factory pattern for creating and configuring agents.
It centralizes agent initialization, making it easy to:
- Create agents with consistent configuration
- Swap agent implementations
- Manage agent lifecycle
- Enable/disable agents based on configuration

The factory is particularly useful for:
- Testing (mock agents via factory configuration)
- Multi-agent debate system setup
- Pipeline orchestration
- Dependency injection
"""

from typing import Any, Dict, Optional, Union

from pydantic_ai import Agent

from ..models import STDNDependencies
from .component_agent import ComponentList, get_component_agent
from .country_agent import CountryList, get_country_data_agent
from .materials_agent import ComponentMaterialsList, get_materials_agent

# ============================================================================
# Agent Factory
# ============================================================================


class AgentFactory:
    """
    Factory for creating and configuring STDN agents.

    Provides centralized initialization of component, materials, and country
    data agents with support for configuration overrides and agent pooling.

    Attributes:
        config: Optional configuration dictionary for agent customization
        _component_agent: Cached component agent instance
        _materials_agent: Cached materials agent instance
        _country_agent: Cached country agent instance

    Example:
        >>> factory = AgentFactory()
        >>> agents = factory.create_all_agents()
        >>> components = await agents["component"].run(
        ...     "Extract components from a smartphone",
        ...     deps=deps
        ... )
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent factory.

        Args:
            config: Optional configuration dictionary with keys:
                - "enable_caching": bool (default: False) - Cache agent instances
                - "component_agent": dict - Override component agent config
                - "materials_agent": dict - Override materials agent config
                - "country_agent": dict - Override country agent config

        Example:
            >>> config = {
            ...     "enable_caching": True,
            ...     "component_agent": {"model": "openai:gpt-4"}
            ... }
            >>> factory = AgentFactory(config)
        """
        self.config = config or {}
        self._caching_enabled = self.config.get("enable_caching", False)

        # Type-specific caches for each agent
        self._component_agent: Optional[Agent[STDNDependencies, ComponentList]] = None
        self._materials_agent: Optional[Agent[STDNDependencies, ComponentMaterialsList]] = None
        self._country_agent: Optional[Agent[STDNDependencies, CountryList]] = None

    # ========================================================================
    # Individual Agent Creation
    # ========================================================================

    def create_component_agent(self) -> Agent[STDNDependencies, ComponentList]:
        """
        Create or retrieve the component extraction agent.

        Returns:
            Configured Agent for component extraction.
            Returns cached instance if caching is enabled.

        Example:
            >>> agent = factory.create_component_agent()
            >>> result = await agent.run(
            ...     "What are the main components?",
            ...     deps=STDNDependencies(...)
            ... )
        """
        # Return cached instance if available
        if self._caching_enabled and self._component_agent is not None:
            return self._component_agent

        # Create new instance
        agent = get_component_agent()

        # Cache if enabled
        if self._caching_enabled:
            self._component_agent = agent

        return agent

    def create_materials_agent(self) -> Agent[STDNDependencies, ComponentMaterialsList]:
        """
        Create or retrieve the materials extraction agent.

        Returns:
            Configured Agent for materials extraction with validation.
            Returns cached instance if caching is enabled.

        Example:
            >>> agent = factory.create_materials_agent()
            >>> result = await agent.run(
            ...     "Extract materials for each component",
            ...     deps=STDNDependencies(...)
            ... )
        """
        # Return cached instance if available
        if self._caching_enabled and self._materials_agent is not None:
            return self._materials_agent

        # Create new instance
        agent = get_materials_agent()

        # Cache if enabled
        if self._caching_enabled:
            self._materials_agent = agent

        return agent

    def create_country_agent(self) -> Agent[STDNDependencies, CountryList]:
        """
        Create or retrieve the country data agent.

        Returns:
            Configured Agent for country production data (LLM fallback).
            Returns cached instance if caching is enabled.

        Example:
            >>> agent = factory.create_country_agent()
            >>> result = await agent.run(
            ...     "Get top countries producing lithium in 2024",
            ...     deps=STDNDependencies(...)
            ... )
        """
        # Return cached instance if available
        if self._caching_enabled and self._country_agent is not None:
            return self._country_agent

        # Create new instance
        agent = get_country_data_agent()

        # Cache if enabled
        if self._caching_enabled:
            self._country_agent = agent

        return agent

    # ========================================================================
    # Batch Agent Creation
    # ========================================================================

    def create_all_agents(
        self,
    ) -> Dict[
        str,
        Union[
            Agent[STDNDependencies, ComponentList],
            Agent[STDNDependencies, ComponentMaterialsList],
            Agent[STDNDependencies, CountryList],
        ],
    ]:
        """
        Create all agents in a single call.

        Convenient method for initializing the complete agent suite for
        pipeline orchestration or debate systems.

        Returns:
            Dictionary with keys:
                - "component": Component extraction agent
                - "materials": Materials extraction agent (with validation)
                - "country": Country data agent (LLM fallback)

        Example:
            >>> factory = AgentFactory()
            >>> agents = factory.create_all_agents()
            >>>
            >>> # Use in pipeline
            >>> components = await agents["component"].run(prompt, deps)
            >>> materials = await agents["materials"].run(prompt, deps)
            >>> countries = await agents["country"].run(prompt, deps)
        """
        return {
            "component": self.create_component_agent(),
            "materials": self.create_materials_agent(),
            "country": self.create_country_agent(),
        }

    # ========================================================================
    # Agent Management
    # ========================================================================

    def clear_cache(self) -> None:
        """
        Clear the agent instance cache.

        Useful for resetting agents or forcing recreation with new configuration.
        Has no effect if caching is disabled.

        Example:
            >>> factory = AgentFactory({"enable_caching": True})
            >>> factory.clear_cache()
            >>> # Next agent creation will create fresh instances
        """
        self._component_agent = None
        self._materials_agent = None
        self._country_agent = None

    def get_cached_agent_count(self) -> int:
        """
        Get count of currently cached agents.

        Returns:
            Number of cached agent instances.

        Example:
            >>> factory = AgentFactory({"enable_caching": True})
            >>> agents = factory.create_all_agents()
            >>> count = factory.get_cached_agent_count()
            >>> print(f"Cached agents: {count}")
            Cached agents: 3
        """
        count = 0
        if self._component_agent is not None:
            count += 1
        if self._materials_agent is not None:
            count += 1
        if self._country_agent is not None:
            count += 1
        return count

    def is_caching_enabled(self) -> bool:
        """
        Check if agent caching is enabled.

        Returns:
            True if agent instances are cached, False otherwise.
        """
        return self._caching_enabled

    def set_caching(self, enabled: bool) -> None:
        """
        Enable or disable agent instance caching.

        Args:
            enabled: True to enable caching, False to disable.

        Note:
            Changing caching state does not clear existing cache.
            Call clear_cache() to clear existing cached agents.
        """
        self._caching_enabled = enabled

    # ========================================================================
    # Configuration Management
    # ========================================================================

    def get_config(self) -> Dict[str, Any]:
        """
        Get the factory configuration.

        Returns:
            Copy of the configuration dictionary.
        """
        return self.config.copy()

    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update factory configuration.

        Args:
            updates: Dictionary with configuration updates.

        Note:
            Requires clear_cache() to apply changes to existing agents.

        Example:
            >>> factory = AgentFactory()
            >>> factory.update_config({"enable_caching": True})
            >>> factory.clear_cache()
        """
        self.config.update(updates)

    # ========================================================================
    # Status Methods
    # ========================================================================

    def __repr__(self) -> str:
        """
        String representation of the factory.
        """
        caching_status = "enabled" if self._caching_enabled else "disabled"
        cached_count = self.get_cached_agent_count()
        return f"AgentFactory(caching={caching_status}, cached_agents={cached_count})"

    def print_status(self) -> None:
        """
        Print detailed factory status.

        Example:
            >>> factory = AgentFactory({"enable_caching": True})
            >>> factory.create_all_agents()
            >>> factory.print_status()
            # Output shows caching status and cached agents
        """
        print(f"Factory Status:")
        print(f"  Caching enabled: {self._caching_enabled}")
        print(f"  Cached agents: {self.get_cached_agent_count()}")

        if self._component_agent is not None:
            print(f"    - component")
        if self._materials_agent is not None:
            print(f"    - materials")
        if self._country_agent is not None:
            print(f"    - country")
