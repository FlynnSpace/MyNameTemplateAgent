"""
FastAPI 路由定义
提供 RESTful API 接口供前端调用
"""

import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .schemas import (
    StreamChatRequest,
    TaskStatusRequest,
    TaskStatusResponse,
    GlobalConfigRequest,
    GlobalConfigResponse,
    HistoryListResponse,
    HealthResponse,
    ThreadResponse,
    ThreadHistoryResponse,
)
from . import handlers
from . import langgraph_client


# ============================================================
# FastAPI 应用初始化
# ============================================================

app = FastAPI(
    title="LoopSkill Agent API",
    description="AI 视频/图像创作助手 API 接口",
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
# 健康检查接口
# ============================================================

@app.get("/api/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """
    服务健康检查
    
    返回服务状态和各 Agent 可用性
    """
    return await handlers.check_health()


# ============================================================
# Thread 管理接口 (LangGraph SDK)
# ============================================================

@app.post("/api/threads", response_model=ThreadResponse, tags=["Thread"])
async def create_thread():
    """
    创建新的 Thread
    
    返回一个持久化的 thread_id，用于后续对话
    
    **注意**: 需要先启动 `langgraph dev` 服务
    """
    try:
        thread = await langgraph_client.create_thread()
        return ThreadResponse(
            success=True,
            message="Thread 创建成功",
            thread_id=thread["thread_id"],
            created_at=thread.get("created_at"),
            metadata=thread.get("metadata", {}),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 Thread 失败: {str(e)}")


@app.get("/api/threads/{thread_id}", response_model=ThreadResponse, tags=["Thread"])
async def get_thread(thread_id: str):
    """
    获取 Thread 信息
    
    - **thread_id**: Thread ID
    """
    thread = await langgraph_client.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} 不存在")
    
    return ThreadResponse(
        success=True,
        message="获取成功",
        thread_id=thread["thread_id"],
        created_at=thread.get("created_at"),
        metadata=thread.get("metadata", {}),
    )


@app.get("/api/threads/{thread_id}/history", response_model=ThreadHistoryResponse, tags=["Thread"])
async def get_thread_history(thread_id: str):
    """
    获取 Thread 的历史消息
    
    - **thread_id**: Thread ID
    """
    messages = await langgraph_client.get_thread_history(thread_id)
    return ThreadHistoryResponse(
        success=True,
        message="获取成功",
        thread_id=thread_id,
        messages=messages,
    )


@app.delete("/api/threads/{thread_id}", tags=["Thread"])
async def delete_thread(thread_id: str):
    """
    删除 Thread
    
    - **thread_id**: Thread ID
    """
    success = await langgraph_client.delete_thread(thread_id)
    if not success:
        raise HTTPException(status_code=500, detail=f"删除 Thread {thread_id} 失败")
    
    return {
        "success": True,
        "message": f"Thread {thread_id} 已删除",
    }


# ============================================================
# 对话接口 ⭐ (核心接口)
# ============================================================

@app.post("/api/chat/stream", tags=["对话"])
async def chat_stream_simple(request: StreamChatRequest):
    """
    流式对话接口 ⭐ (只返回关键信息)
    
    **前端使用此接口**，只返回用户关心的信息
    
    返回 SSE 流，包含以下事件类型:
    
    - **start**: 对话开始
      ```json
      {"event": "start", "thread_id": "xxx"}
      ```
    
    - **response**: Coordinator 直接回复 (简单问题，如问候语)
      ```json
      {"event": "response", "content": "你好！我是 AI 创作助手...", "from": "coordinator"}
      ```
    
    - **planning**: Planner 的思考过程 (复杂任务)
      ```json
      {"event": "planning", "thought": "用户想要...", "title": "生成图片", "total_steps": 2}
      ```
    
    - **executing**: 执行进度
      ```json
      {"event": "executing", "executor": "image_executor", "step_index": 0, "status": "success", "task_id": "xxx", "summary": "执行了 1 个工具调用"}
      ```
    
    - **report**: Reporter 的最终报告 (复杂任务完成后)
      ```json
      {"event": "report", "content": "太棒了！你的图片已经在生成中啦 🎨"}
      ```
    
    - **end**: 对话结束，包含汇总
      ```json
      {"event": "end", "thread_id": "xxx", "summary": {"title": "生成图片", "task_ids": ["xxx"], "total_steps": 1}}
      ```
    
    - **error**: 发生错误
      ```json
      {"event": "error", "error": "错误信息"}
      ```
    
    **两种对话流程**:
    - 简单问题: start → response → end
    - 复杂任务: start → planning → executing → report → end
    
    **注意**: 需要先启动 `langgraph dev` 服务
    """
    async def event_generator():
        async for event in langgraph_client.chat_stream_simple(
            message=request.message,
            thread_id=request.thread_id,
            agent_type=request.agent_type,
            deep_thinking=request.deep_thinking,
        ):
            yield {
                "event": event.get("event", "message"),
                "data": json.dumps(event, ensure_ascii=False),
            }
    
    return EventSourceResponse(event_generator())


# ============================================================
# 任务状态接口
# ============================================================

@app.post("/api/task/status", response_model=TaskStatusResponse, tags=["任务"])
async def get_task_status(request: TaskStatusRequest):
    """
    查询任务状态
    
    - **task_id**: 任务ID
    - **task_type**: 任务类型 (image / video)
    """
    result = await handlers.get_task_status(
        task_id=request.task_id,
        task_type=request.task_type,
    )
    return TaskStatusResponse(**result)


@app.get("/api/task/{task_id}", response_model=TaskStatusResponse, tags=["任务"])
async def get_task_status_by_id(task_id: str, task_type: str = "image"):
    """
    通过路径参数查询任务状态
    
    - **task_id**: 任务ID
    - **task_type**: 任务类型 (默认 image)
    """
    result = await handlers.get_task_status(
        task_id=task_id,
        task_type=task_type,
    )
    return TaskStatusResponse(**result)


# ============================================================
# 配置接口
# ============================================================

@app.get("/api/config", response_model=GlobalConfigResponse, tags=["配置"])
async def get_config():
    """
    获取当前全局配置
    """
    return GlobalConfigResponse(
        success=True,
        message="获取成功",
        config={
            "style": "your_name",
            "resolution": "1024x1024",
            "aspect_ratio": "1:1",
        }
    )


@app.put("/api/config", response_model=GlobalConfigResponse, tags=["配置"])
async def update_config(request: GlobalConfigRequest):
    """
    更新全局配置
    
    - **style**: 默认风格
    - **resolution**: 默认分辨率
    - **aspect_ratio**: 默认宽高比
    """
    new_config = {}
    if request.style:
        new_config["style"] = request.style
    if request.resolution:
        new_config["resolution"] = request.resolution
    if request.aspect_ratio:
        new_config["aspect_ratio"] = request.aspect_ratio
    
    return GlobalConfigResponse(
        success=True,
        message="配置更新成功",
        config=new_config,
    )


# ============================================================
# 历史记录接口
# ============================================================

@app.get("/api/history", response_model=HistoryListResponse, tags=["历史"])
async def list_history(page: int = 1, page_size: int = 20):
    """
    获取对话历史列表
    
    - **page**: 页码 (从 1 开始)
    - **page_size**: 每页数量 (默认 20)
    """
    try:
        offset = (page - 1) * page_size
        threads = await langgraph_client.list_threads(limit=page_size, offset=offset)
        
        conversations = []
        for t in threads:
            conversations.append({
                "thread_id": t.get("thread_id", ""),
                "messages": [],
                "created_at": t.get("created_at", ""),
                "updated_at": t.get("updated_at", ""),
            })
        
        return HistoryListResponse(
            success=True,
            message="获取成功",
            conversations=conversations,
            total=len(threads),
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        return HistoryListResponse(
            success=False,
            message=f"获取失败: {str(e)}",
            conversations=[],
            total=0,
            page=page,
            page_size=page_size,
        )


@app.delete("/api/history/{thread_id}", tags=["历史"])
async def delete_history(thread_id: str):
    """
    删除指定对话历史
    
    - **thread_id**: 对话线程ID
    """
    success = await langgraph_client.delete_thread(thread_id)
    return {
        "success": success,
        "message": f"对话 {thread_id} 已删除" if success else f"删除失败",
    }


# ============================================================
# 入口点 (用于直接运行)
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "service.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
