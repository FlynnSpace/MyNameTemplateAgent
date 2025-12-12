# MyNameChat 项目重构架构设计文档

## 1. 核心设计理念

本项目正在从单文件的实验性质代码迁移至模块化的 **Multi-Agent (多智能体)** 架构。本次重构的核心设计模式采用了 **节点工厂 (Node Factory)** 与 **图构建器 (Graph Builder)**，旨在解决以下痛点：

*   **代码冗余**：消除 `MyNameTemplate.py`, `CustomTemplate.py`, `MyNameTemplate_suggestion.py` 三个文件中高度重复的 State 定义、节点逻辑和工具调用代码。
*   **维护困难**：目前修改一个通用逻辑（如“自动回捞上一轮结果”），需要在三个文件中分别修改，极易出错。
*   **配置兼容**：通过 **Thin Wrapper (瘦包装器)** 模式，保留根目录入口文件，确保 `langgraph.json` 无需改动即可运行。

---

## 2. 目录结构规划

我们将采用以下标准化的 Python 工程结构，将核心逻辑下沉到模块中：

```text
MyNameChat/
├── MyNameTemplate.py           # [入口] 瘦包装器：配置 "你的名字" 风格 Agent
├── CustomTemplate.py           # [入口] 瘦包装器：配置 "自定义" 风格 Agent
├── MyNameTemplate_suggestion.py # [入口] 瘦包装器：配置带 "建议生成" 功能的 Agent
├── langgraph.json              # [配置] 保持不变，依然指向上述三个入口文件
├── .env                        # [配置] 环境变量
├── state/                      # [核心] 数据结构定义
│   ├── __init__.py
│   └── schemas.py              # 统一的 AgentState (包含 suggestions 字段)
├── prompts/                    # [核心] 提示词管理
│   ├── __init__.py
│   └── templates.py            # 集中存放 System Prompt (YourName, Custom, Suggestion)
├── tools/                      # [核心] 工具函数
│   ├── __init__.py
│   ├── image.py                # 图像生成与编辑 (Seedream, Banana)
│   ├── video.py                # 视频生成 (Sora)
│   ├── general.py              # 通用工具 (查询状态, 去水印)
│   └── registry.py             # 工具列表导出
├── nodes/                      # [核心] 节点逻辑 (原子操作库)
│   ├── __init__.py
│   ├── common.py               # 通用节点：Recorder, InitialPrep
│   ├── core.py                 # 核心节点：Model Call (包含自动回捞逻辑)
│   ├── suggestion.py           # 扩展节点：Suggestion Generator
│   └── routers.py              # 路由逻辑：should_continue
├── graphs/                     # [核心] 图编排 (业务流定义)
│   ├── __init__.py
│   └── builder.py              # ★ 图构建器：根据配置动态组装 Graph
└── utils/                      # [辅助] 通用工具
    ├── __init__.py
    └── logger.py               # 日志记录器
```

---

## 3. 关键模块详细设计

### 3.1 统一状态定义 (`state/schemas.py`)

为了兼容三种 Agent，我们定义一个全集的 State。

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    references: list[dict]
    # 核心状态追踪
    last_task_id: str | None
    last_tool_name: str | None
    last_task_config: dict | None
    global_config: dict | None
    model_call_count: int
    # 扩展字段 (仅在 suggestion 模式下有值，平时为空列表)
    suggestions: list[str] | None 
```

### 3.2 节点逻辑库 (`nodes/`)

将逻辑拆分为独立的模块，供 Builder 调用：

*   **`nodes/core.py`**: 包含 `model_call` 函数。重点是将 LLM 实例作为参数传入（通过 `functools.partial` 或闭包实现），而不是硬编码全局变量。
*   **`nodes/suggestion.py`**: 包含 `suggestion_node` 函数。
*   **`nodes/common.py`**: 包含 `initial_prep_node` 和 `recorder_node`。

### 3.3 图构建器 (`graphs/builder.py`)

这是本次重构的核心。我们需要一个通用的构建函数，通过参数控制 Graph 的形态。

```python
def create_graph(
    llm: BaseChatModel,
    system_prompt: str,
    tools: list[BaseTool],
    enable_suggestion: bool = False,
    suggestion_llm: BaseChatModel = None
) -> CompiledGraph:
    """
    通用图构建工厂。
    
    Args:
        enable_suggestion: 是否启用建议生成节点。
                           如果为 True，Graph 会在结束前流转到 suggestion_node。
    """
    workflow = StateGraph(AgentState)
    
    # 1. 绑定节点 (使用 partial 注入配置)
    workflow.add_node("initial_prep", common.initial_prep_node)
    
    # 这里的 core.create_model_node 是一个工厂，返回绑定了 prompt 和 llm 的节点函数
    model_node = core.create_model_node(llm, system_prompt, tools)
    workflow.add_node("our_agent", model_node)
    
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("recorder", common.recorder_node)
    
    # 2. 基础连线
    workflow.set_entry_point("initial_prep")
    workflow.add_edge("initial_prep", "our_agent")
    workflow.add_edge("tools", "recorder")
    workflow.add_edge("recorder", "our_agent")
    
    # 3. 动态处理结束流向
    if enable_suggestion:
        if not suggestion_llm:
            raise ValueError("suggestion_llm must be provided if enable_suggestion is True")
            
        sug_node = suggestion.create_suggestion_node(suggestion_llm)
        workflow.add_node("suggestion_generator", sug_node)
        
        # 路由：Agent 结束 -> 建议生成 -> END
        workflow.add_conditional_edges(
            "our_agent",
            routers.should_continue,
            {
                "continue": "tools",
                "end": "suggestion_generator" 
            }
        )
        workflow.add_edge("suggestion_generator", END)
        
    else:
        # 路由：Agent 结束 -> END
        workflow.add_conditional_edges(
            "our_agent",
            routers.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        
    return workflow.compile()
```

### 3.4 入口文件瘦身示例 (`MyNameTemplate_suggestion.py`)

重构后的入口文件将非常简洁，只负责配置：

```python
# MyNameTemplate_suggestion.py
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from graphs.builder import create_graph
from prompts.templates import YOUR_NAME_PROMPT
from tools.registry import get_all_tools

load_dotenv()

# 1. 配置 LLM
main_llm = ChatOpenAI(model="doubao-seed-1-6-vision-250815", temperature=0)
suggestion_llm = ChatOpenAI(model="doubao-seed-1-6-vision-250815", temperature=0) # 配置为 JSON Mode

# 2. 构建 App
app = create_graph(
    llm=main_llm,
    system_prompt=YOUR_NAME_PROMPT,
    tools=get_all_tools(),
    enable_suggestion=True,
    suggestion_llm=suggestion_llm
)

# 3. 导出 chat 函数供本地调试 (可选)
if __name__ == "__main__":
    from utils.runner import run_chat
    run_chat(app)
```

---

## 4. 迁移执行步骤

1.  **Phase 1: 基础搬迁**
    *   建立目录结构。
    *   迁移 `state/schemas.py`。
    *   拆分 `tools/` 和 `prompts/`。

2.  **Phase 2: 节点逻辑库**
    *   提取 `initial_prep`, `recorder` 到 `nodes/common.py`。
    *   **重点**：提取 `model_call` 到 `nodes/core.py`，注意去除全局变量引用，改为工厂模式闭包或参数传递。
    *   提取 `suggestion_node` 到 `nodes/suggestion.py`。

3.  **Phase 3: Graph Builder**
    *   实现 `graphs/builder.py`，编写支持 `enable_suggestion` 分支逻辑的代码。

4.  **Phase 4: 入口替换**
    *   依次重写 `MyNameTemplate.py`, `CustomTemplate.py`, `MyNameTemplate_suggestion.py`，使其调用 Builder。
    *   确保 `langgraph.json` 仍能正确加载 `app` 对象。

5.  **Phase 5: 验证**
    *   分别运行三个入口文件，验证功能一致性。
