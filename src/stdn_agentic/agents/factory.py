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

    IMPORTANT:
        This factory should be constructed with `deps` so it can consistently
        use per-agent models (component/materials/country) from dependencies.
        This avoids surprising mixed-model behavior where an agent silently
        falls back to environment variables or `config.model`.

    Attributes:
        deps: Runtime dependencies (includes per-agent model configuration)
        config: Optional configuration dictionary for agent customization
        _component_agent: Cached component agent instance
        _materials_agent: Cached materials agent instance
        _country_agent: Cached country agent instance

    Example:
        >>> factory = AgentFactory(deps)
        >>> agents = factory.create_all_agents()
        >>> components = await agents["component"].run(
        ...     "Extract components from a smartphone",
        ...     deps=deps
        ... )
    """

    def __init__(self, deps: STDNDependencies, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent factory.

        Args:
            deps: STDNDependencies instance. Required so the factory can use
                  configured per-agent models consistently.
            config: Optional configuration dictionary with keys:
                - "enable_caching": bool (default: False) - Cache agent instances
                - "component_agent": dict - Override component agent config (future)
                - "materials_agent": dict - Override materials agent config (future)
                - "country_agent": dict - Override country agent config (future)

        Example:
            >>> factory = AgentFactory(
            ...     deps,
            ...     config={"enable_caching": True},
            ... )
        """
        self.deps = deps
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
        """
        # Return cached instance if available
        if self._caching_enabled and self._component_agent is not None:
            return self._component_agent

        # Create new instance (prefer configured per-agent model from deps)
        agent = get_component_agent(model_name=self.deps.get_component_model())

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
        """
        # Return cached instance if available
        if self._caching_enabled and self._materials_agent is not None:
            return self._materials_agent

        # Create new instance (prefer configured per-agent model from deps)
        agent = get_materials_agent(model_name=self.deps.get_materials_model())

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
        """
        # Return cached instance if available
        if self._caching_enabled and self._country_agent is not None:
            return self._country_agent

        # Create new instance (prefer configured per-agent model from deps)
        agent = get_country_data_agent(model_name=self.deps.get_country_model())

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
                - "materials": Materials extraction agent
                - "country": Country data agent
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
        print("Factory Status:")
        print(f"  Caching enabled: {self._caching_enabled}")
        print(f"  Cached agents: {self.get_cached_agent_count()}")

        if self._component_agent is not None:
            print("    - component")
        if self._materials_agent is not None:
            print("    - materials")
        if self._country_agent is not None:
            print("    - country")
