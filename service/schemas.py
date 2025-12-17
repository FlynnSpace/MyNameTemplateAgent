"""
Service 层数据模型
定义 API 请求和响应的数据结构
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ============================================================
# 通用响应模型
# ============================================================

class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = Field(description="请求是否成功")
    message: str = Field(default="", description="响应消息")
    

class ErrorResponse(BaseResponse):
    """错误响应模型"""
    success: bool = False
    error_code: str = Field(description="错误码")
    detail: str = Field(default="", description="错误详情")


# ============================================================
# 对话请求模型
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
# 任务相关模型
# ============================================================

class TaskStatusRequest(BaseModel):
    """任务状态查询请求"""
    task_id: str = Field(description="任务ID")
    task_type: Literal["image", "video"] = Field(default="image", description="任务类型")


class TaskStatusResponse(BaseResponse):
    """任务状态响应"""
    task_id: str = Field(description="任务ID")
    status: Literal["pending", "processing", "completed", "failed", "unknown"] = Field(description="任务状态")
    progress: Optional[int] = Field(default=None, description="进度百分比 (0-100)")
    result_url: Optional[str] = Field(default=None, description="结果URL")
    error_message: Optional[str] = Field(default=None, description="错误信息")


# ============================================================
# 配置相关模型
# ============================================================

class GlobalConfigRequest(BaseModel):
    """全局配置更新请求"""
    style: Optional[str] = Field(default=None, description="默认风格")
    resolution: Optional[str] = Field(default=None, description="默认分辨率")
    aspect_ratio: Optional[str] = Field(default=None, description="默认宽高比")


class GlobalConfigResponse(BaseResponse):
    """全局配置响应"""
    config: dict = Field(description="当前全局配置")


# ============================================================
# 历史记录相关模型
# ============================================================

class ChatMessage(BaseModel):
    """单条消息"""
    role: Literal["user", "assistant", "system"] = Field(description="消息角色")
    content: str = Field(description="消息内容")


class ConversationHistory(BaseModel):
    """对话历史"""
    thread_id: str = Field(description="Thread ID")
    messages: list[ChatMessage] = Field(description="消息列表")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="最后更新时间")


class HistoryListResponse(BaseResponse):
    """历史列表响应"""
    conversations: list[ConversationHistory] = Field(description="对话历史列表")
    total: int = Field(description="总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


# ============================================================
# Thread 相关模型
# ============================================================

class ThreadResponse(BaseResponse):
    """Thread 响应"""
    thread_id: str = Field(description="Thread ID")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    metadata: dict = Field(default={}, description="元数据")


class ThreadHistoryResponse(BaseResponse):
    """Thread 历史消息响应"""
    thread_id: str = Field(description="Thread ID")
    messages: list[dict] = Field(default=[], description="历史消息列表")


# ============================================================
# 健康检查
# ============================================================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: Literal["healthy", "degraded", "unhealthy"] = Field(description="服务状态")
    version: str = Field(description="API 版本")
    agents: dict[str, bool] = Field(description="各 Agent 可用状态")
