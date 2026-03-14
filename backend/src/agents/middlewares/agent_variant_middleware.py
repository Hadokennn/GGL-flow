from typing import NotRequired, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime


class AgentVariantMiddlewareState(AgentState):
    """Compatible with the `ThreadState` schema."""

    agent_variant: NotRequired[str | None]


class AgentVariantMiddleware(AgentMiddleware[AgentVariantMiddlewareState]):
    """Middleware to set agent_variant from configurable on first message.

    This middleware writes the agent_variant to state on the first message,
    using the value from configurable if not already set.
    The reducer ensures agent_variant is immutable after first write.

    Priority:
    1. state.agent_variant (if already set, cannot be changed)
    2. runtime.context.agent_variant (only used on first message)
    3. "default" (fallback)
    """

    state_schema = AgentVariantMiddlewareState

    @override
    def before_agent(self, state: AgentVariantMiddlewareState, runtime: Runtime) -> dict | None:
        current_variant = state.get("agent_variant")
        if current_variant is not None:
            return None

        new_variant = runtime.context.get("agent_variant", "default")

        return {"agent_variant": new_variant}
