"""
Graph Builder 模块
提供工作流图构建函数

包含:
- create_base_ReAct_graph: ReAct 模式工作流 (原有)
- create_planner_supervisor_graph: Planner-Supervisor 模式工作流 (新增)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from state.schemas import AgentState
import nodes.common as common
import nodes.core as core
import nodes.suggestion as suggestion
import nodes.routers as routers
from nodes.coordinator import create_coordinator_node
from nodes.planner import create_planner_node
from nodes.supervisor import create_supervisor_node
from nodes.executors import (
    create_image_executor_node,
    create_video_executor_node,
    create_status_checker_node,
)
from nodes.reporter import create_reporter_node


# ============================================================
# ReAct 模式图构建 (保持原有功能)
# ============================================================

def create_base_ReAct_graph(
    llm: BaseChatModel,
    system_prompt: str,
    tools: list[BaseTool],
    enable_suggestion: bool = False,
    suggestion_llm: BaseChatModel = None
) -> CompiledStateGraph:
    """
    ReAct 模式图构建工厂。
    
    Args:
        llm: 主 Agent 使用的 LLM。
        system_prompt: 系统提示词模板。
        tools: 可用工具列表。
        enable_suggestion: 是否启用建议生成节点。
        suggestion_llm: 建议生成专用的 LLM (仅当 enable_suggestion=True 时需要)。
        
    Returns:
        编译后的工作流图
    """
    workflow = StateGraph(AgentState)
    
    # 1. 绑定节点
    # 通用预处理
    workflow.add_node("initial_prep", common.initial_prep_node)
    
    # 核心模型节点 (使用 Factory 创建闭包)
    model_node = core.create_model_node(llm, system_prompt, tools)
    workflow.add_node("our_agent", model_node)
    
    # 工具节点
    workflow.add_node("tools", ToolNode(tools))
    
    # 记录器节点
    workflow.add_node("recorder", common.recorder_node)
    
    # 2. 基础连线
    workflow.set_entry_point("initial_prep")
    workflow.add_edge("initial_prep", "our_agent")
    
    # 工具循环：Tools -> Recorder -> Agent
    workflow.add_edge("tools", "recorder")
    workflow.add_edge("recorder", "our_agent")
    
    # 3. 动态处理结束流向
    if enable_suggestion:
        if not suggestion_llm:
            raise ValueError("suggestion_llm must be provided if enable_suggestion is True")
            
        sug_node = suggestion.create_suggestion_node(suggestion_llm)
        workflow.add_node("suggestion_generator", sug_node)
        
        # 路由：Agent 结束 -> 建议生成 -> END
        workflow.add_conditional_edges(
            "our_agent",
            routers.should_continue,
            {
                "continue": "tools",
                "end": "suggestion_generator" 
            }
        )
        workflow.add_edge("suggestion_generator", END)
        
    else:
        # 路由：Agent 结束 -> END
        workflow.add_conditional_edges(
            "our_agent",
            routers.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        
    return workflow.compile()


# ============================================================
# Planner-Supervisor 模式图构建 (对标 LangManus)
# ============================================================

def create_planner_supervisor_graph(
    llm: BaseChatModel,
    tools: list[BaseTool],
    reasoning_llm: BaseChatModel | None = None,
) -> CompiledStateGraph:
    """
    Planner-Supervisor 模式图构建工厂。
    
    对标 LangManus 架构:
    - Coordinator: 入口协调，判断是否需要规划
    - Planner: 生成执行计划
    - Supervisor: 调度执行者
    - Executors: 执行具体任务 (image/video/status_checker)
    - Reporter: 生成最终报告
    
    工作流:
    START -> coordinator -> planner -> supervisor <-> executors -> END
    
    Args:
        llm: 主要使用的 LLM (用于 coordinator, supervisor, executors, reporter)
        tools: 可用工具列表
        reasoning_llm: 推理增强 LLM (用于 planner 的深度思考模式，可选)
        
    Returns:
        编译后的工作流图
    """
    workflow = StateGraph(AgentState)
    
    # ============================================================
    # 1. 创建节点
    # ============================================================
    
    # Coordinator 节点
    coordinator_node = create_coordinator_node(llm)
    workflow.add_node("coordinator", coordinator_node)
    
    # Planner 节点
    planner_node = create_planner_node(llm, reasoning_llm)
    workflow.add_node("planner", planner_node)
    
    # Supervisor 节点
    supervisor_node = create_supervisor_node(llm)
    workflow.add_node("supervisor", supervisor_node)
    
    # Executor 节点
    image_executor_node = create_image_executor_node(llm, tools)
    video_executor_node = create_video_executor_node(llm, tools)
    status_checker_node = create_status_checker_node(llm, tools)
    
    workflow.add_node("image_executor", image_executor_node)
    workflow.add_node("video_executor", video_executor_node)
    workflow.add_node("status_checker", status_checker_node)
    
    # Reporter 节点
    reporter_node = create_reporter_node(llm)
    workflow.add_node("reporter", reporter_node)
    
    # ============================================================
    # 2. 设置边 (对标 LangManus: 使用 Command 自动路由)
    # ============================================================
    
    # 入口: START -> coordinator
    workflow.add_edge(START, "coordinator")
    
    # 注意: 大部分路由由节点内部的 Command 控制
    # coordinator -> planner 或 __end__ (由 coordinator 的 Command 决定)
    # planner -> supervisor 或 __end__ (由 planner 的 Command 决定)
    # supervisor -> executors 或 reporter 或 __end__ (由 supervisor 的 Command 决定)
    # executors -> supervisor (由 executor 的 Command 决定)
    # reporter -> supervisor (由 reporter 的 Command 决定)
    
    # ============================================================
    # 3. 编译并返回
    # ============================================================
    
    return workflow.compile()


# ============================================================
# 混合模式图构建 (根据任务复杂度自动选择)
# ============================================================

def create_hybrid_graph(
    llm: BaseChatModel,
    system_prompt: str,
    tools: list[BaseTool],
    reasoning_llm: BaseChatModel | None = None,
    enable_suggestion: bool = False,
    suggestion_llm: BaseChatModel | None = None,
) -> CompiledStateGraph:
    """
    混合模式图构建工厂。
    
    根据任务复杂度自动选择:
    - 简单任务 -> ReAct 模式
    - 复杂任务 -> Planner-Supervisor 模式
    
    Args:
        llm: 主要使用的 LLM
        system_prompt: ReAct 模式的系统提示词
        tools: 可用工具列表
        reasoning_llm: 推理增强 LLM (可选)
        enable_suggestion: 是否启用建议生成 (ReAct 模式)
        suggestion_llm: 建议生成 LLM (可选)
        
    Returns:
        编译后的工作流图
    """
    workflow = StateGraph(AgentState)
    
    # ============================================================
    # 1. 入口预处理
    # ============================================================
    workflow.add_node("initial_prep", common.initial_prep_node)
    workflow.set_entry_point("initial_prep")
    
    # ============================================================
    # 2. Planner-Supervisor 分支
    # ============================================================
    
    # Coordinator
    coordinator_node = create_coordinator_node(llm)
    workflow.add_node("coordinator", coordinator_node)
    
    # Planner
    planner_node = create_planner_node(llm, reasoning_llm)
    workflow.add_node("planner", planner_node)
    
    # Supervisor
    supervisor_node = create_supervisor_node(llm)
    workflow.add_node("supervisor", supervisor_node)
    
    # Executors
    workflow.add_node("image_executor", create_image_executor_node(llm, tools))
    workflow.add_node("video_executor", create_video_executor_node(llm, tools))
    workflow.add_node("status_checker", create_status_checker_node(llm, tools))
    
    # Reporter
    workflow.add_node("reporter", create_reporter_node(llm))
    
    # ============================================================
    # 3. ReAct 分支
    # ============================================================
    
    model_node = core.create_model_node(llm, system_prompt, tools)
    workflow.add_node("react_agent", model_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("recorder", common.recorder_node)
    
    if enable_suggestion and suggestion_llm:
        sug_node = suggestion.create_suggestion_node(suggestion_llm)
        workflow.add_node("suggestion_generator", sug_node)
    
    # ============================================================
    # 4. 路由逻辑
    # ============================================================
    
    # initial_prep -> coordinator (统一入口)
    workflow.add_edge("initial_prep", "coordinator")
    
    # ReAct 分支内部路由
    workflow.add_edge("tools", "recorder")
    workflow.add_edge("recorder", "react_agent")
    
    if enable_suggestion and suggestion_llm:
        workflow.add_conditional_edges(
            "react_agent",
            routers.should_continue,
            {
                "continue": "tools",
                "end": "suggestion_generator"
            }
        )
        workflow.add_edge("suggestion_generator", END)
    else:
        workflow.add_conditional_edges(
            "react_agent",
            routers.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
    
    # ============================================================
    # 5. 编译并返回
    # ============================================================
    
    return workflow.compile()

