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
from state.schemas import AgentState, SuggestionResponse
from utils.logger import get_logger

# 1. 初始化配置
load_dotenv()
logger = get_logger("mynamechat_suggestion.app")

# 2. 配置 LLM
# 主对话模型
llm = ChatOpenAI(
    model="doubao-seed-1-6-vision-250815",
    temperature=0.0,
    api_key=os.getenv("DOUBAO_API_KEY"),
    base_url=os.getenv("DOUBAO_BASE_URL")
)

# 建议生成模型 (使用 JSON Mode)
suggestion_llm = llm.with_structured_output(
    schema=SuggestionResponse,
    method="json_schema",
    strict=True,
    include_raw=True,
    reasoning_effort="low"
)

# 3. 构建 Graph
# 开启 enable_suggestion=True
app = create_graph(
    llm=llm,
    system_prompt=Your_Name_SYSTEM_PROMPT,
    tools=get_all_tools(),
    enable_suggestion=True,
    suggestion_llm=suggestion_llm
)

