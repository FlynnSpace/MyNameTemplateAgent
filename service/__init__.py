"""
Service 层模块
提供 HTTP API 接口供前端调用

包含:
- api.py: FastAPI 路由定义 (核心对话接口)
- schemas.py: 请求数据模型
- langgraph_client.py: LangGraph SDK 封装
"""

from .api import app as api_app

__all__ = ["api_app"]
