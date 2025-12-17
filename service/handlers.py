"""
Service 层业务处理逻辑
封装与 LangGraph Agent 的交互
"""

import os
from typing import Any
from dotenv import load_dotenv

from utils.logger import get_logger, set_logger_context

# 初始化
load_dotenv()
set_logger_context("loopskill.service.handlers")
logger = get_logger("loopskill.service.handlers")


# ============================================================
# Agent 实例管理
# ============================================================

_agents: dict[str, Any] = {}


def get_react_agent():
    """获取 ReAct 模式 Agent"""
    if "react" not in _agents:
        from apps.MyNameTemplate_suggestion import app
        _agents["react"] = app
        logger.info("ReAct Agent 已加载")
    return _agents["react"]


def get_planner_supervisor_agent():
    """获取 Planner-Supervisor 模式 Agent"""
    if "planner_supervisor" not in _agents:
        from apps.PlannerSupervisorTemplate import app
        _agents["planner_supervisor"] = app
        logger.info("Planner-Supervisor Agent 已加载")
    return _agents["planner_supervisor"]


def get_agent(agent_type: str):
    """根据类型获取 Agent"""
    if agent_type == "react":
        return get_react_agent()
    elif agent_type == "planner_supervisor":
        return get_planner_supervisor_agent()
    else:
        raise ValueError(f"未知的 Agent 类型: {agent_type}")


# ============================================================
# 任务状态查询
# ============================================================

async def get_task_status(task_id: str, task_type: str = "image") -> dict:
    """
    查询任务状态
    
    Args:
        task_id: 任务ID
        task_type: 任务类型 (image/video)
        
    Returns:
        任务状态字典
    """
    try:
        # 使用现有的工具函数查询状态
        from tools.general import get_task_status as query_status
        
        result = query_status.invoke({"task_id": task_id})
        
        # 解析结果
        if "completed" in result.lower() or "success" in result.lower():
            status = "completed"
        elif "failed" in result.lower() or "error" in result.lower():
            status = "failed"
        elif "processing" in result.lower() or "running" in result.lower():
            status = "processing"
        else:
            status = "pending"
        
        # 尝试提取 URL
        result_url = None
        if "http" in result:
            import re
            urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', result)
            if urls:
                result_url = urls[0]
        
        return {
            "success": True,
            "message": "查询成功",
            "task_id": task_id,
            "status": status,
            "progress": None,
            "result_url": result_url,
            "error_message": None if status != "failed" else result,
        }
        
    except Exception as e:
        logger.error(f"任务状态查询失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"查询失败: {str(e)}",
            "task_id": task_id,
            "status": "unknown",
            "progress": None,
            "result_url": None,
            "error_message": str(e),
        }


# ============================================================
# 健康检查
# ============================================================

async def check_health() -> dict:
    """
    服务健康检查
    
    Returns:
        健康状态字典
    """
    agents_status = {}
    
    # 检查各 Agent 是否可加载
    try:
        get_react_agent()
        agents_status["react"] = True
    except Exception as e:
        logger.warning(f"ReAct Agent 加载失败: {e}")
        agents_status["react"] = False
    
    try:
        get_planner_supervisor_agent()
        agents_status["planner_supervisor"] = True
    except Exception as e:
        logger.warning(f"Planner-Supervisor Agent 加载失败: {e}")
        agents_status["planner_supervisor"] = False
    
    # 判断整体状态
    if all(agents_status.values()):
        status = "healthy"
    elif any(agents_status.values()):
        status = "degraded"
    else:
        status = "unhealthy"
    
    return {
        "status": status,
        "version": "1.0.0",
        "agents": agents_status,
    }
