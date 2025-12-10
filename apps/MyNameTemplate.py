import asyncio
import json
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage

from graphs.builder import create_graph
from prompts.templates import Your_Name_SYSTEM_PROMPT
from tools.registry import get_all_tools
from nodes.common import prepare_state_from_payload
from state.schemas import AgentState
from utils.logger import get_logger

# 1. 初始化配置
load_dotenv()
logger = get_logger("mynamechat.app")

# 2. 配置 LLM
# 所有的 Agent 统一使用这个 LLM 配置
llm = ChatOpenAI(
    model="gpt-5-nano",
    temperature=0.0
)

# 3. 构建 Graph
# MyNameTemplate 默认不开启 Suggestion
app = create_graph(
    llm=llm,
    system_prompt=Your_Name_SYSTEM_PROMPT,
    tools=get_all_tools(),
    enable_suggestion=False
)

