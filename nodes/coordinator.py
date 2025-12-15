"""
Coordinator 节点
入口协调者：处理问候/简单查询，复杂任务转发给 Planner

对标 LangManus 实现：
- 使用 LLM 判断是否需要规划
- 检查响应中是否包含 handoff_to_planner
"""

from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel
from langgraph.types import Command

from state.schemas import AgentState
from prompts.templates import apply_prompt_template
from utils.logger import get_logger

logger = get_logger("loopskill.nodes.coordinator")


def create_coordinator_node(llm: BaseChatModel):
    """
    创建 Coordinator 节点
    
    Args:
        llm: 用于判断的语言模型
        
    Returns:
        coordinator 节点函数
    """
    
    def coordinator_node(state: AgentState) -> Command[Literal["planner", "__end__"]]:
        """
        协调者节点：判断用户输入类型并路由
        
        对标 LangManus 实现逻辑：
        - 调用 LLM 处理用户输入
        - 检查响应中是否包含 "handoff_to_planner"
        - 如果包含 → 转发给 planner
        - 否则 → 直接回复用户 → __end__
        """
        logger.info("Coordinator 开始处理用户输入")
        
        # 应用提示词模板 (对标 LangManus: apply_prompt_template)
        messages = apply_prompt_template("coordinator", state)
        
        # 调用 LLM
        response = llm.invoke(messages)
        response_content = response.content if hasattr(response, "content") else str(response)
        
        logger.debug(f"Current state messages: {state.get('messages', [])}")
        logger.debug(f"Coordinator 响应: {response_content}")
        
        # 判断路由 (对标 LangManus: 检查 "handoff_to_planner")
        goto = "__end__"
        if "handoff_to_planner" in response_content:
            goto = "planner"
            logger.info("Coordinator handoff to planner")
            return Command(goto=goto)
        
        # 直接回复用户
        logger.info("Coordinator direct response")
        return Command(
            goto=goto,
            update={
                "messages": [AIMessage(content=response_content, name="coordinator")],
            }
        )
    
    return coordinator_node

