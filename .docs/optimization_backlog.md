# 优化待办（Optimization Backlog）

后续可做的优化点，按优先级或阶段记录。

---

## GitHub 仓库代码目录与机制

**背景**：Agent 回答 GitHub 仓库相关问题时存在较大幻觉，因无法访问仓库真实代码，只能依赖 web_search 和通用知识猜测。

**现状**：Thread 目录仅有 `workspace`、`uploads`、`outputs`，无专门存放克隆代码的位置。

**优化方案**：

1. **新增 `repos/` 目录**
   - Paths: `user-data/repos/` → `/mnt/user-data/repos/`
   - 语义：专门存放从 GitHub 克隆的代码，与 workspace 临时产出区分

2. **新增 `clone_github_repo` 工具**
   - 接收 repo URL，clone 到 `repos/{owner}_{repo}/`
   - 支持增量更新（已有则 pull）

3. **上下文注入**
   - 在 thread_data 或 middleware 中注入「已 clone 的 repos 列表及路径」
   - 让 LLM 知道可读取哪些代码

4. **大仓库处理**
   - 可选：只 clone 指定 branch/path
   - 或配合 codebase 索引/摘要，避免全量读入 context

**涉及改动**：Paths、ThreadDataMiddleware、sandbox tools 映射、新增工具、prompt 或 middleware 注入。

---

## 代码/文件 Token 消耗与索引摘要机制

**背景**：当前项目对 uploads 文件未做缓存、摘要或索引。`read_file` 直接返回完整内容，`list_dir` 返回原始目录结构。若将 GitHub 仓库 clone 到 `repos/`，模型通过 `read_file` 读取代码时，Token 消耗将急剧放大。DeerFlow 本身没有集成 RAG ，但设计上支持通过 Skills/MCP 扩展来连接外部 RAG 服务（如 RAGFlow、Qdrant 等）。keywork：Private Knowledgebase Support。

**问题分析**：

| 维度 | 现状 | 风险 |
|------|------|------|
| read_file | 原样返回全文 | 单文件几千行 → 几万 token/次 |
| list_dir | 返回完整树 | 大 repo 数千文件 → 列表本身也占大量 token |
| 多轮对话 | 工具返回内容进入历史 | 历史累积，后续每轮都重复计费 |
| 无摘要 | 模型需全文才能理解 | 无法「先看摘要再按需深入」 |

**典型场景**：用户问「这个 repo 的 API 怎么用？」→ 模型需探索目录、读多个文件 → 单次对话可能读入 10+ 文件、数十万 token。

**优化方向**：

1. **文件/目录摘要**
   - 对 clone 的 repo 做一次性摘要（模块职责、入口、关键 API）
   - 摘要写入 `repos/{repo}/.summary.json` 或类似
   - 模型先读摘要，再按需 `read_file` 具体文件

2. **向量索引 / 语义检索**
   - 对代码建 embedding 索引
   - 用户提问 → 检索相关片段 → 只把 top-k 片段塞入 context
   - 可复用现有 RAG 基础设施（若项目有）

3. **read_file 分块/截断策略**
   - 默认只返回前 N 行（如 200 行）或「摘要 + 前 50 行」
   - 增加参数 `full=True` 才返回全文
   - 减少模型「无意识」读入超大文件

4. **缓存与去重**
   - 同一文件同一轮内多次 read → 只计一次
   - 跨轮：可做「已读文件」标记，避免重复读入历史

5. **与 uploads 统一**
   - uploads 大文件也有同样问题
   - 可设计统一的「大文件处理策略」：超过阈值自动摘要/索引

**优先级**：在实现 `repos/` + `clone_github_repo` 之前或同时，应先有基础的摘要/索引机制，否则大 repo 场景下 token 成本与延迟都难以接受。

---

## 知识卡生成异步化

**背景**：当节点被标记为 mastered 但尚未生成知识卡时，middleware 注入指令，主 agent 顺序调用 `update_knowledge_card` 为每个节点生成。这是**顺序执行**：主 agent 每次调用都要等 LLM 推理 + 工具返回，多节点时耗时为各节点之和。

**当前流程**：pending → 注入指令 → 主 agent 依次调用 update_knowledge_card(A) → update_knowledge_card(B) → ... → 串行阻塞。

---

### 推荐方案：本地存储 + 队列（仿 memory_middleware）

**核心**：知识卡内容存本地文件，不写入 `ggl.knowledge_cards`，无需回写 checkpoint，天然支持异步。

**存储结构**：
```
threads/{thread_id}/user-data/outputs/knowledge_cards/
├── {node_id}_summary.txt   # 短摘要，用于 context 注入
└── {node_id}.md            # 完整文档，供用户下载
```

**流程**：
1. `update_ggl_graph` 检测到 newly_mastered → 投递到队列（类似 memory queue）
2. 后台处理：调用 LLM 生成 → 写入 `{node_id}_summary.txt` 和 `{node_id}.md`
3. 主 agent 立即返回，不阻塞
4. checkpoint 只存轻量信息：`knowledge_card_node_ids: [node_id]`（有卡的节点列表），不存正文

**两处用途**：

| 输出 | 用途 |
|------|------|
| summary | 用户切换节点时，middleware 读取 `{node_id}_summary.txt` 注入 ggl_context |
| document | 用户下载，通过 artifact API：`/api/threads/{id}/artifacts/knowledge_cards/{node_id}.md` |

**优点**：异步、复用 memory 模式、checkpoint 轻量、复用 artifact 下载、middleware 按需读文件注入。

**队列**：新建 `knowledge_card_queue`（不复用 memory queue），模式可参考 `memory/queue.py`：同进程、debounce 或立即消费、ThreadPoolExecutor 处理。

**生成完成后更新 checkpoint**：

1. **GGLState 增加** `knowledge_card_node_ids: list[str]`，记录已有卡的节点，供 FE 显示预览图标。
2. **ggl_reducer** 对该字段做 merge：`merged["knowledge_card_node_ids"] = list(dict.fromkeys((current or []) + (update or [])))`。
3. **队列 processor** 在写入本地文件后，调用与 Gateway 一致的 checkpoint 更新逻辑：
   - 读取当前 checkpoint：`checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})`
   - 取出当前 `ggl`，按 reducer 语义合并：`knowledge_card_node_ids += [node_id]`，`pending_card_node_ids` 移除该 node_id
   - 调用 `_persist_partial_state(thread_id, {"ggl": merged_ggl})`（需将 `_persist_partial_state` 抽到 `src/gateway/checkpoint.py` 或类似，供队列 processor 复用）
4. **同进程**：队列 processor 与 Gateway 同进程，可直接 `get_checkpointer()` 和 `_persist_partial_state`，无需 HTTP 自调。

---

### 其他方案（备选）

| 方案 | 做法 | 难点 |
|------|------|------|
| 专用工具 + 轮询（仿 task） | 新增工具，内部启动 subagent 并轮询，stream 推进度 | 主 agent 仍阻塞；subagent 写主 thread state 需设计 |
| 独立 worker + 队列 | 跨进程：Redis/RabbitMQ + 独立 worker 进程 | 项目当前无此实现，需新增架构 |
| 保持顺序 | 继续由主 agent 顺序调用 | 多节点耗时长 |
