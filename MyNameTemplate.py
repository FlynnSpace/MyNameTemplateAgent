import json
from typing import Annotated, Sequence
from openai.types.responses.response_reasoning_item import Summary
from typing_extensions import TypedDict
from dotenv import load_dotenv  
from langchain_core.messages import BaseMessage # The foundational class for all message types in LangGraph
from langchain_core.messages import ToolMessage # Passes data back to LLM after it calls a tool such as the content and the tool_call_id
from langchain_core.messages import SystemMessage # Message for providing instructions to the LLM
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from KIE_tools import *
# Explicitly import helper functions since 'from KIE_tools import *' skips underscores
from KIE_tools import _get_ppio_task_status_impl, _get_kie_task_status_impl 
from tool_prompts import SYSTEM_PROMPT
from pydantic import BaseModel, Field
from logger_util import get_logger


load_dotenv()
logger = get_logger("mynamechat.agent")


def log_system_message(message: str, echo: bool = False) -> None:
    """Helper to log a system-level message and optionally echo to console."""
    logger.info(message)
    if echo:
        print(message)

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    last_task_id: str | None  # 记录最近一个任务的ID，用于编辑图像时，如果用户没有指定URL，且没有提到retry，则使用此值进行查询
    last_tool_name: str | None # 记录最近一个任务使用的工具名称，用于区分get_kie_task_status和get_ppio_task_status
    last_task_config: dict | None  # 记录最近一个任务的配置，用于编辑图像时，如果用户没有指定URL，且说RETRY则使用此值进行重新生成
    global_config: dict | None  # 记录全局配置，用于储存模板的配置，用于agent的背景知识填入API调用参数
    references: list[dict] | None  # 记录参考素材，有URL时负责记录，无URL时负责指代参考素材

class AgentResponse(BaseModel):
    answer: str = Field(description="The answer to the user's question")
    suggestions: list[str] = Field(description="The suggestions for the user to choose from")

tools = [
    # text_to_image_by_seedream_v4_model_create_task,
    image_edit_by_ppio_banana_pro_create_task,
    # get_task_status,
    text_to_video_by_kie_sora2_create_task,
    first_frame_to_video_by_kie_sora2_create_task,
    remove_watermark_from_image_by_kie_seedream_v4_create_task
    ]  # max function name length is 64

llm = ChatOpenAI(model = "gpt-5-nano",
                 temperature=0.0)

structured_llm = llm.with_structured_output(
    schema=AgentResponse,
    method="json_schema",
    strict=True,
    tools=tools,
    include_raw=True,
    reasoning_effort="medium"  # Can be "low", "medium", or "high"
    )


def recorder_node(state: AgentState) -> AgentState:
    """记录器节点：从工具执行结果中提取状态和更新 References"""
    messages = state["messages"]
    new_state = {}
    
    # 倒序遍历寻找最近的 AIMessage (获取参数)
    last_ai_message = None
    for msg in reversed(messages):
        # 检查是否是 AI 消息且有 tool_calls
        if msg.type == "ai" and hasattr(msg, "tool_calls") and msg.tool_calls:
            last_ai_message = msg
            break
            
    if not last_ai_message:
        logger.debug("Recorder: no AI message with tool_calls, skip")
        return {}

    # 建立 ID 到参数的映射
    call_id_to_args = {call["id"]: call["args"] for call in last_ai_message.tool_calls}
    call_id_to_name = {call["id"]: call["name"] for call in last_ai_message.tool_calls}

    # 倒序查找最近的 ToolMessage
    for msg in reversed(messages):
        if msg.type == "tool":
            tool_call_id = msg.tool_call_id
            
            # 只处理属于当前 AI 消息的 ToolMessage
            if tool_call_id in call_id_to_args:
                tool_name = call_id_to_name[tool_call_id]
                
                # 1. 如果是生成类任务 -> 记录 ID, Config, ToolName
                if "create_task" in tool_name:
                    task_payload = msg.content
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
                        logger.warning("Recorder: tool %s returned no task_id payload=%s", tool_name, task_payload)
                        continue

                    logger.info("Recorder captured task %s via tool %s", task_id, tool_name)
                    
                    new_state["last_task_id"] = task_id
                    new_state["last_tool_name"] = tool_name
                    new_state["last_task_config"] = call_id_to_args[tool_call_id]

                    break 
                        
    return new_state


def model_call(state:AgentState) -> AgentState:
    """模型调用节点：负责构建 Prompt 并调用 LLM，同时处理自动加载逻辑"""
    
    # --- 自动加载上一轮生成结果 (Auto-Load Logic) ---
    # 保留自动查询：即使前端也会传回 URL，我们仍提供"无感知兜底"体验，
    # 尤其在用户连续编辑、没有选择 ref 时，可以自动查询上一轮任务结果，减轻人工操作
    
    current_refs = state.get("references", [])
    last_tid = state.get("last_task_id")
    last_tool = state.get("last_tool_name")
    
    # 如果当前没有引用，且有上一轮任务，且上一轮是图像编辑任务，尝试自动加载
    if not current_refs:
        if last_tid and last_tool and "image_edit" in last_tool.lower():
            fetched_url = None
            log_system_message(f"[系统] 尝试自动加载上一轮任务结果 (ID: {last_tid})...", echo=True)
            
            # 根据 Last Tool Name 决定调用哪个查询函数 (复用 KIE_tools 内部逻辑)
            if "ppio" in last_tool.lower() or "banana" in last_tool.lower():
                try:
                    res = _get_ppio_task_status_impl(last_tid)
                    if isinstance(res, str) and res.startswith("http"):
                        fetched_url = res
                except Exception as e:
                    log_system_message(f"[系统] PPIO 查询失败: {e}", echo=True)
            else:
                try:
                    res = _get_kie_task_status_impl(last_tid)
                    if isinstance(res, str) and res.startswith("http"):
                        fetched_url = res
                except Exception as e:
                     log_system_message(f"[系统] KIE 查询失败: {e}", echo=True)
            
            if fetched_url:
                log_system_message(f"[系统] ✅ 成功加载上一轮结果: {fetched_url}", echo=True)
                # 直接更新 state，本轮生效；因为不返回，所以不会持久化到下一轮
                state["references"] = [{"url": fetched_url, "desc": "Last Generation Result (Auto-loaded)"}]
            else:
                log_system_message("[系统] ⏳ 上一轮任务仍在处理中或无法获取结果。", echo=True)
        else:
            logger.debug(
                "AutoLoad skipped: refs=%s last_tid=%s last_tool=%s",
                current_refs,
                last_tid,
                last_tool,
            )

    # 1. 注入动态上下文
    context_str = ""
    
    # 注入素材库 (使用本轮的 references，可能来自用户输入或自动加载)
    if state.get("references"):
        context_str += "\n### [REFERENCES]\n"
        for idx, asset in enumerate(state["references"]):
            context_str += f"{idx+1}. {asset.get('desc', 'Image')}: {asset.get('url')}\n"

    # 注入全局风格配置
    if state.get("global_config"):
        import json
        context_str += f"\n### [GLOBAL CONFIG]\n{json.dumps(state['global_config'], ensure_ascii=False)}\n"
        context_str += "INSTRUCTION: Always use these parameters (resolution, aspect_ratio, art_style, etc.) when calling tools unless the user explicitly overrides them in query.\n"

    if state.get("last_task_id"):
        context_str += f"\n[MEMORY] Last Task ID: {state['last_task_id']}"
    if state.get("last_task_config"):
        context_str += f"\n[MEMORY] Last Task Config: {state['last_task_config']}"
        
    # 2. 组合 Prompt
    system_prompt = SystemMessage(content=SYSTEM_PROMPT.format(tools_description=str(tools)) + context_str)
    
    # 3. 调用模型
    response = structured_llm.invoke([system_prompt] + state["messages"])
    raw_response = response["raw"]
    
    # 只返回 messages，不返回 references
    # references 会在本轮使用后，由 recorder_node 强制清空，避免持久化到下一轮
    return {"messages": [raw_response]}


def should_continue(state: AgentState): 
    """判断是否继续调用工具"""
    messages = state["messages"]
    last_message = messages[-1]
    if hasattr(last_message, 'tool_calls') and not last_message.tool_calls: 
        return "end"
    else:
        return "continue"
    

graph = StateGraph(AgentState)
graph.add_node("our_agent", model_call)


tool_node = ToolNode(tools=tools)
graph.add_node("tools", tool_node)
graph.add_node("recorder", recorder_node)

graph.set_entry_point("our_agent")

graph.add_conditional_edges(
    "our_agent",
    should_continue,
    {
        "continue": "tools",
        "end": END,
    },
)

graph.add_edge("tools", "recorder")
graph.add_edge("recorder", "our_agent")

app = graph.compile()

def print_stream(stream):
    for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()


async def chat_async():
    """持续对话模式 - Token级流式输出"""
    from langchain_core.messages import AIMessage, HumanMessage
    
    # 欢迎界面
    print("\n" + "=" * 60)
    print("🎬  AI 视频/图像生成助手 - 《你的名字》续集模板")
    print("=" * 60)
    
    # AI 的开场白
    greeting = ("你好！我是你的 AI 创作助手。\n"
                "我可以帮你基于《你的名字》创作续集内容：\n"
                "📷 根据角色参考图生成新图像\n"
                "🎬 通过文本或首帧生成视频\n"
                "输入 '退出' 或 'exit' 结束对话。")
    
    # 初始化 AgentState
    state: AgentState = {"messages": [AIMessage(content=greeting)]}
    print(f"\nAI: {greeting}\n")
    
    while True:
        user_input = input("你: ")
        
        # 退出检测
        if user_input.lower() in ["exit", "quit", "退出"]:
            print("👋 再见！")
            break
        if not user_input.strip():
            continue

        log_system_message(f"[INPUT] 用户输入: {user_input[:100]}{'...' if len(user_input) > 100 else ''}", echo=True)
        # 尝试解析 JSON 输入
        try:
            input_data = json.loads(user_input)
            query = input_data.get("user_query", "")
            # 显式覆盖 references
            incoming_refs = input_data.get("references", [])
            state["references"] = incoming_refs
            
            # 添加用户消息 (只包含 query)
            state["messages"].append(HumanMessage(content=query))
            
            # 日志记录 JSON 解析结果
            log_system_message(f"[INPUT] JSON 解析成功 - query: {query[:50]}{'...' if len(query) > 50 else ''}", echo=True)
            log_system_message(f"[INPUT] references 数量: {len(incoming_refs)}", echo=True)
            if incoming_refs:
                for i, ref in enumerate(incoming_refs):
                    log_system_message(f"[INPUT]   [{i+1}] url: {ref.get('url', 'N/A')[:80]}", echo=True)
            else:
                log_system_message("[INPUT]   (空列表)", echo=True)
            log_system_message(f"[INPUT] last_task_id: {state.get('last_task_id', 'None')}", echo=True)
            log_system_message(f"[INPUT] last_tool_name: {state.get('last_tool_name', 'None')}", echo=True)
            
        except json.JSONDecodeError:
            # 普通文本输入 -> 清空上一轮的参考素材
            state["references"] = []
            
            # 日志记录纯文本解析
            log_system_message("[INPUT] 纯文本输入 (非 JSON)", echo=True)
            log_system_message("[INPUT] references: [] (已清空)", echo=True)
            log_system_message(f"[INPUT] last_task_id: {state.get('last_task_id', 'None')}", echo=True)
            log_system_message(f"[INPUT] last_tool_name: {state.get('last_tool_name', 'None')}", echo=True)
            # Config 可以选择保留（因为它通常是全局的），或者也清空？
            # 根据你的需求"每次都根据用户的新提问来决定"，这里最好也重置，或者是保持默认。
            # 但通常 Config (风格) 是相对稳定的，Assets (素材) 是易变的。
            # 为了安全起见，且符合"无状态"设计，我们这里选择不主动清空 Config (假设用户没传就是沿用旧的或者默认)，
            # 但 Assets 必须清空。
            
            state["messages"].append(HumanMessage(content=user_input))
        
        # 使用 Token 级流式输出
        print()
        
        # 跟踪状态
        in_agent_response = False
        shown_ai_prefix = False
        
        # 使用 astream_events 实现 Token 级流式（只执行一次）
        async for event in app.astream_events(state, version="v2"):
            kind = event["event"]
            
            # 捕获 LLM 的流式 token
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    if not shown_ai_prefix:
                        print("AI: ", end="", flush=True)
                        shown_ai_prefix = True
                    print(content, end="", flush=True)
                    in_agent_response = True
            
            # 捕获工具调用信息
            elif kind == "on_tool_start":
                tool_name = event["name"]
                if in_agent_response:
                    print()  # 换行
                    in_agent_response = False
                print(f"\n[🔧 调用工具: {tool_name}]", flush=True)
                shown_ai_prefix = False  # 重置，下次模型输出时再显示
            
            elif kind == "on_tool_end":
                print(f"[✓ 工具执行完成]\n", flush=True)
                in_agent_response = False
            
            # 捕获最终状态更新
            elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                # 获取最终输出状态
                state = event["data"]["output"]
        
        print("\n")  # 空行分隔


def chat():
    """同步包装器 - 调用异步 chat 函数"""
    import asyncio
    
    try:
        asyncio.run(chat_async())
    except KeyboardInterrupt:
        print("\n\n程序已中断。再见！")


if __name__ == "__main__":
    chat()
