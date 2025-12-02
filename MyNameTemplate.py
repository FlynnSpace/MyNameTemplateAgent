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
from tool_prompts import SYSTEM_PROMPT
from pydantic import BaseModel, Field


load_dotenv()

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    last_task_id: str | None
    last_task_config: dict | None

class AgentResponse(BaseModel):
    answer: str = Field(description="The answer to the user's question")
    suggestions: list[str] = Field(description="The suggestions for the user to choose from")

tools = [
    # text_to_image_by_seedream_v4_model_create_task,
    image_edit_by_ppio_banana_pro_create_task,
    get_task_status,
    get_ppio_task_status,
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


def recorder_node(state: AgentState):
    """记录器节点：从工具执行结果中提取状态"""
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
        return {}

    # 建立 ID 到参数的映射
    call_id_to_args = {call["id"]: call["args"] for call in last_ai_message.tool_calls}
    call_id_to_name = {call["id"]: call["name"] for call in last_ai_message.tool_calls}

    # 倒序查找最近的 ToolMessage
    for msg in reversed(messages):
        if msg.type == "tool":
            tool_call_id = msg.tool_call_id
            if tool_call_id in call_id_to_args:
                tool_name = call_id_to_name[tool_call_id]
                
                # 只有生成类任务才需要记录
                if "create_task" in tool_name:
                    # 提取 ID (content) 和 Config (args)
                    new_state["last_task_id"] = str(msg.content)
                    new_state["last_task_config"] = call_id_to_args[tool_call_id]
                    break # 只记录最近的一个
        elif msg.type == "ai":
            # 遇到 AI 消息停止，说明这轮 Tool 执行的消息已经遍历完了
            break
            
    return new_state


def model_call(state:AgentState) -> AgentState:
    # 1. 注入动态上下文
    context_str = ""
    if state.get("last_task_id"):
        context_str += f"\n[MEMORY] Last Task ID: {state['last_task_id']}"
    if state.get("last_task_config"):
        context_str += f"\n[MEMORY] Last Task Config: {state['last_task_config']}"
        
    # 2. 组合 Prompt
    system_prompt = SystemMessage(content=SYSTEM_PROMPT.format(tools_description=str(tools)) + context_str)
    
    # 3. 调用模型
    response = structured_llm.invoke([system_prompt] + state["messages"])
    raw_response = response["raw"]
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
        
        # 检查退出命令
        if user_input.lower().strip() in ["退出", "exit", "quit", "结束", "再见"]:
            print("\nAI: 再见！期待下次为你创作精彩内容。👋\n")
            break
        
        # 检查空输入
        if not user_input.strip():
            print("AI: 请输入有效的内容。\n")
            continue
        
        # 添加用户消息到 state
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
