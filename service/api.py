"""
FastAPI 路由定义
提供 RESTful API 接口供前端调用
"""

import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .schemas import StreamChatRequest
from . import langgraph_client


# ============================================================
# FastAPI 应用初始化
# ============================================================

app = FastAPI(
    title="LoopSkill Agent API",
    description="""
AI 视频/图像创作助手 API 接口

## 两种调用方式

### 1. REST API (本接口)
- 使用 SSE (Server-Sent Events) 流式返回
- 适用于浏览器前端
- ⚠️ **不支持 LangGraph Cloud 云端部署**

### 2. LangGraph SDK Custom Mode (推荐)
- 使用 `stream_mode="custom"` 直接连接 LangGraph Server
- 适用于 Python 后端 / 脚本
- ✅ **支持云端部署**

```python
from langgraph_sdk import get_client

client = get_client(url="http://localhost:2024")

async for chunk in client.runs.stream(
    thread_id=thread_id,
    assistant_id="planner_supervisor_agent",
    input={"messages": [{"role": "user", "content": "你好"}]},
    stream_mode="custom",
):
    if chunk.event == "custom":
        print(chunk.data)  # {"delta": "..."} / {"thought": "..."} / {"tool_name": "..."}
```

## 可用的 Assistant ID

| ID | 模式 |
|----|------|
| `planner_supervisor_agent` | Planner-Supervisor 模式 |
| `my_name_suggestion_chat_agent` | ReAct 模式 |
| `custom_chat_agent` | ReAct 自定义创作 |
""",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS 配置 - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 对话接口 ⭐ (核心接口)
# ============================================================

@app.post("/api/chat/stream", tags=["对话"])
async def chat_stream_simple(request: StreamChatRequest):
    """
    流式对话接口 ⭐ (对标 planning_agent 设计)
    
    ## SSE 返回格式
    
    所有事件的 event 字段统一为 `"message"`，通过 data 内部字段区分类型。
    
    ### 1. 开始事件
    ```json
    {"type": "start", "thread_id": "xxx"}
    ```
    
    ### 2. 文本回复 (Coordinator 或 Reporter) - 使用 delta 字段
    ```json
    {"delta": "你好！我是 AI 创作助手..."}
    {"delta": "太棒了！你的图片已经在生成中啦 🎨"}
    ```
    
    ### 3. Planner 思考过程 - 流式逐行返回
    ```json
    {"thought": "Thought: 用户想要生成一张图片\\n"}
    {"thought": "1. 生成图片\\n"}
    {"thought": "2. 查询状态\\n"}
    ```
    
    ### 4. Executor 执行结果 - 一次性返回完整 JSON
    ```json
    {"tool_name": "text_to_image", "tool_result": "{\\"step_index\\": 0, \\"status\\": \\"success\\", \\"task_id\\": \\"xxx\\"}"}
    ```
    
    ### 5. 结束事件
    ```json
    {"type": "end", "thread_id": "xxx"}
    ```
    
    ### 6. 错误事件
    ```json
    {"type": "error", "error": "错误信息"}
    ```
    
    ## 两种对话流程
    
    - **简单问题**: start → delta (Coordinator) → end
    - **复杂任务**: start → thought (Planner) → tool_name+tool_result (Executor) → delta (Reporter) → end
    
    ## 前端处理逻辑
    
    ```javascript
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.delta) {
        // 文本回复 (Coordinator 或 Reporter) → 累加拼接
        fullContent += data.delta;
      } else if (data.thought) {
        // 思考过程 → 显示在思考区域
        thinkingContent += data.thought;
      } else if (data.tool_name) {
        // 工具结果 → 渲染卡片
        renderToolCard(data.tool_name, JSON.parse(data.tool_result));
      } else if (data.type === "start") {
        threadId = data.thread_id;
      } else if (data.type === "end") {
        // 完成
      } else if (data.type === "error") {
        showError(data.error);
      }
    };
    ```
    
    ## ⚠️ 注意事项
    
    - 需要先启动 `langgraph dev` 服务
    - 本接口**不支持 LangGraph Cloud 云端部署**
    - 如需云端部署，请使用 LangGraph SDK 的 `stream_mode="custom"` 直接调用
    """
    async def event_generator():
        async for event in langgraph_client.chat_stream_simple(
            message=request.message,
            thread_id=request.thread_id,
            agent_type=request.agent_type,
            deep_thinking=request.deep_thinking,
        ):
            # event 已经是 {"event": "message", "data": {...}} 格式
            # SSE 需要: event 字段 + data 字段(JSON 字符串)
            yield {
                "event": event.get("event", "message"),
                "data": json.dumps(event.get("data", {}), ensure_ascii=False),
            }
    
    return EventSourceResponse(event_generator())
