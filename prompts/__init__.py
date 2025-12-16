"""
Prompts 模块
提供提示词模板加载和管理功能
"""

from .templates import (
    # 模板加载函数
    get_prompt_template,
    apply_prompt_template,
    
    # 格式化辅助函数
    format_step_results,
    
    # 便捷提示词获取函数
    get_planner_prompt,
    get_supervisor_prompt,
    get_coordinator_prompt,
    get_reporter_prompt,
    get_executor_prompt,
    
    # 旧版提示词常量 (保持兼容)
    Your_Name_SYSTEM_PROMPT,
    Custom_SYSTEM_PROMPT,
    SUGGESTION_SYSTEM_PROMPT,
)

__all__ = [
    # 模板加载
    "get_prompt_template",
    "apply_prompt_template",
    
    # 格式化工具
    "format_step_results",
    
    # 提示词获取
    "get_planner_prompt",
    "get_supervisor_prompt",
    "get_coordinator_prompt",
    "get_reporter_prompt",
    "get_executor_prompt",
    
    # 兼容旧版
    "Your_Name_SYSTEM_PROMPT",
    "Custom_SYSTEM_PROMPT",
    "SUGGESTION_SYSTEM_PROMPT",
]

