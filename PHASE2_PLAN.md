# Phase 2 实现计划

## Phase 2: Canvas 与双向同步（1-2 周）

### 当前状态

#### 后端
- ✅ PUT /ggl/active-node 已有 node 存在性校验
- ⚠️ 需要确认 SSE values 包含 state.ggl

#### 前端
- ⚠️ 无 GGLProvider
- ⚠️ 无 GGLCanvas
- ⚠️ 需要实现 SSE 同步

---

## 实现任务

### 1. 后端：确认 SSE 包含 ggl 状态

**问题**: 当前 LangGraph 的 stream 事件是否包含 ggl 状态？

**检查点**:
```python
# 在 agent 运行时，ggl 状态应该在 ThreadState 中
# LangGraph 的 stream_mode="values" 应该会输出每个 step 的完整 state
```

**确认方式**:
1. 启用 LangSmith 追踪，查看 stream 事件
2. 或在前端打印 stream 事件内容

**如需修改**:
- 确保 `streamSubgraphs: true` 时，每个 checkpoint 都包含 ggl 字段

---

### 2. 前端：GGLProvider

创建 `frontend/src/core/ggl/provider.tsx`:

```typescript
import { createContext, useContext, useState, useEffect } from 'react'
import { fetchGGLGraph } from './api'
import type { GGLState } from './types'

interface GGLContextValue {
  gglState: GGLState | null
  isLoading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

const GGLContext = createContext<GGLContextValue | null>(null)

export function GGLProvider({ 
  threadId, 
  children,
  enabled = false  // 仅 agent_variant=ggl 时启用
}: {
  threadId: string
  children: React.ReactNode
  enabled?: boolean
}) {
  const [gglState, setGglState] = useState<GGLState | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const refetch = async () => {
    if (!enabled || !threadId) return
    setIsLoading(true)
    try {
      const data = await fetchGGLGraph(threadId)
      setGglState(data)
    } catch (e) {
      setError(e as Error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    refetch()
  }, [threadId, enabled])

  // TODO: SSE 监听 - 当 agent 执行完成后刷新 ggl 状态
  // 可以通过 onRefresh 回调触发 refetch

  return (
    <GGLContext.Provider value={{ gglState, isLoading, error, refetch }}>
      {children}
    </GGLContext.Provider>
  )
}

export function useGGL() {
  const context = useContext(GGLContext)
  if (!context) {
    throw new Error('useGGL must be used within GGLProvider')
  }
  return context
}
```

---

### 3. 前端：GGLCanvas 组件

创建 `frontend/src/components/workspace/ggl/ggl-canvas.tsx`:

```typescript
import { useGGL } from '@/core/ggl/provider'
import { setActiveNode } from '@/core/ggl/api'

export function GGLCanvas() {
  const { gglState, refetch } = useGGL()
  
  if (!gglState?.topic_graph) {
    return <div>No topic graph yet</div>
  }

  const handleNodeDoubleClick = async (nodeId: string) => {
    await setActiveNode(threadId, nodeId)
    await refetch()  // 刷新状态
  }

  return (
    <div className="ggl-canvas">
      {gglState.topic_graph.nodes.map(node => (
        <div
          key={node.id}
          className={`node node-${node.state}`}
          onDoubleClick={() => handleNodeDoubleClick(node.id)}
        >
          {node.label}
        </div>
      ))}
      {/* 渲染 edges */}
    </div>
  )
}
```

---

### 4. 前端：GGLCanvasTrigger（侧边栏开关）

修改 `frontend/src/components/workspace/workspace-sidebar.tsx`:

```typescript
// 添加 GGL 侧边栏按钮
<Button 
  variant="ghost" 
  onClick={() => setGglPanelOpen(!gglPanelOpen)}
>
  <NetworkIcon />
  GGL
</Button>

{gglPanelOpen && (
  <GGLCanvas />
)}
```

---

### 5. SSE 同步实现

**方案 A: 轮询（简单）**
```typescript
// 在 GGLProvider 中
useEffect(() => {
  const interval = setInterval(refetch, 5000)  // 每5秒轮询
  return () => clearInterval(interval)
}, [threadId])
```

**方案 B: 监听 SSE 事件（推荐）**
```typescript
// 前端在 agent 执行完成后触发 refetch
// 可以在 useThreadStream 的 onFinish 回调中调用
```

---

## 实施顺序

1. **创建 GGLProvider** - 基础状态管理
2. **创建 GGLCanvas** - 图谱渲染
3. **集成到页面** - 在 thread 页面使用 GGLProvider
4. **添加 GGLCanvasTrigger** - 侧边栏开关
5. **实现 SSE/轮询同步** - 保持状态更新

---

## 依赖关系

```
GGLProvider (context)
    ↓
GGLCanvas (消费 context)
    ↓
Workspace 页面 (包裹 GGLProvider)
    ↓
Sidebar (GGLCanvasTrigger 开关)
```
