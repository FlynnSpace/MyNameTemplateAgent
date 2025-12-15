"""
Planner 节点
规划者：分析用户需求，生成结构化执行计划

支持动态工具配置:
- 从 state.EXECUTOR_TOOLS 获取当前可用的工具列表
- Planner 会根据实际可用工具生成计划
- 如果请求的功能超出能力范围，会在 thought 中说明
"""

import json
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel
from langgraph.types import Command

from state.schemas import AgentState, ExecutionPlan, TEAM_MEMBERS as DEFAULT_TEAM_MEMBERS, DEFAULT_EXECUTOR_TOOLS
from prompts.templates import apply_prompt_template
from utils.logger import get_logger

logger = get_logger("loopskill.nodes.planner")


def _validate_plan_tools(
    steps: list[dict], 
    available_executors: list[str],
    executor_tools: dict[str, list[str]]
) -> tuple[bool, list[dict]]:
    """
    验证计划中所有步骤的工具是否都可用
    
    Args:
        steps: 计划中的步骤列表
        available_executors: 可用的执行者列表
        executor_tools: 每个执行者的工具配置
        
    Returns:
        (is_valid, missing_info): 
        - is_valid: 是否所有工具都可用
        - missing_info: 缺失的工具信息列表 [{"step": 0, "executor": "...", "reason": "..."}]
    """
    missing_info = []
    
    for i, step in enumerate(steps):
        executor = step.get("executor", "")
        
        # 检查执行者是否可用
        if executor not in available_executors:
            # 尝试模糊匹配
            matched = None
            for avail in available_executors:
                if executor.lower() in avail.lower() or avail.lower() in executor.lower():
                    matched = avail
                    break
            
            if matched:
                step["executor"] = matched  # 修正执行者名称
                logger.info(f"步骤 {i}: 执行者 '{executor}' 模糊匹配到 '{matched}'")
            else:
                missing_info.append({
                    "step_index": i,
                    "step_title": step.get("title", f"步骤 {i+1}"),
                    "executor": executor,
                    "reason": f"执行者 '{executor}' 不可用",
                    "available_executors": available_executors
                })
                continue
        
        # 检查执行者是否有可用工具 (reporter 除外)
        actual_executor = step.get("executor", executor)
        if actual_executor != "reporter":
            tools = executor_tools.get(actual_executor, [])
            if not tools:
                missing_info.append({
                    "step_index": i,
                    "step_title": step.get("title", f"步骤 {i+1}"),
                    "executor": actual_executor,
                    "reason": f"执行者 '{actual_executor}' 没有可用的工具",
                    "suggestion": "请在 EXECUTOR_TOOLS 中配置该执行者的工具"
                })
    
    is_valid = len(missing_info) == 0
    return is_valid, missing_info


def _build_missing_tools_context(
    missing_info: list[dict], 
    user_request: str,
    available_tools: list[str]
) -> str:
    """
    构建缺失工具的上下文信息（供 LLM 润色使用）
    
    Args:
        missing_info: 缺失信息列表
        user_request: 用户原始请求
        available_tools: 当前可用的工具列表
        
    Returns:
        结构化的上下文信息
    """
    missing_capabilities = []
    for info in missing_info:
        step_title = info.get("step_title", "未知步骤")
        executor = info.get("executor", "")
        
        # 将技术名称转换为能力描述
        capability_map = {
            "image_executor": "图片生成/编辑",
            "video_executor": "视频生成",
            "audio_executor": "音频生成",
            "general_executor": "通用任务处理",
        }
        capability = capability_map.get(executor, executor.replace("_executor", "").replace("_", " "))
        missing_capabilities.append(f"- {step_title}: 需要「{capability}」功能")
    
    return f"""用户请求: {user_request}

缺失的功能:
{chr(10).join(missing_capabilities)}

当前可用的工具: {', '.join(available_tools) if available_tools else '无'}"""


# ============================================================
# LLM 润色提示词 - 将技术错误转换为用户友好的消息
# ============================================================
TOOL_MISSING_PROMPT = """你是一个友好的助手。用户想要完成一个创作任务，但系统目前缺少必要的功能。

请根据以下信息，用简洁、友好的语言告诉用户：
1. 他们的需求目前无法完成
2. 具体缺少什么功能（用通俗易懂的话说，比如"图片生成"而不是"image_executor"）
3. 建议用户去「添加工具」来启用所需功能

要求：
- 不要使用任何技术术语（如 executor、TEAM_MEMBERS、EXECUTOR_TOOLS 等）
- 语气友好、简洁
- 不要道歉太多次
- 最后引导用户去添加需要的工具

{context}

请直接输出给用户的消息（不要有任何解释或前缀）："""


def create_planner_node(
    llm: BaseChatModel,
    reasoning_llm: BaseChatModel | None = None
):
    """
    创建 Planner 节点 (支持动态工具配置)
    
    Args:
        llm: 基础语言模型
        reasoning_llm: 推理增强模型 (用于深度思考模式)
        
    Returns:
        planner 节点函数
        
    动态工具配置:
    - Planner 会从 state.EXECUTOR_TOOLS 获取当前可用的工具
    - 生成的计划只会使用实际可用的工具
    - 如果请求超出能力范围，会在 thought 中说明并建议替代方案
    """
    
    def planner_node(state: AgentState) -> Command[Literal["supervisor", "__end__"]]:
        """
        规划者节点：分析用户需求，生成执行计划
        
        输入: 用户消息 + 动态工具配置
        输出: JSON 格式的执行计划
        """
        logger.info("Planner 开始生成执行计划")
        
        # 使用 apply_prompt_template 获取动态配置的提示词 (对标 LangManus)
        # 这会自动注入 TEAM_MEMBERS 和 EXECUTOR_CAPABILITIES
        messages = apply_prompt_template("planner", state)
        
        # 选择 LLM (根据深度思考模式)
        use_llm = llm
        if state.get("deep_thinking_mode") and reasoning_llm:
            logger.info("启用深度思考模式，使用 reasoning LLM")
            use_llm = reasoning_llm
        
        # 调用 LLM 生成计划
        response = use_llm.invoke(messages)
        response_content = response.content if hasattr(response, "content") else str(response)
        
        logger.debug(f"Planner 原始响应: {response_content[:500]}...")
        
        # 清理 JSON 格式
        plan_json = _clean_json_response(response_content)
        
        # 解析并验证计划
        try:
            plan_dict = json.loads(plan_json)
            
            # 提取计划信息
            thought = plan_dict.get("thought", "")
            title = plan_dict.get("title", "创作任务")
            steps = plan_dict.get("steps", [])
            
            logger.info(f"Planner 生成计划: {title}, 共 {len(steps)} 步")
            
            # 获取可用的执行者和工具配置
            available_executors = state.get("TEAM_MEMBERS", DEFAULT_TEAM_MEMBERS)
            executor_tools = state.get("EXECUTOR_TOOLS", DEFAULT_EXECUTOR_TOOLS)
            
            # ============================================================
            # 安全校验：验证计划中所有步骤的工具是否都可用
            # ============================================================
            validated_steps = []
            for i, step in enumerate(steps):
                validated_steps.append({
                    "executor": step.get("executor", "general_executor"),
                    "title": step.get("title", f"步骤 {i+1}"),
                    "description": step.get("description", ""),
                    "depends_on": step.get("depends_on", []),
                    "note": step.get("note")
                })
            
            # 执行安全校验
            is_valid, missing_info = _validate_plan_tools(
                validated_steps, 
                available_executors, 
                executor_tools
            )
            
            if not is_valid:
                # ============================================================
                # 工具缺失：使用 LLM 润色错误消息，然后到 __end__
                # ============================================================
                logger.warning(f"计划校验失败，缺少工具: {missing_info}")
                
                # 获取用户原始请求
                user_messages = [m for m in state.get("messages", []) if hasattr(m, "type") and m.type == "human"]
                user_request = user_messages[-1].content if user_messages else "用户请求"
                
                # 获取当前可用的工具列表
                all_available_tools = []
                for tools in executor_tools.values():
                    all_available_tools.extend(tools)
                
                # 构建上下文
                context = _build_missing_tools_context(missing_info, user_request, all_available_tools)
                
                # 使用 LLM 润色错误消息
                polish_prompt = TOOL_MISSING_PROMPT.format(context=context)
                polish_response = use_llm.invoke([HumanMessage(content=polish_prompt)])
                error_message = polish_response.content if hasattr(polish_response, "content") else str(polish_response)
                
                logger.info(f"LLM 润色后的错误消息: {error_message[:100]}...")
                
                return Command(
                    goto="__end__",
                    update={
                        "messages": [AIMessage(
                            content=error_message,
                            name="planner"
                        )],
                        "plan_thought": thought,
                        "plan_title": title,
                    }
                )
            
            # ============================================================
            # 校验通过：继续执行计划
            # ============================================================
            logger.info("计划校验通过，所有工具都可用")
            
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
                        content=f"抱歉，我在理解你的需求时遇到了问题。请尝试更具体地描述你想要的创作内容。\n\n原始响应: {response_content[:200]}...",
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


