from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.graph import CompiledGraph

from state.schemas import AgentState
import nodes.common as common
import nodes.core as core
import nodes.suggestion as suggestion
import nodes.routers as routers

def create_graph(
    llm: BaseChatModel,
    system_prompt: str,
    tools: list[BaseTool],
    enable_suggestion: bool = False,
    suggestion_llm: BaseChatModel = None
) -> CompiledGraph:
    """
    通用图构建工厂。
    
    Args:
        llm: 主 Agent 使用的 LLM。
        system_prompt: 系统提示词模板。
        tools: 可用工具列表。
        enable_suggestion: 是否启用建议生成节点。
                           如果为 True，Graph 会在结束前流转到 suggestion_node。
        suggestion_llm: 建议生成专用的 LLM (仅当 enable_suggestion=True 时需要)。
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

