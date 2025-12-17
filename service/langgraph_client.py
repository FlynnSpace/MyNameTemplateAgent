"""
LangGraph SDK 客户端封装
通过 SDK 调用 langgraph dev 服务，复用其持久化和流式功能
"""

import os
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
    """
    创建新的 Thread
    
    Args:
        metadata: 可选的元数据
        
    Returns:
        包含 thread_id 的字典
    """
    client = get_langgraph_client()
    thread = await client.threads.create(metadata=metadata or {})
    logger.info(f"创建新 Thread: {thread['thread_id']}")
    return thread


async def get_thread(thread_id: str) -> dict | None:
    """
    获取 Thread 信息
    
    Args:
        thread_id: Thread ID
        
    Returns:
        Thread 信息，不存在则返回 None
    """
    client = get_langgraph_client()
    try:
        thread = await client.threads.get(thread_id)
        return thread
    except Exception as e:
        logger.warning(f"Thread {thread_id} 不存在: {e}")
        return None


async def get_thread_state(thread_id: str) -> dict | None:
    """
    获取 Thread 状态（包含历史消息等）
    
    Args:
        thread_id: Thread ID
        
    Returns:
        Thread 状态
    """
    client = get_langgraph_client()
    try:
        state = await client.threads.get_state(thread_id)
        return state
    except Exception as e:
        logger.warning(f"获取 Thread 状态失败: {e}")
        return None


# ============================================================
# 简洁流式对话 (核心接口)
# ============================================================

async def chat_stream_simple(
    message: str,
    thread_id: str | None = None,
    agent_type: str = "planner_supervisor",
    deep_thinking: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    简洁流式对话 - 只返回关键信息
    
    使用 updates 模式，过滤只保留:
    - Coordinator 的直接回复 (简单问题)
    - Planner 的 thought (复杂任务)
    - Executor 的执行进度
    - Reporter 的 final_report
    
    Args:
        message: 用户消息
        thread_id: Thread ID（可选）
        agent_type: Agent 类型
        deep_thinking: 是否启用深度思考模式
        
    Yields:
        简洁的流式事件:
        - start: 开始，包含 thread_id
        - response: Coordinator 直接回复
        - planning: Planner 的思考过程
        - executing: 执行进度
        - report: Reporter 的最终报告
        - end: 结束，包含汇总信息
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
    
    logger.info(f"简洁流式对话: thread_id={thread_id}, assistant={assistant_id}")
    
    # 构建输入
    input_data = {
        "messages": [{"role": "user", "content": message}],
        "deep_thinking_mode": deep_thinking,
    }
    
    # 发送开始事件
    yield {
        "event": "start",
        "thread_id": thread_id,
    }
    
    # 收集执行信息
    task_ids = []
    step_results = []
    plan_title = ""
    
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
                # Coordinator 节点 - 直接回复 (简单问题)
                # ============================================================
                if node_name == "coordinator":
                    messages = node_data.get("messages", [])
                    for msg in messages:
                        # 检查是否是 AI 回复
                        if msg.get("type") == "ai" and msg.get("content"):
                            content = msg.get("content", "")
                            # 排除 handoff_to_planner 的情况
                            if "handoff_to_planner" not in content:
                                yield {
                                    "event": "response",
                                    "content": content,
                                    "from": "coordinator",
                                }
                
                # ============================================================
                # Planner 节点 - 返回 thought
                # ============================================================
                elif node_name == "planner":
                    thought = node_data.get("plan_thought", "")
                    title = node_data.get("plan_title", "")
                    total_steps = node_data.get("total_steps", 0)
                    plan_title = title
                    
                    if thought:
                        yield {
                            "event": "planning",
                            "thought": thought,
                            "title": title,
                            "total_steps": total_steps,
                        }
                
                # ============================================================
                # Executor 节点 - 返回执行进度
                # ============================================================
                elif node_name in ["image_executor", "video_executor", "general_executor"]:
                    new_results = node_data.get("step_results", [])
                    if new_results and len(new_results) > len(step_results):
                        # 只发送新增的结果
                        latest = new_results[-1]
                        step_results = new_results
                        
                        task_id = latest.get("task_id")
                        if task_id:
                            task_ids.append(task_id)
                        
                        yield {
                            "event": "executing",
                            "executor": latest.get("executor", node_name),
                            "step_index": latest.get("step_index", 0),
                            "status": latest.get("status", "unknown"),
                            "task_id": task_id,
                            "summary": latest.get("summary", ""),
                        }
                
                # ============================================================
                # Reporter 节点 - 返回 final_report
                # ============================================================
                elif node_name == "reporter":
                    final_report = node_data.get("final_report", "")
                    
                    if final_report:
                        yield {
                            "event": "report",
                            "content": final_report,
                        }
        
        # 发送结束事件，包含汇总信息
        yield {
            "event": "end",
            "thread_id": thread_id,
            "summary": {
                "title": plan_title,
                "task_ids": list(set(task_ids)),
                "total_steps": len(step_results),
            }
        }
        
    except Exception as e:
        logger.error(f"简洁流式调用失败: {e}", exc_info=True)
        yield {
            "event": "error",
            "error": str(e),
        }


# ============================================================
# 历史记录查询
# ============================================================

async def get_thread_history(thread_id: str) -> list[dict]:
    """
    获取 Thread 的历史消息
    
    Args:
        thread_id: Thread ID
        
    Returns:
        消息列表
    """
    state = await get_thread_state(thread_id)
    if state and state.get("values"):
        return state["values"].get("messages", [])
    return []


async def list_threads(limit: int = 20, offset: int = 0) -> list[dict]:
    """
    列出所有 Threads
    
    Args:
        limit: 返回数量
        offset: 偏移量
        
    Returns:
        Thread 列表
    """
    client = get_langgraph_client()
    try:
        threads = await client.threads.list(limit=limit, offset=offset)
        return list(threads)
    except Exception as e:
        logger.error(f"列出 Threads 失败: {e}")
        return []


async def delete_thread(thread_id: str) -> bool:
    """
    删除 Thread
    
    Args:
        thread_id: Thread ID
        
    Returns:
        是否成功
    """
    client = get_langgraph_client()
    try:
        await client.threads.delete(thread_id)
        logger.info(f"删除 Thread: {thread_id}")
        return True
    except Exception as e:
        logger.error(f"删除 Thread 失败: {e}")
        return False
