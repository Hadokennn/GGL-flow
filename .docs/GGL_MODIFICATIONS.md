# GGL-flow 改造说明

本文档记录在 DeerFlow 基础上为 GGL（Graph Guided Learning）模式所做的改造。

---

## 1. 知识卡异步生成

### 1.1 背景

原实现：节点 mastered 后，middleware 注入指令，主 agent 顺序调用 `update_knowledge_card` 为每个节点生成知识卡，串行阻塞。

### 1.2 改造方案

**本地存储 + 后台队列**（参考 `memory_middleware` 模式）：

- 新建 `knowledge_card_queue`，不复用 memory queue
- `update_ggl_graph` 检测 newly mastered 节点 → 写入 `pending_card_node_ids`
- `GGLMiddleware.after_agent` 读取 pending → 入队 → 清空 pending
- 后台 daemon 线程：LLM 生成知识卡 → 写 `outputs/knowledge_cards/{node_id}.md` → 更新 checkpoint

### 1.3 涉及文件

| 路径 | 说明 |
|------|------|
| `backend/src/agents/knowledge_card/queue.py` | 队列：每任务独立 daemon 线程，`(thread_id, node_id)` 去重 |
| `backend/src/agents/knowledge_card/processor.py` | 处理器：LLM 生成 → 写文件 → 更新 checkpoint + artifacts |
| `backend/src/agents/middlewares/ggl_middleware.py` | 移除 before_model 的「请生成卡」注入，新增 after_agent 入队 |
| `backend/src/ggl/tools.py` | 移除 `update_knowledge_card` 工具，仅保留 `update_ggl_graph` |

### 1.4 Checkpoint 更新

- 抽离 `src/gateway/checkpoint_utils.py`：`persist_partial_state`、`get_checkpoint_tuple`
- Processor 写入时**合并完整 ggl state**，避免覆盖 `topic_graph` 等字段
- 新增 `knowledge_card_node_ids` 供前端显示预览图标
- 知识卡路径加入 `artifacts`，支持 Artifacts 列表下载

---

## 2. GGL 首次 Research 强制 Subagent

### 2.1 背景

非 Ultra 模式下 `subagent_enabled=false`，但 GGL 首次构建知识图谱需要 subagent 做深度调研。

### 2.2 改造

在 `make_lead_agent` 中，当 `agent_variant === "ggl"` 时：

- 无 `thread_id`（新会话）→ `subagent_enabled = true`
- `topic_graph` 为空或无 nodes → `subagent_enabled = true`
- 否则使用配置值（`context.mode === "ultra"`）

### 2.3 涉及文件

`backend/src/agents/lead_agent/agent.py`：新增 `_resolve_subagent_enabled_for_ggl`，在解析 `subagent_enabled` 后按 GGL 状态覆盖。

---

## 3. 知识图谱布局：环形 → 脑图

### 3.1 背景

原 `circularLayout` 将节点排成环形，不符合学习路径的层级关系。

### 3.2 改造

`mindMapLayout`：基于边的层级布局

- 根节点：`current_path[0]` 或无入边节点
- 按边 `[source, target]` BFS，source 在上、target 在下
- 每层水平排布，层间垂直留白
- 孤立节点置于底层

### 3.3 涉及文件

`frontend/src/components/workspace/ggl/knowledge-map.tsx`：`circularLayout` → `mindMapLayout`，传入 `edges`、`current_path`。

---

## 4. Thread 删除与 Checkpoint

### 4.1 改造

- Gateway 新增 `DELETE /api/threads/{thread_id}`：删除 checkpoint 及 thread 目录
- 前端删除 thread 时调用该接口，而非 LangGraph SDK

### 4.2 涉及文件

`backend/src/gateway/routers/threads.py`、`frontend` threads API。

---

## 5. GGL Middleware 行为

### 5.1 Init 注入

- `_has_init_been_injected`：避免每轮重复注入
- 仅当 `topic_graph` 为空时注入一次

### 5.2 Context 注入

- `_has_context_been_injected`：仅考虑 last user message 之后的 message，避免同 turn 重复

### 5.3 MASTERED 启发式

- 短确认词（如「好」「继续」「1」）+ 当前节点 exploring → 直接走 MASTERED 分支，不调用 `classify_intent`

---

## 6. Active Node 切换

### 6.1 行为

- `PUT /api/threads/{id}/ggl/active-node` 更新 `ggl.active_node_id` 并写入 checkpoint
- 下次会话时，`GGLMiddleware.before_model` 从 checkpoint 读取最新 `active_node_id`，注入「当前学习节点」上下文

---

## 7. 已知限制与待办

| 限制 | 说明 |
|------|------|
| Subagent 产出未进 artifacts | 深度调研文档由 subagent 生成，但 `present_files` 被禁用，不会进入 parent artifacts。需扩展 subagent→parent 的 artifacts 合并。 |
| 节点与 artifact 映射 | 图谱节点点击仅展示知识卡摘要，完整调研文档的 node-artifact 映射尚未实现。 |
| 损坏的 checkpoint | 旧版 processor 曾只写部分 ggl 导致 `topic_graph` 丢失，需删除旧 thread 重建。 |

详见 `.docs/optimization_backlog.md`。
