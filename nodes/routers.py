"""
路由器模块
提供各种条件路由函数，用于 LangGraph 工作流的条件边

包含:
- ReAct 模式路由 (原有)
- Planner-Supervisor 模式路由 (新增)
"""

from typing import Literal
from state.schemas import AgentState
from utils.logger import get_logger

logger = get_logger("loopskill.nodes.routers")


# ============================================================
# ReAct 模式路由 (保持原有功能)
# ============================================================

def should_continue(state: AgentState) -> Literal["continue", "end"]:
    """
    ReAct 模式：判断是否继续调用工具
    
    - continue: 有工具调用，继续执行
    - end: 无工具调用，结束
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "continue"
    else:
        return "end"


# ============================================================
# Planner-Supervisor 模式路由
# ============================================================

def coordinator_router(state: AgentState) -> Literal["planner", "__end__"]:
    """
    Coordinator 路由：判断是否需要规划
    
    - planner: 需要规划的复杂任务
    - __end__: 简单问候/直接回复
    """
    # 检查是否启用了规划模式
    enable_planning = state.get("enable_planning", False)
    
    if enable_planning:
        logger.info("Router: 路由到 planner")
        return "planner"
    else:
        logger.info("Router: 直接结束")
        return "__end__"


def planner_router(state: AgentState) -> Literal["supervisor", "__end__"]:
    """
    Planner 路由：检查计划是否有效
    
    - supervisor: 计划有效，开始执行
    - __end__: 计划无效，直接结束
    """
    full_plan = state.get("full_plan")
    
    if full_plan:
        logger.info("Router: 计划有效，路由到 supervisor")
        return "supervisor"
    else:
        logger.info("Router: 计划无效，结束")
        return "__end__"


def supervisor_router(state: AgentState) -> Literal["image_executor", "video_executor", "general_executor", "reporter", "__end__"]:
    """
    Supervisor 路由：根据决策路由到对应执行者
    
    读取 state.next_executor 进行路由
    """
    next_executor = state.get("next_executor", "FINISH")
    
    logger.info(f"Router: Supervisor 决策 = {next_executor}")
    
    if next_executor == "FINISH":
        return "__end__"
    
    # 验证执行者名称
    valid_executors = ["image_executor", "video_executor", "general_executor", "reporter"]
    
    if next_executor in valid_executors:
        return next_executor
    else:
        logger.warning(f"Router: 无效的执行者 {next_executor}，默认结束")
        return "__end__"


def executor_router(state: AgentState) -> Literal["supervisor", "__end__"]:
    """
    Executor 路由：执行完成后返回 supervisor
    
    目前执行者总是返回 supervisor (通过 Command)
    此函数作为备用路由
    """
    return "supervisor"


# ============================================================
# 混合模式路由
# ============================================================

def mode_selector(state: AgentState) -> Literal["react", "planner"]:
    """
    模式选择器：根据配置选择工作模式
    
    - react: 使用 ReAct 模式 (简单任务)
    - planner: 使用 Planner-Supervisor 模式 (复杂任务)
    """
    enable_planning = state.get("enable_planning", False)
    
    if enable_planning:
        return "planner"
    else:
        return "react"


def task_complexity_router(state: AgentState) -> Literal["simple", "complex"]:
    """
    任务复杂度路由：根据用户输入判断任务复杂度
    
    - simple: 单步任务，使用 ReAct
    - complex: 多步任务，使用 Planner-Supervisor
    
    判断依据:
    - 包含多个动作词 (生成+转换, 编辑+视频等)
    - 包含 "然后"、"接着"、"之后" 等顺序词
    - 消息长度超过阈值
    """
    messages = state.get("messages", [])
    if not messages:
        return "simple"
    
    # 获取最后一条用户消息
    last_message = messages[-1]
    content = last_message.content if hasattr(last_message, "content") else ""
    
    # 复杂任务关键词
    sequence_keywords = ["然后", "接着", "之后", "再", "先", "最后", "第一步", "第二步"]
    multi_action_keywords = ["并且", "同时", "以及", "和"]
    
    # 动作词
    action_keywords = ["生成", "创建", "制作", "编辑", "修改", "转换", "变成", "做成"]
    
    # 检查是否有顺序词
    has_sequence = any(kw in content for kw in sequence_keywords)
    
    # 检查动作词数量
    action_count = sum(1 for kw in action_keywords if kw in content)
    
    # 检查是否有多动作词
    has_multi_action = any(kw in content for kw in multi_action_keywords)
    
    # 判断复杂度
    if has_sequence or action_count >= 2 or has_multi_action:
        logger.info(f"Router: 检测到复杂任务 (sequence={has_sequence}, actions={action_count})")
        return "complex"
    else:
        logger.info("Router: 检测到简单任务")
        return "simple"


# ============================================================
# 工具函数
# ============================================================

def get_last_message_content(state: AgentState) -> str:
    """获取最后一条消息的内容"""
    messages = state.get("messages", [])
    if not messages:
        return ""
    
    last_message = messages[-1]
    return last_message.content if hasattr(last_message, "content") else ""


def is_planning_enabled(state: AgentState) -> bool:
    """检查是否启用规划模式"""
    return state.get("enable_planning", False)


def has_valid_plan(state: AgentState) -> bool:
    """检查是否有有效的执行计划"""
    full_plan = state.get("full_plan")
    if not full_plan:
        return False
    
    try:
        import json
        plan = json.loads(full_plan)
        steps = plan.get("steps", [])
        return len(steps) > 0
    except:
        return False


def is_all_steps_completed(state: AgentState) -> bool:
    """检查是否所有步骤都已完成"""
    current_index = state.get("current_step_index", 0)
    total_steps = state.get("total_steps", 0)
    
    return current_index >= total_steps and total_steps > 0


def is_reporter_done(state: AgentState) -> bool:
    """检查 Reporter 是否已执行"""
    step_results = state.get("step_results", [])
    return any(r.get("executor") == "reporter" for r in step_results)
