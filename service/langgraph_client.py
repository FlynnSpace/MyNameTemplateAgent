"""
LangGraph SDK 客户端封装
通过 SDK 调用 langgraph dev 服务，复用其持久化和流式功能

流式返回设计 (对标 planning_agent):
- event 统一为 "message"
- 数据统一包在 data 内部
- planner: thought 字段，逐字流式返回
- executor: tool_name + tool_result 字段，一次性返回
- reporter/coordinator: delta 字段，逐字流式返回
"""

import os
import json
import asyncio
from typing import AsyncGenerator
from dotenv import load_dotenv
from langgraph_sdk import get_client

from utils.logger import get_logger, set_logger_context

# 初始化
load_dotenv()
set_logger_context("loopskill.service.langgraph_client")
logger = get_logger("loopskill.service.langgraph_client")

# LangGraph 服务地址
LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://localhost:2024")

# Agent 名称映射 (对应 langgraph.json 中的 graphs)
AGENT_MAPPING = {
    "react": "my_name_suggestion_chat_agent",
    "planner_supervisor": "planner_supervisor_agent",
}

# 流式输出延迟 (秒)，设为 0 则无延迟
STREAM_DELAY = float(os.getenv("STREAM_DELAY", "0.02"))


def get_langgraph_client():
    """获取 LangGraph SDK 客户端"""
    return get_client(url=LANGGRAPH_URL)


# ============================================================
# Thread 管理
# ============================================================

async def create_thread(metadata: dict | None = None) -> dict:
    """创建新的 Thread"""
    client = get_langgraph_client()
    thread = await client.threads.create(metadata=metadata or {})
    logger.info(f"创建新 Thread: {thread['thread_id']}")
    return thread


async def get_thread(thread_id: str) -> dict | None:
    """获取 Thread 信息，不存在则返回 None"""
    client = get_langgraph_client()
    try:
        thread = await client.threads.get(thread_id)
        return thread
    except Exception as e:
        logger.warning(f"Thread {thread_id} 不存在: {e}")
        return None


# ============================================================
# 流式输出辅助函数
# ============================================================

async def stream_text(text: str, field: str, delay: float = STREAM_DELAY):
    """
    逐字流式输出文本
    
    Args:
        text: 要输出的文本
        field: 字段名 ("thought" 或 "delta")
        delay: 每个字符之间的延迟 (秒)
        
    Yields:
        {"event": "message", "data": {field: char}}
    """
    for char in text:
        yield {
            "event": "message",
            "data": {field: char}
        }
        if delay > 0:
            await asyncio.sleep(delay)


# ============================================================
# 流式对话 (核心接口)
# ============================================================

async def chat_stream_simple(
    message: str,
    thread_id: str | None = None,
    agent_type: str = "planner_supervisor",
    deep_thinking: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    简洁流式对话 - 对标 planning_agent 设计
    
    返回格式:
    - event: 统一为 "message"
    - data: 包含具体字段
    
    字段说明:
    - planner: {"thought": "..."} - 逐字流式返回
    - executor: {"tool_name": "...", "tool_result": "..."} - 一次性返回
    - reporter/coordinator: {"delta": "..."} - 逐字流式返回
    
    Args:
        message: 用户消息
        thread_id: Thread ID（可选）
        agent_type: Agent 类型
        deep_thinking: 是否启用深度思考模式
    """
    client = get_langgraph_client()
    
    # 获取对应的 assistant_id
    assistant_id = AGENT_MAPPING.get(agent_type, "planner_supervisor_agent")
    
    # 如果没有 thread_id，创建新的
    if not thread_id:
        thread = await create_thread()
        thread_id = thread["thread_id"]
    else:
        existing = await get_thread(thread_id)
        if not existing:
            thread = await create_thread()
            thread_id = thread["thread_id"]
    
    logger.info(f"流式对话: thread_id={thread_id}, assistant={assistant_id}")
    
    # 构建输入
    input_data = {
        "messages": [{"role": "user", "content": message}],
        "deep_thinking_mode": deep_thinking,
    }
    
    # 发送开始事件
    yield {
        "event": "message",
        "data": {
            "type": "start",
            "thread_id": thread_id,
        }
    }
    
    # 收集执行信息
    step_results = []
    
    try:
        # 使用 updates 模式流式调用
        async for chunk in client.runs.stream(
            thread_id=thread_id,
            assistant_id=assistant_id,
            input=input_data,
            stream_mode="updates",
        ):
            event_type = chunk.event
            data = chunk.data
            
            if event_type != "updates" or not data:
                continue
            
            # 处理各节点的更新
            for node_name, node_data in data.items():
                if node_data is None:
                    continue
                
                # ============================================================
                # Coordinator 节点 - 逐字流式返回 (简单问题)
                # ============================================================
                if node_name == "coordinator":
                    messages = node_data.get("messages", [])
                    for msg in messages:
                        if msg.get("type") == "ai" and msg.get("content"):
                            content = msg.get("content", "")
                            if "handoff_to_planner" not in content:
                                # 逐字流式返回
                                async for event in stream_text(content, "delta"):
                                    yield event
                
                # ============================================================
                # Planner 节点 - 逐字流式返回 thought + steps
                # ============================================================
                elif node_name == "planner":
                    thought = node_data.get("plan_thought", "")
                    full_plan = node_data.get("full_plan", "")
                    
                    if thought or full_plan:
                        # 构建流式内容
                        thought_content = _format_planner_output(thought, full_plan)
                        
                        # 逐字流式返回
                        async for event in stream_text(thought_content, "thought"):
                            yield event
                
                # ============================================================
                # Executor 节点 - 一次性返回 tool_name + tool_result
                # ============================================================
                elif node_name in ["image_executor", "video_executor", "status_checker"]:
                    new_results = node_data.get("step_results", [])
                    if new_results and len(new_results) > len(step_results):
                        latest = new_results[-1]
                        step_results = new_results
                        
                        # 获取实际调用的工具名称列表
                        tool_names = latest.get("tool_names", [])
                        # 使用第一个工具名称作为 tool_name（通常只有一个）
                        tool_name = tool_names[0] if tool_names else node_name
                        
                        # 构建 tool_result JSON
                        tool_result = {
                            "step_index": latest.get("step_index", 0),
                            "status": latest.get("status", "unknown"),
                            "task_id": latest.get("task_id"),
                            "summary": latest.get("summary", ""),
                        }
                        
                        yield {
                            "event": "message",
                            "data": {
                                "tool_name": tool_name,
                                "tool_result": json.dumps(tool_result, ensure_ascii=False),
                            }
                        }
                
                # ============================================================
                # Reporter 节点 - 逐字流式返回 delta
                # ============================================================
                elif node_name == "reporter":
                    final_report = node_data.get("final_report", "")
                    
                    if final_report:
                        # 逐字流式返回
                        async for event in stream_text(final_report, "delta"):
                            yield event
        
        # 发送结束事件
        yield {
            "event": "message",
            "data": {
                "type": "end",
                "thread_id": thread_id,
            }
        }
        
    except Exception as e:
        logger.error(f"流式调用失败: {e}", exc_info=True)
        yield {
            "event": "message",
            "data": {
                "type": "error",
                "error": str(e),
            }
        }


def _format_planner_output(thought: str, full_plan: str) -> str:
    """
    格式化 Planner 输出
    
    格式:
    Thought: {thought}
    
    1. {step 1.title}
    
    2. {step 2.title}
    """
    lines = []
    
    # 添加 Thought
    if thought:
        lines.append(f"Thought: {thought}")
        lines.append("")  # 空行
    
    # 解析 steps
    if full_plan:
        try:
            plan = json.loads(full_plan)
            steps = plan.get("steps", [])
            
            for i, step in enumerate(steps, 1):
                title = step.get("title", f"步骤 {i}")
                lines.append(f"{i}. {title}")
                lines.append("")  # 空行
                
        except (json.JSONDecodeError, TypeError):
            pass
    
    return "\n".join(lines)
