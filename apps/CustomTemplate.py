import asyncio
import json
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage

from graphs.builder import create_base_ReAct_graph
from prompts.templates import Custom_SYSTEM_PROMPT # 使用 Custom Prompt
from tools.registry import get_all_tools
from nodes.common import prepare_state_from_payload
from state.schemas import AgentState
from utils.logger import get_logger, set_logger_context

# 1. 初始化配置
load_dotenv()
set_logger_context("customchat.CustomTemplate")
logger = get_logger("customchat.CustomTemplate")

# 2. 配置 LLM
llm = ChatOpenAI(
    model="gpt-5-nano",
    temperature=0.0
)

# 3. 构建 Graph
app = create_base_ReAct_graph(
    llm=llm,
    system_prompt=Custom_SYSTEM_PROMPT, # 差异点：使用 Custom Prompt
    tools=get_all_tools(),
    enable_suggestion=False
)

