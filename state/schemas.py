from typing import Annotated, Literal, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ============================================================
# 执行者类型定义 (用于 Supervisor 路由) - 对标 LangManus
# ============================================================
TEAM_MEMBERS = ["image_executor", "video_executor", "general_executor", "reporter"]
OPTIONS = TEAM_MEMBERS + ["FINISH"]

# 保持兼容性
EXECUTOR_TYPES = TEAM_MEMBERS
ExecutorType = Literal["image_executor", "video_executor", "general_executor", "reporter", "FINISH"]


class AgentState(TypedDict):
    """
    Unified state for all agent variants.
    支持 ReAct 模式和 Planner-Supervisor 模式
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # ============================================================
    # 核心状态追踪 (ReAct 模式)
    # ============================================================
    last_task_id: str | None  # 记录最近一个任务的ID
    last_tool_name: str | None # 记录最近一个任务使用的工具名称
    last_task_config: dict | None  # 记录最近一个任务的配置
    global_config: dict | None  # 记录全局配置
    
    references: list[dict] | None  # 记录参考素材
    model_call_count: int  # 记录单轮交互中 model_call 的执行次数
    
    # 扩展字段 (仅在 suggestion 模式下有值，平时为空列表或None)
    suggestions: list[str] | None
    
    # ============================================================
    # Planner-Supervisor 模式扩展字段
    # ============================================================
    
    # --- 规划相关 ---
    full_plan: str | None           # 完整执行计划 (JSON 字符串)
    current_step_index: int         # 当前执行步骤索引 (从 0 开始)
    total_steps: int                # 总步骤数
    
    # --- 执行控制 ---
    next_executor: str | None       # 下一个执行者 (由 Supervisor 决定)
    step_results: list[dict] | None # 每步执行结果列表
    
    # --- 上下文信息 ---
    plan_thought: str | None        # Planner 对任务的理解
    plan_title: str | None          # 任务标题
    
    # --- 模式控制 ---
    deep_thinking_mode: bool        # 是否启用深度思考模式 (Planner 使用 reasoning LLM)
    enable_planning: bool           # 是否启用规划模式 (False 时退化为 ReAct) 

class SuggestionResponse(BaseModel):
    suggestions: list[str] = Field(description="3 follow-up suggestions for the user")


class LegacyAgentResponse(BaseModel):
    """
        早期的 Agent 响应格式，包含 answer 和 suggestions
        现在不使用这个格式，但是为了兼容旧的 MyNameTemplate.py，保留这个模型
    """
    answer: str = Field(description="The answer to the user's question")
    suggestions: list[str] = Field(description="The suggestions for the user to choose from")


# ============================================================
# Planner-Supervisor 模式相关数据结构
# ============================================================

class PlanStep(BaseModel):
    """单个执行步骤"""
    executor: str = Field(description="执行者名称: image_executor, video_executor, general_executor")
    title: str = Field(description="步骤标题")
    description: str = Field(description="详细描述，包含具体参数和要求")
    depends_on: list[int] = Field(default=[], description="依赖的步骤索引列表")
    note: str | None = Field(default=None, description="备注信息")


class ExecutionPlan(BaseModel):
    """完整执行计划"""
    thought: str = Field(description="对用户需求的理解和分析")
    title: str = Field(description="任务标题")
    steps: list[PlanStep] = Field(description="执行步骤列表")


class SupervisorDecision(TypedDict):
    """
    Supervisor 的路由决策 (对标 LangManus Router)
    Worker to route to next. If no workers needed, route to FINISH.
    """
    next: Literal["image_executor", "video_executor", "general_executor", "reporter", "FINISH"]


class StepResult(BaseModel):
    """单步执行结果"""
    step_index: int = Field(description="步骤索引")
    executor: str = Field(description="执行者名称")
    status: Literal["success", "failed", "pending"] = Field(description="执行状态")
    task_id: str | None = Field(default=None, description="任务ID (如果有)")
    result_url: str | None = Field(default=None, description="结果URL (如果有)")
    summary: str = Field(description="执行摘要")
