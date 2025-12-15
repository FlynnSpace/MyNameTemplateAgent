"""
Nodes 模块
提供所有 LangGraph 工作流节点

包含:
- ReAct 模式节点 (core, common)
- Planner-Supervisor 模式节点 (coordinator, planner, supervisor, executors, reporter)
- 路由器 (routers)
"""

# ReAct 模式节点
from .core import create_model_node
from .common import (
    initial_prep_node,
    recorder_node,
    prepare_state_from_payload,
)
from .suggestion import create_suggestion_node

# Planner-Supervisor 模式节点
from .coordinator import create_coordinator_node
from .planner import (
    create_planner_node,
    parse_plan_steps,
    get_current_step,
    get_step_by_index,
)
from .supervisor import create_supervisor_node
from .executors import (
    create_image_executor_node,
    create_video_executor_node,
    create_general_executor_node,
)
from .reporter import create_reporter_node

# 路由器
from .routers import (
    # ReAct 路由
    should_continue,
    # Planner-Supervisor 路由
    coordinator_router,
    planner_router,
    supervisor_router,
    executor_router,
    # 混合模式路由
    mode_selector,
    task_complexity_router,
    # 工具函数
    get_last_message_content,
    is_planning_enabled,
    has_valid_plan,
    is_all_steps_completed,
    is_reporter_done,
)


__all__ = [
    # ReAct 模式
    "create_model_node",
    "initial_prep_node",
    "recorder_node",
    "prepare_state_from_payload",
    "create_suggestion_node",
    
    # Planner-Supervisor 模式 (对标 LangManus)
    "create_coordinator_node",
    "create_planner_node",
    "parse_plan_steps",
    "get_current_step",
    "get_step_by_index",
    "create_supervisor_node",
    "create_image_executor_node",
    "create_video_executor_node",
    "create_general_executor_node",
    "create_reporter_node",
    
    # 路由器
    "should_continue",
    "coordinator_router",
    "planner_router",
    "supervisor_router",
    "executor_router",
    "mode_selector",
    "task_complexity_router",
    "get_last_message_content",
    "is_planning_enabled",
    "has_valid_plan",
    "is_all_steps_completed",
    "is_reporter_done",
]

