from pydantic import BaseModel, Field


class AgentVariantConfig(BaseModel):
    """Configuration for a single agent variant."""

    label: str = Field(description="Human-readable label for the variant")
    description: str = Field(default="", description="Description of the variant")


class AgentVariantsConfig(BaseModel):
    """Configuration for agent variants."""

    agentVariants: dict[str, AgentVariantConfig] = Field(
        default_factory=dict,
        description="Map of agent variant name to configuration",
    )

    def get_variant(self, variant_name: str) -> AgentVariantConfig | None:
        """Get variant config by name."""
        return self.agentVariants.get(variant_name)

    def get_available_variants(self) -> list[str]:
        """Get list of available variant names."""
        return list(self.agentVariants.keys())


DEFAULT_AGENT_VARIANTS = AgentVariantsConfig(
    agentVariants={
        "default": AgentVariantConfig(
            label="Default",
            description="Standard DeerFlow agent",
        ),
        "ggl": AgentVariantConfig(
            label="GGL",
            description="Graph Guided Learning - Adaptive learning agent with topic graphs",
        ),
    }
)


_agent_variants_config: AgentVariantsConfig | None = None


def get_agent_variants_config() -> AgentVariantsConfig:
    """Get the agent variants config instance.

    Returns a cached singleton instance.

    Returns:
        The cached AgentVariantsConfig instance.
    """
    global _agent_variants_config
    if _agent_variants_config is None:
        _agent_variants_config = DEFAULT_AGENT_VARIANTS
    return _agent_variants_config


def set_agent_variants_config(config: AgentVariantsConfig) -> None:
    """Set a custom agent variants config instance.

    Args:
        config: The AgentVariantsConfig instance to use.
    """
    global _agent_variants_config
    _agent_variants_config = config


def reset_agent_variants_config() -> None:
    """Reset the cached agent variants config instance."""
    global _agent_variants_config
    _agent_variants_config = None
