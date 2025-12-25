"""
LangGraph SDK 客户端封装
通过 SDK 调用 langgraph dev 服务，使用 custom stream mode 透传节点发送的流式数据

流式返回设计:
- 使用 stream_mode="custom" 接收节点主动发送的数据
- 节点直接发送格式化的数据：delta/thought/tool_name+tool_result
- 客户端只需透传，无需二次处理
"""

import os
import uuid
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
# 流式对话 (核心接口) - 使用 custom stream mode
# ============================================================

async def chat_stream_simple(
    message: str,
    thread_id: str | None = None,
    agent_type: str = "planner_supervisor",
    deep_thinking: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    简洁流式对话 - 使用 custom stream mode
    
    节点直接发送格式化的数据：
    - coordinator/reporter: {"delta": "..."}
    - planner: {"thought": "..."}
    - executors: {"tool_name": "...", "tool_result": "..."}
    
    客户端只需透传，包装成 SSE 格式返回。
    
    Args:
        message: 用户消息
        thread_id: Thread ID（可选）
        agent_type: Agent 类型
        deep_thinking: 是否启用深度思考模式
    """
    client = get_langgraph_client()
    
    # 获取对应的 assistant_id
    assistant_id = AGENT_MAPPING.get(agent_type)
    if not assistant_id:
        yield {
            "event": "message",
            "data": {
                "type": "error",
                "error": f"Unknown agent_type: {agent_type}, expected: 'react' or 'planner_supervisor'",
            }
        }
        return
    
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
    
    try:
        # 使用 custom 模式流式调用 - 节点主动发送的数据会通过这里返回
        async for chunk in client.runs.stream(
            thread_id=thread_id,
            assistant_id=assistant_id,
            input=input_data,
            stream_mode="custom",  # 只使用 custom 模式
        ):
            # chunk.event 应该是 "custom"
            # chunk.data 是节点通过 writer() 发送的数据
            if chunk.event == "custom" and chunk.data:
                # 直接透传节点发送的数据
                yield {
                    "event": "message",
                    "data": chunk.data,
                }
        
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
