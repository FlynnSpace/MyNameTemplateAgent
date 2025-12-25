"""
Reporter 节点
汇报者：根据执行结果生成最终报告

对标 LangManus 实现：
- 使用 apply_prompt_template 构建提示词
- 使用 RESPONSE_FORMAT 格式化输出

流式输出：
- 使用 get_stream_writer() 发送 {"delta": "..."} 格式数据
- 发送 {"type": "end"} 事件标记结束
"""

from typing import Literal
from langchain_core.messages import HumanMessage
from langchain_core.language_models import BaseChatModel
from langgraph.types import Command
from langgraph.config import get_stream_writer, get_config

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
    
    def reporter_node(state: AgentState) -> Command[Literal["__end__"]]:
        """
        汇报者节点：根据执行结果生成最终报告
        
        对标 LangManus 实现逻辑：
        - 使用 apply_prompt_template 构建提示词
        - 调用 LLM 生成报告
        - 使用 RESPONSE_FORMAT 格式化输出
        - 直接结束工作流
        
        流式输出：发送 {"delta": "..."} + {"type": "end"} 事件
        """
        logger.info("Reporter 开始生成最终报告")
        
        # 获取流式写入器和配置
        writer = get_stream_writer()
        config = get_config()
        thread_id = config.get("configurable", {}).get("thread_id", "unknown")
        
        # 应用提示词模板 (对标 LangManus: apply_prompt_template)
        messages = apply_prompt_template("reporter", state)
        
        # 调试：打印实际使用的提示词
        logger.info(f"Reporter 提示词: {messages[0]['content'][:500]}...")
        logger.info(f"Reporter step_results: {state.get('step_results')}")
        
        # 使用流式调用 LLM 生成报告
        response_content = ""
        for chunk in llm.stream(messages):
            chunk_content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if chunk_content:
                response_content += chunk_content
                # 流式发送 delta
                writer({"delta": chunk_content})
        
        logger.debug(f"Current state messages: {state.get('messages', [])}")
        logger.info(f"Reporter 响应: {response_content}")
        
        # Reporter 的输出是给用户看的最终报告
        # 使用 RESPONSE_FORMAT 用于内部通信（让 Supervisor 知道 Reporter 已完成）
        # 同时保留干净的 response_content 供前端提取展示
        formatted_for_supervisor = RESPONSE_FORMAT.format("reporter", response_content)
        
        # 发送结束事件
        writer({"type": "end", "thread_id": thread_id})
        
        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=formatted_for_supervisor,
                        name="reporter",
                    )
                ],
                # 额外存储干净的报告内容，供前端直接使用
                "final_report": response_content,
            },
            goto="__end__",  # Reporter 是工作流最后一步，直接结束
        )
    
    return reporter_node


