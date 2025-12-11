import asyncio
import json
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage

from graphs.builder import create_base_ReAct_graph
from prompts.templates import Your_Name_SYSTEM_PROMPT
from tools.registry import get_all_tools
from nodes.common import prepare_state_from_payload
from state.schemas import AgentState, LegacyAgentResponse
from utils.logger import get_logger, set_logger_context

# 1. 初始化配置
load_dotenv()
set_logger_context("mynamechat.MyNameTemplate")
logger = get_logger("mynamechat.MyNameTemplate")

# 2. 配置 LLM
# 所有的 Agent 统一使用这个 LLM 配置
llm = ChatOpenAI(
    model="doubao-seed-1-6-vision-250815",
    temperature=0.0,
    api_key=os.getenv("DOUBAO_API_KEY"),
    base_url=os.getenv("DOUBAO_BASE_URL"),
)

structured_llm = llm.with_structured_output(
    schema=LegacyAgentResponse,
    method="json_schema",
    strict=True,
    include_raw=True,
    reasoning_effort="medium",
    tools=get_all_tools()
)

SUGGESTION_SYSTEM_PROMPT = """
### Suggestion Logic (in 'suggestions' key)
Always provide exactly 3 strings in the list:
- Option 1 & 2: **Refinement** (e.g., "Fix face details", "Change lighting to sunset").
- Option 3: **Advance** (e.g., "Confirm and generate video", "Next step").
"""

# 3. 构建 Graph
# MyNameTemplate 默认不开启 Suggestion
app = create_base_ReAct_graph(
    llm=structured_llm,
    system_prompt=Your_Name_SYSTEM_PROMPT + SUGGESTION_SYSTEM_PROMPT,
    tools=get_all_tools(),
    enable_suggestion=False
)

