# GGL Phase 1 Implementation

## Backend Implementation

### 1. Agent Variants Config
- Create `backend/src/config/agent_variants_config.py`
- Add to `extensions_config.py` (or create separate config)

### 2. ThreadState Extension
- Modify `backend/src/agents/thread_state.py`
- Add `agent_variant` field with reducer
- Add `GGLState` with all required fields

### 3. AgentVariantMiddleware
- Create `backend/src/agents/middlewares/agent_variant_middleware.py`

### 4. GGL Config
- Create `backend/src/config/ggl_config.py`

### 5. GGL Router
- Create `backend/src/gateway/routers/ggl.py`
- Create `backend/src/gateway/routers/agent_variants.py`
- Modify `backend/src/gateway/app.py` to include routers

### 6. Modify lead_agent
- Update `backend/src/agents/lead_agent/agent.py` to use AgentVariantMiddleware and GGL injection

## Frontend Implementation

### 1. Agent Variant Selector
- Modify `frontend/src/components/workspace/welcome.tsx` or create new component

### 2. GGL API Types
- Create `frontend/src/core/ggl/types.ts`
- Create `frontend/src/core/ggl/api.ts`

### 3. GGL Provider
- Create `frontend/src/components/workspace/ggl/context.tsx`

## Testing
- Add unit tests for reducers
- Add integration tests for GGL routes
