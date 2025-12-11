from typing import Annotated, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

class AgentState(TypedDict):
    """
    Unified state for all agent variants.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # 核心状态追踪
    last_task_id: str | None  # 记录最近一个任务的ID
    last_tool_name: str | None # 记录最近一个任务使用的工具名称
    last_task_config: dict | None  # 记录最近一个任务的配置
    global_config: dict | None  # 记录全局配置
    
    references: list[dict] | None  # 记录参考素材
    model_call_count: int  # 记录单轮交互中 model_call 的执行次数
    
    # 扩展字段 (仅在 suggestion 模式下有值，平时为空列表或None)
    suggestions: list[str] | None 

class SuggestionResponse(BaseModel):
    suggestions: list[str] = Field(description="3 follow-up suggestions for the user")

class LegacyAgentResponse(BaseModel):
    """
        早期的 Agent 响应格式，包含 answer 和 suggestions
        现在不使用这个格式，但是为了兼容旧的 MyNameTemplate.py，保留这个模型
    """
    answer: str = Field(description="The answer to the user's question")
    suggestions: list[str] = Field(description="The suggestions for the user to choose from")
