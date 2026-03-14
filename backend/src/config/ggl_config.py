from pydantic import BaseModel, Field


class GGLStorageConfig(BaseModel):
    """Storage configuration for GGL (export/backup only)."""

    export_enabled: bool = Field(
        default=False,
        description="Whether to enable exporting GGL data to file (for backup)",
    )
    path: str = Field(
        default=".deer-flow/threads",
        description="Export path (only used when export_enabled is true)",
    )


class GGLConfig(BaseModel):
    """GGL (Graph Guided Learning) configuration."""

    storage: GGLStorageConfig = Field(
        default_factory=GGLStorageConfig,
        description="Storage configuration for GGL",
    )


_ggl_config: GGLConfig | None = None


def get_ggl_config() -> GGLConfig:
    """Get the GGL config instance.

    Returns a cached singleton instance.

    Returns:
        The cached GGLConfig instance.
    """
    global _ggl_config
    if _ggl_config is None:
        _ggl_config = GGLConfig()
    return _ggl_config


def set_ggl_config(config: GGLConfig) -> None:
    """Set a custom GGL config instance.

    Args:
        config: The GGLConfig instance to use.
    """
    global _ggl_config
    _ggl_config = config


def reset_ggl_config() -> None:
    """Reset the cached GGL config instance."""
    global _ggl_config
    _ggl_config = None
