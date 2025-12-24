"""
Service 层数据模型
定义 API 请求和响应的数据结构

只保留 chat_stream_simple 接口相关模型
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ============================================================
# 流式对话请求模型 (核心)
# ============================================================

class StreamChatRequest(BaseModel):
    """流式对话请求"""
    message: str = Field(description="用户消息内容")
    thread_id: Optional[str] = Field(default=None, description="Thread ID，用于追踪上下文")
    agent_type: Literal["react", "planner_supervisor"] = Field(
        default="planner_supervisor", 
        description="Agent 类型"
    )
    deep_thinking: bool = Field(default=False, description="是否启用深度思考模式")


# ============================================================
# SSE 返回格式说明 (对标 planning_agent)
# ============================================================
#
# 所有事件的 event 字段统一为 "message"，通过 data 内部字段区分类型:
#
# 1. 开始:       {"type": "start", "thread_id": "..."}
# 2. 思考过程:   {"thought": "T"} {"thought": "h"} ...  (Planner, 逐字流式)
# 3. 工具结果:   {"tool_name": "text_to_image", "tool_result": "{...}"}  (Executor, 一次性完整JSON)
# 4. 文本回复:   {"delta": "太"} {"delta": "棒"} ...  (Coordinator/Reporter, 逐字流式)
# 5. 结束:       {"type": "end", "thread_id": "..."}
# 6. 错误:       {"type": "error", "error": "..."}
#
# 两种对话流程:
# - 简单问题: start → delta (逐字) → end
# - 复杂任务: start → thought (逐字) → tool_name+tool_result → delta (逐字) → end
#
# 前端处理:
# - delta → 逐字累加拼接显示 (打字机效果)
# - thought → 逐字累加显示在思考区域
# - tool_name + tool_result → 渲染工具卡片
#
# 环境变量:
# - STREAM_DELAY: 逐字输出延迟，默认 0.02 秒，设为 0 则无延迟
