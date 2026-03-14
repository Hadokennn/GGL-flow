"""API for agent variants management."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config.agent_variants_config import get_agent_variants_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["agent-variants"])


class AgentVariantInfo(BaseModel):
    """Information about an agent variant."""

    name: str = Field(..., description="Variant name (e.g., 'default', 'ggl')")
    label: str = Field(..., description="Human-readable label")
    description: str = Field(default="", description="Description of the variant")


class AgentVariantsResponse(BaseModel):
    """Response model for listing agent variants."""

    variants: list[AgentVariantInfo]


@router.get(
    "/agent-variants",
    response_model=AgentVariantsResponse,
    summary="List Agent Variants",
    description="List all available agent variants (e.g., default, ggl).",
)
async def list_agent_variants() -> AgentVariantsResponse:
    """List all available agent variants.

    Returns:
        List of agent variants with their metadata.
    """
    try:
        config = get_agent_variants_config()
        variants = [
            AgentVariantInfo(
                name=name,
                label=variant.label,
                description=variant.description,
            )
            for name, variant in config.agentVariants.items()
        ]
        return AgentVariantsResponse(variants=variants)
    except Exception as e:
        logger.error(f"Failed to list agent variants: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list agent variants: {str(e)}")
