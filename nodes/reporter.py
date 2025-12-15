"""
Reporter 节点
汇报者：根据执行结果生成最终报告

对标 LangManus 实现：
- 使用 apply_prompt_template 构建提示词
- 使用 RESPONSE_FORMAT 格式化输出
"""

from typing import Literal
from langchain_core.messages import HumanMessage
from langchain_core.language_models import BaseChatModel
from langgraph.types import Command

from state.schemas import AgentState
from prompts.templates import apply_prompt_template, RESPONSE_FORMAT
from utils.logger import get_logger

logger = get_logger("loopskill.nodes.reporter")


def create_reporter_node(llm: BaseChatModel):
    """
    创建 Reporter 节点
    
    Args:
        llm: 语言模型
        
    Returns:
        reporter 节点函数
    """
    
    def reporter_node(state: AgentState) -> Command[Literal["supervisor"]]:
        """
        汇报者节点：根据执行结果生成最终报告
        
        对标 LangManus 实现逻辑：
        - 使用 apply_prompt_template 构建提示词
        - 调用 LLM 生成报告
        - 使用 RESPONSE_FORMAT 格式化输出
        - 返回到 supervisor
        """
        logger.info("Reporter write final report")
        
        # 应用提示词模板 (对标 LangManus: apply_prompt_template)
        messages = apply_prompt_template("reporter", state)
        
        # 调用 LLM 生成报告
        response = llm.invoke(messages)
        
        logger.debug(f"Current state messages: {state.get('messages', [])}")
        logger.debug(f"Reporter 响应: {response}")
        
        # 格式化输出 (对标 LangManus: RESPONSE_FORMAT)
        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=RESPONSE_FORMAT.format("reporter", response.content),
                        name="reporter",
                    )
                ]
            },
            goto="supervisor",
        )
    
    return reporter_node


