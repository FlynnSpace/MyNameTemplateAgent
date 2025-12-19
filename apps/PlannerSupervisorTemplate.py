"""
Planner-Supervisor 模式应用入口

对标 LangManus 架构:
- Coordinator: 入口协调，判断是否需要规划
- Planner: 生成执行计划
- Supervisor: 调度执行者
- Executors: 执行具体任务 (image/video/general)
- Reporter: 生成最终报告

工作流:
START -> coordinator -> planner -> supervisor <-> executors -> END
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import OpenAI

from graphs.builder import create_planner_supervisor_graph
from tools.registry import get_all_tools
from utils.logger import get_logger, set_logger_context

# ============================================================
# 1. 初始化配置
# ============================================================
load_dotenv()
set_logger_context("loopskill.PlannerSupervisorTemplate")
logger = get_logger("loopskill.PlannerSupervisorTemplate")

# ============================================================
# 2. 配置 LLM
# ============================================================

# 主要模型 (用于 coordinator, supervisor, executors, reporter)
llm2 = ChatOpenAI(
    model=os.getenv("BASIC_MODEL", "doubao-seed-1-8-251215"),
    temperature=0.0,
    api_key=os.getenv("DOUBAO_API_KEY"),
    base_url=os.getenv("DOUBAO_BASE_URL"),
    model_kwargs={
        "extra_body": {
            "thinking": {"type": "enabled"},
        }
    },
)
llm = ChatOpenAI(model = "gpt-5-mini",
    temperature=0.0,
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)
#llm = ChatOpenAI(
#    model="google/gemini-2.5-flash",
#    openai_api_key=os.getenv("ROUTER_GEMINI_KEY"),
#    openai_api_base=os.getenv("ROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
#)

# 推理增强模型 (用于 planner 的深度思考模式，可选)
# 如果设置了 REASONING_MODEL，则启用
reasoning_llm = None

if os.getenv("REASONING_MODEL"):
    reasoning_llm = ChatOpenAI(
        model=os.getenv("REASONING_MODEL"),
        temperature=0.0,
        api_key=os.getenv("REASONING_API_KEY", os.getenv("DOUBAO_API_KEY")),
        base_url=os.getenv("REASONING_BASE_URL", os.getenv("DOUBAO_BASE_URL"))
    )
    logger.info(f"启用推理增强模型: {os.getenv('REASONING_MODEL')}")

# ============================================================
# 3. 构建 Graph
# ============================================================

app = create_planner_supervisor_graph(
    llm=llm,
    tools=get_all_tools(),
    reasoning_llm=reasoning_llm,
)

logger.info("Planner-Supervisor 模式应用已初始化")

