"""
Supervisor 节点
监督者：根据执行计划调度执行者，监控执行进度

对标 LangManus 实现：
- 使用 with_structured_output 强制结构化输出
- 简洁的决策逻辑
"""

from typing import Literal
from langchain_core.language_models import BaseChatModel
from langgraph.types import Command

from state.schemas import AgentState, SupervisorDecision
from prompts.templates import apply_prompt_template
from utils.logger import get_logger

logger = get_logger("loopskill.nodes.supervisor")


def create_supervisor_node(llm: BaseChatModel):
    """
    创建 Supervisor 节点 (对标 LangManus)
    
    使用 with_structured_output 强制 LLM 返回结构化决策
    
    Args:
        llm: 用于决策的语言模型
        
    Returns:
        supervisor 节点函数
    """
    
    def supervisor_node(state: AgentState) -> Command[Literal["image_executor", "video_executor", "general_executor", "reporter", "__end__"]]:
        """
        监督者节点：决定下一步执行哪个 agent
        
        对标 LangManus 实现逻辑：
        - 使用 with_structured_output(SupervisorDecision) 强制结构化输出
        - 直接从响应中获取 next 字段
        - 如果 next == "FINISH"，则结束工作流
        """
        logger.info("Supervisor 开始决策下一个行动")
        
        # 应用提示词模板 (对标 LangManus: apply_prompt_template)
        messages = apply_prompt_template("supervisor", state)
        
        # 使用 structured_output 获取决策 (对标 LangManus: with_structured_output)
        response = llm.with_structured_output(SupervisorDecision).invoke(messages)
        logger.info(f"Supervisor 响应: {response}") # TODO: 删除
        # 安全获取 next 字段，处理可能的异常情况
        goto = None
        if response is not None:
            # response 可能是 dict 或 Pydantic 对象
            if isinstance(response, dict):
                # 优先使用 next 字段
                if response.get("next"):
                    goto = response.get("next")
                elif response.get("name"):
                    goto = response.get("name")
            # 豆包模型返回的 tool call 列表格式: [{'name': 'xxx', 'parameters': {...}}]
            elif isinstance(response, list) and len(response) > 0:
                first_call = response[0]
                if isinstance(first_call, dict) and 'name' in first_call:
                    goto = first_call.get('name')
                    logger.debug(f"从豆包 tool call 格式中提取 goto: {goto}")
            elif hasattr(response, "next"):
                goto = response.next
        
        # 如果无法获取有效的 next，默认结束
        if goto is None:
            logger.warning(f"Supervisor 无法解析响应: {response}，默认结束工作流")
            goto = "__end__"
        
        logger.debug(f"Current state messages: {state.get('messages', [])}")
        logger.debug(f"Supervisor 响应: {response}")
        
        # 路由决策 (对标 LangManus)
        if goto == "FINISH":
            goto = "__end__"
            logger.info("Workflow completed")
        else:
            logger.info(f"Supervisor delegating to: {goto}")
        
        return Command(goto=goto, update={"next": goto})
    
    return supervisor_node

