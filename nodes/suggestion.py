from typing import Callable
from langchain_core.messages import SystemMessage
from langchain_core.language_models import BaseChatModel
from state.schemas import AgentState
from prompts.templates import SUGGESTION_SYSTEM_PROMPT
from utils.logger import get_logger

logger = get_logger("mynamechat.nodes.suggestion")

def log_system_message(message: str, echo: bool = False) -> None:
    logger.info(message)
    if echo:
        print(message)

def create_suggestion_node(suggestion_llm: BaseChatModel) -> Callable[[AgentState], dict]:
    """
    Factory to create a suggestion node with a specific LLM.
    """
    
    def suggestion_node(state: AgentState) -> dict:
        """建议生成节点：基于当前对话历史生成后续建议"""
        log_system_message("--- [DEBUG] Generating Suggestions ---", echo=False)
        
        # 构建专门的 Prompt 用于生成建议
        # 获取最近的对话作为上下文
        messages = state["messages"][-5:] # 取最近5条即可
        
        prompt = SystemMessage(content=SUGGESTION_SYSTEM_PROMPT)
        
        try:
            response = suggestion_llm.invoke([prompt] + messages)
            # Handle structured output
            if hasattr(response, "parsed") and response.parsed:
                 suggestions = response.parsed.suggestions
            elif isinstance(response, dict) and "suggestions" in response:
                 suggestions = response["suggestions"]
            # Fallback for some LLM wrappers that might behave differently
            elif hasattr(response, "suggestions"): 
                suggestions = response.suggestions
            else:
                 # Should not happen with strict schema, but safe fallback
                 suggestions = []

            log_system_message(f"--- [DEBUG] Suggestions Generated: {suggestions}", echo=False)
            return {"suggestions": suggestions}
        except Exception as e:
            logger.error(f"Failed to generate suggestions: {e}")
            return {"suggestions": []}

    return suggestion_node

