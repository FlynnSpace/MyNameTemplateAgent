import json
from langchain_core.messages import HumanMessage
from state.schemas import AgentState
from utils.logger import get_logger

logger = get_logger("mynamechat.nodes.common")

def log_system_message(message: str, echo: bool = False) -> None:
    """Helper to log a system-level message and optionally echo to console."""
    logger.info(message)
    if echo:
        print(message)

def prepare_state_from_payload(query_json: dict, state: AgentState) -> AgentState:
    """
    输入预处理：
    - 解析 user_query 与 references
    - 写入 messages
    - 打日志（log_system_message 会同时输出到控制台与文件）
    """
    query = query_json.get("user_query", "")
    refs = query_json.get("references", [])

    state["references"] = refs
    
    if query:
        state.setdefault("messages", []).append(HumanMessage(content=query))
        log_system_message(f"[INPUT] JSON 解析成功 - query: {query[:50]}{'...' if len(query) > 50 else ''}", echo=False)
    else:
        log_system_message("[INPUT] Query 为空，跳过添加 HumanMessage (可能是 State 传递)", echo=False)

    log_system_message(f"[INPUT] references 数量: {len(refs)}", echo=False)
    if refs:
        for i, ref in enumerate(refs):
            log_system_message(f"[INPUT]   [{i+1}] url: {ref.get('url', 'N/A')[:80]}", echo=False)
    else:
        log_system_message("[INPUT]   (空列表)", echo=False)
    log_system_message(f"[INPUT] last_task_id: {state.get('last_task_id', 'None')}", echo=False)
    log_system_message(f"[INPUT] last_tool_name: {state.get('last_tool_name', 'None')}", echo=False)

    return state

def initial_prep_node(input_dict: dict) -> AgentState:
    """
    图的第一个节点：将外部原始输入 (input_dict) 转换为 AgentState。
    LangGraph Server 部署时，HTTP 请求体解析后的字典会作为 input_dict 传入。
    """
    # 1. 只需要处理本次请求相关的字段 (messages, references)
    # 不要重置 last_task_id 等持久化字段，否则会丢失历史状态
    partial_state = {
        "references": [],
        "model_call_count": 0, # 每次新用户输入，重置计数器
        "suggestions": [], # 重置建议
        # "last_task_id": None,  <-- 移除这些重置操作
        # "last_tool_name": None,
        # "last_task_config": None,
        # "global_config": None
    }
    
    # 2. 调用预处理逻辑，解析输入并填入 partial_state
    return prepare_state_from_payload(input_dict, partial_state)


def recorder_node(state: AgentState) -> AgentState:
    """记录器节点：从工具执行结果中提取状态和更新 References"""
    messages = state["messages"]
    new_state = {}
    
    log_system_message("--- [DEBUG] Entering recorder_node ---", echo=False)
    
    # 倒序遍历寻找最近的 AIMessage (获取参数)
    last_ai_message = None
    for msg in reversed(messages):
        # 检查是否是 AI 消息且有 tool_calls
        if msg.type == "ai" and hasattr(msg, "tool_calls") and msg.tool_calls:
            last_ai_message = msg
            break
            
    if not last_ai_message:
        log_system_message("--- [DEBUG] Recorder: No AI message with tool_calls found.", echo=False)
        return {}

    # 建立 ID 到参数的映射
    call_id_to_args = {call["id"]: call["args"] for call in last_ai_message.tool_calls}
    call_id_to_name = {call["id"]: call["name"] for call in last_ai_message.tool_calls}
    
    log_system_message(f"--- [DEBUG] Found Tool Calls: {list(call_id_to_name.values())}", echo=False)

    # 倒序查找最近的 ToolMessage
    for msg in reversed(messages):
        if msg.type == "tool":
            tool_call_id = msg.tool_call_id
            
            # 只处理属于当前 AI 消息的 ToolMessage
            if tool_call_id in call_id_to_args:
                tool_name = call_id_to_name[tool_call_id]
                log_system_message(f"--- [DEBUG] Processing ToolMessage for: {tool_name}", echo=False)
                
                # 1. 如果是生成类任务 -> 记录 ID, Config, ToolName
                if "create_task" in tool_name:
                    task_payload = msg.content
                    log_system_message(f"--- [DEBUG] Raw Payload: {task_payload}", echo=False)
                    
                    task_id = None
                    if isinstance(task_payload, dict):
                        task_id = task_payload.get("task_id") or task_payload.get("id")
                    elif isinstance(task_payload, str):
                        candidate = task_payload.strip()
                        if candidate.startswith("{") and candidate.endswith("}"):
                            try:
                                parsed = json.loads(candidate)
                                task_id = parsed.get("task_id") or parsed.get("id")
                            except json.JSONDecodeError:
                                task_id = candidate
                        else:
                            task_id = candidate
                    elif task_payload:
                        task_id = str(task_payload)

                    if not task_id:
                        log_system_message(f"--- [DEBUG] ❌ FAILED to extract task_id", echo=False)
                        logger.warning("Recorder: tool %s returned no task_id payload=%s", tool_name, task_payload)
                        continue

                    log_system_message(f"--- [DEBUG] ✅ CAPTURED task_id: {task_id}, tool_name: {tool_name}, config: {call_id_to_args[tool_call_id]}", echo=False)
                    logger.info("Recorder captured task %s via tool %s", task_id, tool_name)
                    
                    new_state["last_task_id"] = task_id
                    new_state["last_tool_name"] = tool_name
                    new_state["last_task_config"] = call_id_to_args[tool_call_id]

                    break 
                        
    return new_state

