"""
Service 层模块
提供 HTTP API 接口供前端调用

包含:
- api.py: FastAPI 路由定义
- schemas.py: 请求/响应数据模型
- handlers.py: 业务处理逻辑
"""

from .api import app as api_app

__all__ = ["api_app"]

