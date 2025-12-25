"""
Planner 节点
规划者：分析用户需求，生成结构化执行计划

职责：
- 分析用户需求，生成高层执行计划
- 只关注 executor 层面的规划
- 具体的 tool 可用性由 Executor 层负责校验

流式输出：
- 使用 get_stream_writer() 发送 {"thought": "..."} 格式数据
"""

import json
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel
from langgraph.types import Command
from langgraph.config import get_stream_writer

from state.schemas import AgentState, ExecutionPlan, TEAM_MEMBERS as DEFAULT_TEAM_MEMBERS
from prompts.templates import apply_prompt_template
from utils.logger import get_logger

logger = get_logger("loopskill.nodes.planner")


def _validate_executor(executor: str, available_executors: list[str]) -> str | None:
    """
    验证执行者是否可用，支持模糊匹配
    
    Args:
        executor: 计划中指定的执行者
        available_executors: 可用的执行者列表
        
    Returns:
        匹配到的执行者名称，如果无法匹配则返回 None
    """
    # 精确匹配
    if executor in available_executors:
        return executor
    
    # 模糊匹配
    for avail in available_executors:
        if executor.lower() in avail.lower() or avail.lower() in executor.lower():
            logger.info(f"执行者 '{executor}' 模糊匹配到 '{avail}'")
            return avail
    
    return None


def create_planner_node(
    llm: BaseChatModel,
    reasoning_llm: BaseChatModel | None = None
):
    """
    创建 Planner 节点
    
    Args:
        llm: 基础语言模型
        reasoning_llm: 推理增强模型 (用于深度思考模式)
        
    Returns:
        planner 节点函数
        
    职责:
    - 分析用户需求，生成高层执行计划
    - 只负责 executor 层面的规划
    - 具体的 tool 可用性由 Executor 层负责校验
    """
    
    def planner_node(state: AgentState) -> Command[Literal["supervisor", "__end__"]]:
        """
        规划者节点：分析用户需求，生成执行计划
        
        输入: 用户消息
        输出: JSON 格式的执行计划
        
        流式输出：解析 JSON 后，发送 thought + steps 内容
        """
        logger.info("Planner 开始生成执行计划")
        
        # 获取流式写入器
        writer = get_stream_writer()
        
        # 获取提示词
        messages = apply_prompt_template("planner", state)
        
        # 选择 LLM (根据深度思考模式)
        use_llm = llm
        if state.get("deep_thinking_mode") and reasoning_llm:
            logger.info("启用深度思考模式，使用 reasoning LLM")
            use_llm = reasoning_llm
        
        # 调用 LLM 生成计划（不流式，因为需要完整 JSON）
        response = use_llm.invoke(messages)
        response_content = response.content if hasattr(response, "content") else str(response)
        
        logger.debug(f"Planner 原始响应: {response_content}...")
        
        # 清理 JSON 格式
        plan_json = _clean_json_response(response_content)
        
        # 解析计划
        try:
            plan_dict = json.loads(plan_json)
            
            # 提取计划信息
            thought = plan_dict.get("thought", "")
            title = plan_dict.get("title", "创作任务")
            steps = plan_dict.get("steps", [])
            
            # 流式发送思考过程和步骤
            # 1. 发送 thought
            if thought:
                thought_text = f"Thought: {thought}\n\n"
                for char in thought_text:
                    writer({"thought": char})
            
            # 2. 发送步骤列表
            for i, step in enumerate(steps, 1):
                step_title = step.get("title", f"步骤 {i}")
                step_text = f"{i}. {step_title}\n"
                for char in step_text:
                    writer({"thought": char})
            
            logger.info(f"Planner 生成计划: {title}, 共 {len(steps)} 步")
            
            # 获取可用的执行者列表
            available_executors = state.get("TEAM_MEMBERS", DEFAULT_TEAM_MEMBERS)
            
            # 简单校验：修正执行者名称（模糊匹配）
            validated_steps = []
            for i, step in enumerate(steps):
                raw_executor = step.get("executor", "general_executor")
                validated_executor = _validate_executor(raw_executor, available_executors)
                
                # 如果无法匹配到有效执行者，使用 general_executor
                if validated_executor is None:
                    logger.warning(f"步骤 {i}: 未知执行者 '{raw_executor}'，使用 general_executor")
                    validated_executor = "general_executor"
                
                validated_steps.append({
                    "executor": validated_executor,
                    "title": step.get("title", f"步骤 {i+1}"),
                    "description": step.get("description", ""),
                    "depends_on": step.get("depends_on", []),
                    "note": step.get("note")
                })
            
            # 更新计划
            plan_dict["steps"] = validated_steps
            
            return Command(
                goto="supervisor",
                update={
                    "messages": [AIMessage(content=plan_json, name="planner")],
                    "full_plan": json.dumps(plan_dict, ensure_ascii=False),
                    "plan_thought": thought,
                    "plan_title": title,
                    "current_step_index": 0,
                    "total_steps": len(validated_steps),
                    "step_results": [],
                }
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Planner JSON 解析失败: {e}")
            logger.error(f"原始内容: {plan_json}")
            
            # 解析失败，直接结束
            return Command(
                goto="__end__",
                update={
                    "messages": [AIMessage(
                        content=f"抱歉，我在理解你的需求时遇到了问题。请尝试更具体地描述你想要的创作内容。",
                        name="planner"
                    )],
                }
            )
    
    return planner_node

def _clean_json_response(response: str) -> str:
    """
    清理 LLM 响应中的 JSON 内容
    - 移除 ```json 标记
    - 移除多余的空白
    """
    content = response.strip()
    
    # 移除 markdown 代码块标记
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    
    if content.endswith("```"):
        content = content[:-3]
    
    return content.strip()


def parse_plan_steps(full_plan: str) -> list[dict]:
    """
    从完整计划中解析步骤列表
    
    Args:
        full_plan: JSON 格式的完整计划
        
    Returns:
        步骤列表
    """
    try:
        plan = json.loads(full_plan)
        return plan.get("steps", [])
    except (json.JSONDecodeError, TypeError):
        return []


def get_current_step(state: AgentState) -> dict | None:
    """
    获取当前待执行的步骤
    
    Args:
        state: 当前状态
        
    Returns:
        当前步骤字典，如果没有则返回 None
    """
    full_plan = state.get("full_plan")
    current_index = state.get("current_step_index", 0)
    
    if not full_plan:
        return None
    
    steps = parse_plan_steps(full_plan)
    
    if 0 <= current_index < len(steps):
        return steps[current_index]
    
    return None


def get_step_by_index(state: AgentState, index: int) -> dict | None:
    """
    根据索引获取步骤
    
    Args:
        state: 当前状态
        index: 步骤索引
        
    Returns:
        步骤字典
    """
    full_plan = state.get("full_plan")
    if not full_plan:
        return None
    
    steps = parse_plan_steps(full_plan)
    
    if 0 <= index < len(steps):
        return steps[index]
    
    return None


