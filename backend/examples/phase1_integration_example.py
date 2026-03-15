"""
GGL Phase 1 前端增强 - 后端集成示例

本文件展示如何在后端为消息添加节点关联元数据，以支持前端的双向同步功能。
"""

from langchain_core.messages import AIMessage, HumanMessage


def create_node_related_message(
    content: str,
    node_id: str,
    node_label: str,
    message_type: str = "ai"
) -> AIMessage | HumanMessage:
    """
    创建带有节点关联元数据的消息
    
    Args:
        content: 消息内容
        node_id: 关联的节点 ID
        node_label: 节点显示标签
        message_type: 消息类型 ("ai" 或 "human")
    
    Returns:
        带有节点关联元数据的消息对象
    """
    additional_kwargs = {
        "ggl_related_node_id": node_id,
        "ggl_related_node_label": node_label,
    }
    
    if message_type == "ai":
        return AIMessage(
            content=content,
            additional_kwargs=additional_kwargs
        )
    else:
        return HumanMessage(
            content=content,
            additional_kwargs=additional_kwargs
        )


# 示例 1: 在 GGL 中间件中添加节点关联
def example_ggl_middleware_usage():
    """
    在 GGL 中间件中自动为消息添加当前活跃节点信息
    """
    # 假设我们有当前的 GGL 状态
    active_node_id = "ml_basics_001"
    active_node = {
        "id": active_node_id,
        "label": "机器学习基础"
    }
    
    # 创建 AI 回复消息时添加节点关联
    response_content = "机器学习是人工智能的一个分支..."
    
    message = create_node_related_message(
        content=response_content,
        node_id=active_node["id"],
        node_label=active_node["label"],
        message_type="ai"
    )
    
    return message


# 示例 2: 在工具调用后添加节点关联
def example_tool_message_with_node():
    """
    在工具执行后为结果消息添加节点关联
    """
    # 假设用户刚刚更新了某个节点
    updated_node_id = "supervised_learning_002"
    updated_node_label = "监督学习"
    
    # 创建工具执行结果消息
    tool_result = "节点状态已更新为 'exploring'"
    
    message = create_node_related_message(
        content=f"好的，我们开始学习{updated_node_label}。{tool_result}",
        node_id=updated_node_id,
        node_label=updated_node_label,
        message_type="ai"
    )
    
    return message


# 示例 3: 批量处理历史消息添加节点关联
def add_node_relation_to_existing_messages(
    messages: list,
    node_mapping: dict[str, dict]
) -> list:
    """
    为现有消息批量添加节点关联
    
    Args:
        messages: 现有消息列表
        node_mapping: 消息索引到节点的映射
            格式: {message_index: {"id": "node_id", "label": "node_label"}}
    
    Returns:
        更新后的消息列表
    """
    updated_messages = []
    
    for idx, msg in enumerate(messages):
        if idx in node_mapping:
            node_info = node_mapping[idx]
            # 更新消息的 additional_kwargs
            msg.additional_kwargs = msg.additional_kwargs or {}
            msg.additional_kwargs.update({
                "ggl_related_node_id": node_info["id"],
                "ggl_related_node_label": node_info["label"],
            })
        updated_messages.append(msg)
    
    return updated_messages


# 示例 4: 在 Lead Agent 中集成
def example_lead_agent_integration(state, config):
    """
    在 Lead Agent 的消息生成流程中集成节点关联
    
    这是一个伪代码示例，展示集成点
    """
    # 1. 从状态中获取 GGL 信息
    ggl_state = state.get("ggl")
    if not ggl_state:
        # 非 GGL 模式，正常处理
        return normal_message_generation(state, config)
    
    active_node_id = ggl_state.get("active_node_id")
    topic_graph = ggl_state.get("topic_graph")
    
    # 2. 找到当前活跃节点的标签
    active_node_label = None
    if active_node_id and topic_graph:
        for node in topic_graph["nodes"]:
            if node["id"] == active_node_id:
                active_node_label = node["label"]
                break
    
    # 3. 生成回复内容
    response_content = generate_ai_response(state, config)
    
    # 4. 创建带节点关联的消息
    if active_node_id and active_node_label:
        message = create_node_related_message(
            content=response_content,
            node_id=active_node_id,
            node_label=active_node_label,
            message_type="ai"
        )
    else:
        # 无活跃节点时，创建普通消息
        message = AIMessage(content=response_content)
    
    return message


# 示例 5: 工具函数 - 自动提取节点信息
def auto_extract_node_info_from_state(state):
    """
    从状态中自动提取节点关联信息的辅助函数
    
    Returns:
        (node_id, node_label) 元组，如果没有则返回 (None, None)
    """
    ggl_state = state.get("ggl")
    if not ggl_state:
        return None, None
    
    active_node_id = ggl_state.get("active_node_id")
    if not active_node_id:
        return None, None
    
    topic_graph = ggl_state.get("topic_graph")
    if not topic_graph or "nodes" not in topic_graph:
        return active_node_id, None
    
    # 查找节点标签
    for node in topic_graph["nodes"]:
        if node["id"] == active_node_id:
            return active_node_id, node.get("label")
    
    return active_node_id, None


# 推荐的集成方式
"""
在 backend/src/agents/middlewares/ggl_middleware.py 中：

1. 在 before_generate_response 中：
   - 提取当前 active_node_id 和 label
   - 保存到 config 或临时变量中

2. 在 after_generate_response 中：
   - 为生成的 AI 消息添加 additional_kwargs
   - 包含 ggl_related_node_id 和 ggl_related_node_label

示例代码：

class GGLMiddleware(BaseMiddleware):
    async def before_generate_response(self, state, config):
        node_id, node_label = auto_extract_node_info_from_state(state)
        config["ggl_current_node"] = {
            "id": node_id,
            "label": node_label
        }
        return state
    
    async def after_generate_response(self, response, state, config):
        node_info = config.get("ggl_current_node")
        if node_info and node_info["id"]:
            # 为最后一条 AI 消息添加节点关联
            if response.messages and isinstance(response.messages[-1], AIMessage):
                last_msg = response.messages[-1]
                last_msg.additional_kwargs = last_msg.additional_kwargs or {}
                last_msg.additional_kwargs.update({
                    "ggl_related_node_id": node_info["id"],
                    "ggl_related_node_label": node_info["label"],
                })
        return response
"""


if __name__ == "__main__":
    # 测试示例
    print("=== 示例 1: 基本使用 ===")
    msg1 = example_ggl_middleware_usage()
    print(f"Content: {msg1.content}")
    print(f"Node ID: {msg1.additional_kwargs.get('ggl_related_node_id')}")
    print(f"Node Label: {msg1.additional_kwargs.get('ggl_related_node_label')}")
    
    print("\n=== 示例 2: 工具消息 ===")
    msg2 = example_tool_message_with_node()
    print(f"Content: {msg2.content}")
    print(f"Node Info: {msg2.additional_kwargs}")
