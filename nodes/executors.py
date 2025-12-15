"""
Executors 节点
执行者：根据任务类型执行具体的生成任务

包含:
- ImageExecutor: 图像生成/编辑
- VideoExecutor: 视频生成
- GeneralExecutor: 通用任务 (状态查询等)

支持动态工具配置:
- 从 state.EXECUTOR_TOOLS 获取每个执行者可用的工具列表
- 前端可通过传入 EXECUTOR_TOOLS 控制工具的启用/禁用
"""

import json
import random
from typing import Literal, Callable, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Command
from langgraph.prebuilt import ToolNode

from state.schemas import AgentState, DEFAULT_EXECUTOR_TOOLS
from prompts.templates import get_executor_prompt
from utils.logger import get_logger

logger = get_logger("loopskill.nodes.executors")


# ============================================================
# 工具过滤辅助函数
# ============================================================

def _get_available_tools(
    all_tools: List[BaseTool],
    executor_name: str,
    state: AgentState
) -> List[BaseTool]:
    """
    根据 state 中的 EXECUTOR_TOOLS 配置过滤可用工具
    
    Args:
        all_tools: 所有可用工具列表
        executor_name: 执行者名称 (image_executor, video_executor, general_executor)
        state: 当前状态 (包含 EXECUTOR_TOOLS 配置)
        
    Returns:
        过滤后的工具列表
        
    工作流程:
    1. 从 state.EXECUTOR_TOOLS 获取该执行者允许使用的工具名称列表
    2. 如果没有配置，使用默认配置 DEFAULT_EXECUTOR_TOOLS
    3. 根据工具名称过滤 all_tools
    """
    # 获取工具配置
    executor_tools_config = state.get("EXECUTOR_TOOLS", DEFAULT_EXECUTOR_TOOLS)
    allowed_tool_names = executor_tools_config.get(executor_name, [])
    
    if not allowed_tool_names:
        logger.warning(f"{executor_name} 没有配置可用工具，将使用空工具列表")
        return []
    
    # 建立工具名称映射 (支持模糊匹配)
    filtered_tools = []
    for tool in all_tools:
        tool_name_lower = tool.name.lower()
        for allowed_name in allowed_tool_names:
            # 精确匹配或部分匹配
            if allowed_name.lower() in tool_name_lower or tool_name_lower in allowed_name.lower():
                filtered_tools.append(tool)
                break
    
    logger.info(f"{executor_name} 可用工具: {[t.name for t in filtered_tools]} (配置: {allowed_tool_names})")
    
    return filtered_tools


# ============================================================
# 图像执行者
# ============================================================

def create_image_executor_node(
    llm: BaseChatModel,
    tools: List[BaseTool]
):
    """
    创建 ImageExecutor 节点 (支持动态工具配置)
    
    Args:
        llm: 语言模型
        tools: 所有可用工具列表 (会根据 state.EXECUTOR_TOOLS 过滤)
        
    Returns:
        image_executor 节点函数
        
    动态工具配置:
    - 在运行时从 state.EXECUTOR_TOOLS["image_executor"] 获取允许使用的工具名称
    - 根据名称从 tools 中过滤出实际可用的工具
    - 前端可通过修改 EXECUTOR_TOOLS 来启用/禁用特定工具
    """
    
    def image_executor_node(state: AgentState) -> Command[Literal["supervisor"]]:
        """
        图像执行者节点：执行图像生成/编辑任务
        """
        logger.info("ImageExecutor 开始执行")
        
        # 动态获取可用工具 (从 state.EXECUTOR_TOOLS 配置)
        image_tools = _get_available_tools(tools, "image_executor", state)
        
        if not image_tools:
            logger.warning("ImageExecutor 没有可用工具，使用备用方案")
            # 备用：根据关键词过滤
            image_tools = [t for t in tools if any(kw in t.name.lower() for kw in ["image", "seedream", "banana", "watermark"])]
        
        # 动态绑定工具到 LLM
        llm_with_tools = llm.bind_tools(image_tools) if image_tools else llm
        
        # 获取当前步骤信息
        current_step = _get_current_step(state)
        if not current_step:
            logger.error("无法获取当前步骤")
            return _create_error_result(state, "image_executor", "无法获取当前步骤")
        
        logger.info(f"执行步骤: {current_step.get('title', 'Unknown')}")
        
        # 构建执行提示词
        system_prompt = get_executor_prompt("image_executor")
        
        # 构建任务消息
        task_description = current_step.get("description", "")
        
        # 注入上下文信息 (上一步结果等)
        context = _build_execution_context(state)
        
        task_message = f"""
请执行以下图像任务:

{task_description}

{context}
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=task_message)
        ]
        
        # 调用 LLM (带工具)
        try:
            response = llm_with_tools.invoke(messages)
            
            # 检查是否有工具调用
            if hasattr(response, "tool_calls") and response.tool_calls:
                # 执行工具
                tool_result = _execute_tools(response, image_tools)
                
                # 记录结果
                return _create_success_result(
                    state, 
                    "image_executor",
                    tool_result.get("task_id"),
                    tool_result.get("summary", "图像任务已提交")
                )
            else:
                # 没有工具调用
                content = response.content if hasattr(response, "content") else str(response)
                logger.warning(f"ImageExecutor 没有调用工具: {content[:200]}")
                return _create_error_result(state, "image_executor", "没有执行工具调用")
                
        except Exception as e:
            logger.error(f"ImageExecutor 执行失败: {e}")
            return _create_error_result(state, "image_executor", str(e))
    
    return image_executor_node


# ============================================================
# 视频执行者
# ============================================================

def create_video_executor_node(
    llm: BaseChatModel,
    tools: List[BaseTool]
):
    """
    创建 VideoExecutor 节点 (支持动态工具配置)
    
    Args:
        llm: 语言模型
        tools: 所有可用工具列表 (会根据 state.EXECUTOR_TOOLS 过滤)
        
    Returns:
        video_executor 节点函数
    """
    
    def video_executor_node(state: AgentState) -> Command[Literal["supervisor"]]:
        """
        视频执行者节点：执行视频生成任务
        """
        logger.info("VideoExecutor 开始执行")
        
        # 动态获取可用工具 (从 state.EXECUTOR_TOOLS 配置)
        video_tools = _get_available_tools(tools, "video_executor", state)
        
        if not video_tools:
            logger.warning("VideoExecutor 没有可用工具，使用备用方案")
            video_tools = [t for t in tools if any(kw in t.name.lower() for kw in ["video", "sora"])]
        
        # 动态绑定工具到 LLM
        llm_with_tools = llm.bind_tools(video_tools) if video_tools else llm
        
        # 获取当前步骤信息
        current_step = _get_current_step(state)
        if not current_step:
            logger.error("无法获取当前步骤")
            return _create_error_result(state, "video_executor", "无法获取当前步骤")
        
        logger.info(f"执行步骤: {current_step.get('title', 'Unknown')}")
        
        # 构建执行提示词
        system_prompt = get_executor_prompt("video_executor")
        
        # 构建任务消息
        task_description = current_step.get("description", "")
        
        # 注入上下文信息 (上一步结果等)
        context = _build_execution_context(state)
        
        task_message = f"""
请执行以下视频任务:

{task_description}

{context}
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=task_message)
        ]
        
        # 调用 LLM (带工具)
        try:
            response = llm_with_tools.invoke(messages)
            
            # 检查是否有工具调用
            if hasattr(response, "tool_calls") and response.tool_calls:
                # 执行工具
                tool_result = _execute_tools(response, video_tools)
                
                # 记录结果
                return _create_success_result(
                    state,
                    "video_executor",
                    tool_result.get("task_id"),
                    tool_result.get("summary", "视频任务已提交")
                )
            else:
                # 没有工具调用
                content = response.content if hasattr(response, "content") else str(response)
                logger.warning(f"VideoExecutor 没有调用工具: {content[:200]}")
                return _create_error_result(state, "video_executor", "没有执行工具调用")
                
        except Exception as e:
            logger.error(f"VideoExecutor 执行失败: {e}")
            return _create_error_result(state, "video_executor", str(e))
    
    return video_executor_node


# ============================================================
# 通用执行者
# ============================================================

def create_general_executor_node(
    llm: BaseChatModel,
    tools: List[BaseTool]
):
    """
    创建 GeneralExecutor 节点 (支持动态工具配置)
    
    Args:
        llm: 语言模型
        tools: 所有可用工具列表 (会根据 state.EXECUTOR_TOOLS 过滤)
        
    Returns:
        general_executor 节点函数
    """
    
    def general_executor_node(state: AgentState) -> Command[Literal["supervisor"]]:
        """
        通用执行者节点：执行状态查询等任务
        """
        logger.info("GeneralExecutor 开始执行")
        
        # 动态获取可用工具 (从 state.EXECUTOR_TOOLS 配置)
        general_tools = _get_available_tools(tools, "general_executor", state)
        
        if not general_tools:
            logger.warning("GeneralExecutor 没有可用工具，使用备用方案")
            general_tools = [t for t in tools if "status" in t.name.lower() or "config" in t.name.lower()]
        
        # 动态绑定工具到 LLM
        llm_with_tools = llm.bind_tools(general_tools) if general_tools else llm
        
        # 获取当前步骤信息
        current_step = _get_current_step(state)
        if not current_step:
            logger.error("无法获取当前步骤")
            return _create_error_result(state, "general_executor", "无法获取当前步骤")
        
        logger.info(f"执行步骤: {current_step.get('title', 'Unknown')}")
        
        # 构建执行提示词
        system_prompt = get_executor_prompt("general_executor")
        
        # 构建任务消息
        task_description = current_step.get("description", "")
        
        task_message = f"""
请执行以下任务:

{task_description}
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=task_message)
        ]
        
        # 调用 LLM
        try:
            response = llm_with_tools.invoke(messages)
            
            # 检查是否有工具调用
            if hasattr(response, "tool_calls") and response.tool_calls:
                tool_result = _execute_tools(response, general_tools)
                return _create_success_result(
                    state,
                    "general_executor",
                    None,
                    tool_result.get("summary", "任务已完成")
                )
            else:
                content = response.content if hasattr(response, "content") else str(response)
                return _create_success_result(
                    state,
                    "general_executor",
                    None,
                    content[:200]
                )
                
        except Exception as e:
            logger.error(f"GeneralExecutor 执行失败: {e}")
            return _create_error_result(state, "general_executor", str(e))
    
    return general_executor_node


# ============================================================
# 辅助函数
# ============================================================

def _get_current_step(state: AgentState) -> dict | None:
    """获取当前待执行的步骤"""
    full_plan = state.get("full_plan")
    current_index = state.get("current_step_index", 0)
    
    if not full_plan:
        return None
    
    try:
        plan = json.loads(full_plan)
        steps = plan.get("steps", [])
        
        if 0 <= current_index < len(steps):
            return steps[current_index]
    except (json.JSONDecodeError, TypeError):
        pass
    
    return None


def _build_execution_context(state: AgentState) -> str:
    """构建执行上下文 (包含上一步结果等)"""
    context_parts = []
    
    # 添加上一步结果
    step_results = state.get("step_results", [])
    if step_results:
        context_parts.append("## 上一步执行结果")
        for result in step_results[-3:]:  # 只取最近3个
            status = result.get("status", "unknown")
            task_id = result.get("task_id", "N/A")
            result_url = result.get("result_url", "")
            
            context_parts.append(f"- [{result.get('executor', '?')}] 状态: {status}")
            if task_id != "N/A":
                context_parts.append(f"  Task ID: {task_id}")
            if result_url:
                context_parts.append(f"  结果 URL: {result_url}")
    
    # 添加参考素材
    references = state.get("references", [])
    if references:
        context_parts.append("\n## 可用参考素材")
        for i, ref in enumerate(references):
            context_parts.append(f"- [{i+1}] {ref.get('desc', 'Image')}: {ref.get('url', 'N/A')}")
    
    # 添加全局配置
    global_config = state.get("global_config")
    if global_config:
        context_parts.append(f"\n## 全局配置\n{json.dumps(global_config, ensure_ascii=False)}")
    
    return "\n".join(context_parts) if context_parts else ""


def _execute_tools(response, tools: List[BaseTool]) -> dict:
    """
    执行 LLM 响应中的工具调用
    
    Args:
        response: LLM 响应 (包含 tool_calls)
        tools: 可用工具列表
        
    Returns:
        执行结果字典
    """
    if not hasattr(response, "tool_calls") or not response.tool_calls:
        return {"summary": "没有工具调用"}
    
    # 建立工具名称到工具的映射
    tool_map = {t.name: t for t in tools}
    
    results = []
    task_id = None
    
    for tool_call in response.tool_calls:
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        
        logger.info(f"执行工具: {tool_name}, 参数: {tool_args}")
        
        if tool_name in tool_map:
            try:
                tool = tool_map[tool_name]
                result = tool.invoke(tool_args)
                
                logger.info(f"工具结果: {result}")
                
                # 尝试提取 task_id
                if isinstance(result, dict):
                    task_id = result.get("task_id") or result.get("id")
                elif isinstance(result, str):
                    # 尝试解析 JSON
                    try:
                        parsed = json.loads(result)
                        task_id = parsed.get("task_id") or parsed.get("id")
                    except:
                        # 可能直接是 task_id 字符串
                        if result and not result.startswith("{"):
                            task_id = result
                
                results.append({
                    "tool": tool_name,
                    "result": result,
                    "task_id": task_id
                })
                
            except Exception as e:
                logger.error(f"工具执行失败 {tool_name}: {e}")
                results.append({
                    "tool": tool_name,
                    "error": str(e)
                })
        else:
            logger.warning(f"未找到工具: {tool_name}")
    
    return {
        "task_id": task_id,
        "summary": f"执行了 {len(results)} 个工具调用",
        "details": results
    }


def _create_success_result(
    state: AgentState,
    executor: str,
    task_id: str | None,
    summary: str
) -> Command[Literal["supervisor"]]:
    """创建成功结果并返回到 supervisor"""
    current_index = state.get("current_step_index", 0)
    step_results = state.get("step_results", []).copy()
    
    # 添加执行结果
    step_results.append({
        "step_index": current_index,
        "executor": executor,
        "status": "success",
        "task_id": task_id,
        "result_url": None,  # 异步任务需要后续查询
        "summary": summary
    })
    
    logger.info(f"步骤 {current_index} 执行成功: {summary}")
    
    return Command(
        goto="supervisor",
        update={
            "messages": [AIMessage(
                content=f"[{executor}] 执行完成: {summary}" + (f" (Task ID: {task_id})" if task_id else ""),
                name=executor
            )],
            "current_step_index": current_index + 1,  # 推进到下一步
            "step_results": step_results,
            "last_task_id": task_id,
            "last_tool_name": executor,
        }
    )


def _create_error_result(
    state: AgentState,
    executor: str,
    error_message: str
) -> Command[Literal["supervisor"]]:
    """创建错误结果并返回到 supervisor"""
    current_index = state.get("current_step_index", 0)
    step_results = state.get("step_results", []).copy()
    
    # 添加失败结果
    step_results.append({
        "step_index": current_index,
        "executor": executor,
        "status": "failed",
        "task_id": None,
        "result_url": None,
        "summary": f"执行失败: {error_message}"
    })
    
    logger.error(f"步骤 {current_index} 执行失败: {error_message}")
    
    return Command(
        goto="supervisor",
        update={
            "messages": [AIMessage(
                content=f"[{executor}] 执行失败: {error_message}",
                name=executor
            )],
            "current_step_index": current_index + 1,  # 仍然推进 (让 supervisor 决定是否重试)
            "step_results": step_results,
        }
    )

