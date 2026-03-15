# Phase 1.2: 智能图谱生成实现文档

## 实现概述

本次实现完成了 GGL 渐进式开发方案 Phase 1.2 的智能图谱生成功能，替换了原有的硬编码模板，使用 LLM 动态生成知识图谱和自评问卷。

## 完成时间

2026-03-15

## 实现功能

### 1. 智能知识图谱生成

**文件**: `backend/src/ggl/deep_research.py`

#### 功能描述
- 使用 LLM 根据学习主题动态生成 8-12 个知识节点
- 自动识别节点间的依赖关系（前置、并行、进阶）
- 生成分层结构（基础层、核心层、进阶层）
- 包含元数据（预估学习时长、难度等级）

#### 核心函数
```python
def generate_knowledge_graph(topic: str, model_name: str | None = None) -> dict[str, Any]:
    """
    使用 LLM 生成知识图谱。
    
    Returns:
        {
            "nodes": [{"id": "root", "label": "主题", "layer": "root"}, ...],
            "edges": [["source_id", "target_id"], ...],
            "metadata": {"total_nodes": 10, "estimated_hours": 20, ...}
        }
    """
```

#### 提示词设计
- **GRAPH_GENERATION_PROMPT**: 详细的图谱生成指令
  - 节点设计要求（粒度、标签）
  - 关系设计要求（前置、并行、进阶）
  - 结构要求（根节点、分层）
  - JSON 输出格式示例

#### 验证逻辑
- 必需字段检查（nodes, edges）
- 节点格式验证（id, label）
- 边格式验证（二元组列表）
- 根节点存在性检查

### 2. 自评问卷生成

**文件**: `backend/src/ggl/deep_research.py`

#### 功能描述
- 根据知识图谱节点生成 3-5 个开放式问题
- 问题覆盖核心知识点
- 具有高区分度（能区分掌握程度）
- 场景化设计

#### 核心函数
```python
def generate_self_assessment_survey(
    topic: str, 
    nodes: list[dict], 
    model_name: str | None = None
) -> dict[str, Any]:
    """
    根据知识图谱生成自评问卷。
    
    Returns:
        {
            "questions": [
                {
                    "id": "q1",
                    "question": "问题文本",
                    "related_nodes": ["node_1", "node_2"],
                    "evaluation_hints": {
                        "mastered": "掌握标准",
                        "blurry": "模糊标准",
                        "unknown": "不了解标准"
                    }
                },
                ...
            ]
        }
    """
```

#### 提示词设计
- **SURVEY_GENERATION_PROMPT**: 问卷生成指令
  - 覆盖核心节点
  - 区分度要求
  - 开放式提问
  - 场景化要求

### 3. 自评回答分析

**文件**: `backend/src/ggl/deep_research.py`

#### 功能描述
- 使用 LLM 分析用户的自评回答
- 判断每个相关节点的掌握程度
- 输出节点状态映射（mastered/blurry/unknown）

#### 核心函数
```python
def analyze_survey_responses(
    survey_questions: list[dict],
    user_responses: dict[str, str],
    model_name: str | None = None
) -> dict[str, str]:
    """
    分析用户的自评回答，判断节点掌握程度。
    
    Returns:
        {"node_id": "state", ...}
        state 为 "mastered"/"blurry"/"unknown"
    """
```

### 4. Gateway API 更新

**文件**: `backend/src/gateway/routers/ggl.py`

#### 新增/修改的端点

##### 1. `POST /api/threads/{thread_id}/ggl/init` (修改)

**新增请求参数**:
```python
class InitGraphRequest(BaseModel):
    topic: str
    expected_version: int | None = None
    use_llm: bool = True  # 新增：是否使用 LLM
    model_name: str | None = None  # 新增：指定模型
```

**新增响应字段**:
```python
class InitGraphResponse(BaseModel):
    topic_graph: dict
    topic_graph_version: int
    survey: dict | None  # 新增：自评问卷数据
```

**功能增强**:
- 支持 LLM 动态生成图谱
- 自动生成配套的自评问卷
- 失败时回退到硬编码模板
- 将问卷数据存储在 ggl_state 中

##### 2. `POST /api/threads/{thread_id}/ggl/survey-answers` (新增)

**请求体**:
```python
class SurveyAnswersRequest(BaseModel):
    responses: dict[str, str]  # {question_id: answer_text}
    expected_version: int | None = None
```

**响应体**:
```python
class SurveyAnswersResponse(BaseModel):
    topic_graph: dict
    topic_graph_version: int
    assessments: dict[str, str]  # {node_id: state}
```

**功能**:
- 接收用户的问卷回答
- 调用 LLM 分析回答
- 自动更新节点状态
- 返回更新后的图谱和评估结果

#### 辅助函数更新

**`_build_initial_topic_graph` 函数重构**:
```python
def _build_initial_topic_graph(
    topic: str, 
    use_llm: bool = True, 
    model_name: str | None = None
) -> tuple[dict, dict | None]:
    """
    Returns:
        (topic_graph, survey_data)
    """
```

- 新增参数支持 LLM 或硬编码模式
- 返回图谱和问卷的元组
- LLM 失败时自动回退

### 5. 前端类型定义更新

**文件**: `frontend/src/core/ggl/types.ts`

#### 新增类型
```typescript
export interface SurveyData {
  questions: SurveyQuestion[];
}

export interface SurveyQuestion {
  id: string;
  question: string;
  related_nodes?: string[];
  evaluation_hints?: {
    mastered: string;
    blurry: string;
    unknown: string;
  };
}

export interface SurveyAnswersRequest {
  responses: Record<string, string>;
  expected_version?: number;
}

export interface SurveyAnswersResponse {
  topic_graph: TopicGraph;
  topic_graph_version: number;
  assessments: Record<string, string>;
}
```

#### 修改类型
```typescript
export interface InitGraphRequest {
  topic: string;
  expected_version?: number;
  use_llm?: boolean;  // 新增
  model_name?: string;  // 新增
}

export interface InitGraphResponse {
  topic_graph: TopicGraph;
  topic_graph_version: number;
  survey?: SurveyData;  // 新增
}
```

### 6. 前端 API 函数

**文件**: `frontend/src/core/ggl/api.ts`

#### 新增函数
```typescript
export async function submitSurveyAnswers(
  threadId: string,
  payload: SurveyAnswersRequest,
): Promise<SurveyAnswersResponse>;
```

## 技术实现要点

### 1. LLM 响应解析

**支持的格式**:
- 纯 JSON 字符串
- Markdown 代码块 (```json ... ```)
- 普通代码块 (``` ... ```)

**解析流程**:
1. 检测 markdown 代码块
2. 提取 JSON 内容
3. 解析并验证
4. 错误处理和回退

### 2. 容错机制

**多层容错**:
1. **LLM 级别**: 使用 config 中配置的默认模型
2. **解析级别**: 支持多种 JSON 格式
3. **生成级别**: LLM 失败时回退到硬编码模板
4. **验证级别**: 严格的字段和格式验证

### 3. 状态管理

**新增 ggl_state 字段**:
```python
ggl_state = {
    "topic_graph": {...},
    "topic_graph_version": 1,
    "active_node_id": "root",
    "current_path": ["root"],
    "digression_stack": [],
    "survey_data": {...},  # 新增：问卷数据
    "knowledge_cards": {...}
}
```

### 4. 日志记录

**关键日志点**:
- 图谱生成开始/结束
- 问卷生成开始/结束
- 回答分析开始/结束
- LLM 失败和回退
- 节点状态更新

## 测试

### 单元测试

**文件**: `backend/tests/test_deep_research.py`

**测试用例**:
1. `test_graph_validation`: 图谱验证逻辑
2. `test_extract_json_from_markdown`: JSON 提取（markdown）
3. `test_extract_json_without_language_tag`: JSON 提取（普通代码块）

**需要 LLM 的测试**（已跳过）:
- `test_generate_knowledge_graph_structure`
- `test_generate_survey_structure`
- `test_analyze_survey_responses_structure`

**运行测试**:
```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_deep_research.py -v
```

### 质量检查

- ✅ Backend lint 通过 (`ruff check`)
- ✅ Backend 单元测试通过
- ✅ Frontend TypeScript 类型检查通过
- ✅ Frontend ESLint 检查通过

## 使用示例

### 1. 初始化图谱（使用 LLM）

**请求**:
```http
POST /api/threads/{thread_id}/ggl/init
Content-Type: application/json

{
  "topic": "深度学习基础",
  "use_llm": true,
  "model_name": null
}
```

**响应**:
```json
{
  "topic_graph": {
    "nodes": [
      {"id": "root", "label": "深度学习基础", "state": "exploring"},
      {"id": "basic_1", "label": "神经网络原理", "state": "unvisited"},
      ...
    ],
    "edges": [["root", "basic_1"], ...]
  },
  "topic_graph_version": 1,
  "survey": {
    "questions": [
      {
        "id": "q1",
        "question": "请解释什么是神经网络？",
        "related_nodes": ["root", "basic_1"],
        "evaluation_hints": {
          "mastered": "能清晰解释神经网络的结构和原理",
          "blurry": "能说出大概概念但不够准确",
          "unknown": "完全不了解"
        }
      },
      ...
    ]
  }
}
```

### 2. 提交自评回答

**请求**:
```http
POST /api/threads/{thread_id}/ggl/survey-answers
Content-Type: application/json

{
  "responses": {
    "q1": "神经网络是一种模拟人脑神经元结构的计算模型...",
    "q2": "反向传播算法用于计算梯度并更新权重...",
    "q3": "激活函数的作用是引入非线性..."
  },
  "expected_version": 1
}
```

**响应**:
```json
{
  "topic_graph": {
    "nodes": [
      {"id": "root", "label": "深度学习基础", "state": "mastered"},
      {"id": "basic_1", "label": "神经网络原理", "state": "mastered"},
      {"id": "basic_2", "label": "反向传播", "state": "blurry"},
      {"id": "basic_3", "label": "激活函数", "state": "mastered"}
    ],
    ...
  },
  "topic_graph_version": 2,
  "assessments": {
    "root": "mastered",
    "basic_1": "mastered",
    "basic_2": "blurry",
    "basic_3": "mastered"
  }
}
```

### 3. 初始化图谱（硬编码模板）

**请求**:
```http
POST /api/threads/{thread_id}/ggl/init
Content-Type: application/json

{
  "topic": "Python 编程",
  "use_llm": false
}
```

**响应**:
```json
{
  "topic_graph": {
    "nodes": [
      {"id": "root", "label": "Python 编程", "state": "exploring"},
      {"id": "n1", "label": "Python 编程 - 核心概念", "state": "unvisited"},
      {"id": "n2", "label": "Python 编程 - 关键术语", "state": "unvisited"},
      ...
    ],
    "edges": [["root", "n1"], ["root", "n2"], ...]
  },
  "topic_graph_version": 1,
  "survey": null
}
```

## 配置要求

### 后端配置

**config.yaml** 必须包含至少一个可用的 LLM 模型：

```yaml
models:
  - name: default
    use: langchain_openai:ChatOpenAI
    api_key: $OPENAI_API_KEY
    model: gpt-4o
```

或任何其他支持的模型（Claude, Gemini, 等）。

### 环境变量

确保设置对应的 API key：
- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- Google: `GOOGLE_API_KEY`

## 已知限制

1. **LLM 依赖**: 智能功能完全依赖 LLM，如果模型不可用会回退到硬编码模板
2. **响应质量**: LLM 生成的图谱质量依赖于模型能力和提示词设计
3. **语言支持**: 当前提示词使用中文，多语言支持需要额外实现
4. **Token 消耗**: 每次生成图谱和分析回答都会消耗 token

## 后续优化方向

1. **提示词优化**:
   - A/B 测试不同的提示词
   - 针对不同学科定制提示词
   - 支持多语言提示词

2. **缓存机制**:
   - 缓存常见主题的图谱
   - 缓存问卷模板

3. **增量生成**:
   - 支持用户修改生成的图谱
   - 动态添加/删除节点
   - 调整节点关系

4. **评估改进**:
   - 更精细的掌握度评分（0-100 分）
   - 多维度评估（理解度、应用能力、深度）
   - 历史追踪和趋势分析

## 相关文件

### 新增文件
1. `backend/src/ggl/deep_research.py` - 核心实现
2. `backend/tests/test_deep_research.py` - 单元测试
3. `backend/PHASE1.2_IMPLEMENTATION.md` - 本文档

### 修改文件
1. `backend/src/gateway/routers/ggl.py` - API 端点
2. `frontend/src/core/ggl/types.ts` - 类型定义
3. `frontend/src/core/ggl/api.ts` - API 函数

## 总结

Phase 1.2 成功实现了智能图谱生成功能，核心亮点：

✅ **智能化**: 使用 LLM 动态生成知识图谱和问卷  
✅ **容错性**: 多层回退机制确保可用性  
✅ **可扩展**: 清晰的接口设计便于后续扩展  
✅ **质量保证**: 完整的测试和代码检查  

**下一步**: 继续实现 Phase 1.3 基础苏格拉底引导功能。
