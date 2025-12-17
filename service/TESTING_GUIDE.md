# LoopSkill Agent 本地测试指南

> 本文档指导如何在本地启动服务，并使用 Apifox 测试 `planner_supervisor_agent` 的流式对话功能。

---

## 目录

- [环境准备](#环境准备)
- [启动服务](#启动服务)
- [API 版本说明](#api-版本说明)
- [Apifox 配置](#apifox-配置)
- [测试用例](#测试用例)
- [使用 SDK 接口（推荐）](#使用-sdk-接口推荐)
- [常见问题](#常见问题)

---

## 环境准备

### 1. 安装依赖

```bash
cd C:\Users\D5\Desktop\code\LoopSkillAgent

# 安装 Python 依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

确保项目根目录下有 `.env` 文件，包含以下配置：

```env
# LLM 配置
DOUBAO_API_KEY=your-doubao-api-key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
BASIC_MODEL=doubao-seed-1-6-vision-250815

# KIE 服务 (视频生成)
KIE_API_KEY=your-kie-api-key

# PPIO 服务 (图像生成)
GEMINI_API_KEY=your-ppio-api-key

# Supabase (任务状态追踪)
VITE_SUPABASE_URL=your-supabase-url
VITE_SUPABASE_ANON_KEY=your-supabase-key
```

---

## 启动服务

你有 **两种方式** 启动服务：

### 方式一：FastAPI 服务 (推荐用于前端开发)

```bash
# 在项目根目录下执行
python -m service.api
```

或者使用 uvicorn (支持热重载)：

```bash
uvicorn service.api:app --host 0.0.0.0 --port 8000 --reload
```

**服务地址**: `http://localhost:8000`

启动成功后会看到：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx]
```

### 方式二：LangGraph 原生服务

```bash
langgraph dev
```

**服务地址**: `http://localhost:2024`

---

## API 版本说明

我们提供两套 API：

| 版本 | 路径前缀 | 持久化 | 适用场景 |
|------|----------|--------|----------|
| v1 (原版) | `/api/chat` | ❌ 不支持 | 简单测试、无需历史 |
| **v2 (SDK)** | `/api/v2/chat` | ✅ 支持 | **推荐！生产环境使用** |

**重要**: 如果需要保存对话历史，请使用 v2 接口，并确保 `langgraph dev` 服务正在运行。

---

## Apifox 配置

### 步骤 1：创建新项目

1. 打开 Apifox
2. 点击 **"新建项目"**
3. 项目名称填写：`LoopSkill Agent`

### 步骤 2：配置环境

1. 点击右上角 **"环境管理"**
2. 添加环境变量：

| 变量名 | 本地开发值 |
|--------|-----------|
| `base_url` | `http://localhost:8000` |

### 步骤 3：测试健康检查接口

先测试服务是否正常运行：

1. 点击 **"新建" → "快捷请求"**
2. 配置如下：
   - **Method**: `GET`
   - **URL**: `{{base_url}}/api/health`
3. 点击 **"发送"**

**预期响应**：

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "agents": {
    "react": true,
    "planner_supervisor": true
  }
}
```

### 步骤 4：测试普通对话接口

1. **新建请求**
2. 配置如下：
   - **Method**: `POST`
   - **URL**: `{{base_url}}/api/chat`
   - **Headers**: 
     - `Content-Type`: `application/json`
   - **Body** (JSON):

```json
{
  "message": "帮我生成一张新海诚风格的夕阳场景图片",
  "agent_type": "planner_supervisor",
  "deep_thinking": false
}
```

3. 点击 **"发送"**

**预期响应**：

```json
{
  "success": true,
  "message": "对话完成",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "answer": "我已经为您规划了图片生成任务...",
  "suggestions": ["调整色调", "添加人物", "转换为视频"],
  "task_ids": ["task_xxx"],
  "media_urls": []
}
```

---

### 步骤 5：测试流式对话接口 (SSE) ⭐

这是重点！Apifox 支持 SSE 流式请求。

#### 方法 A：使用 Apifox 的 SSE 功能

1. **新建请求**
2. 配置如下：
   - **Method**: `POST`
   - **URL**: `{{base_url}}/api/chat/stream`
   - **Headers**: 
     - `Content-Type`: `application/json`
     - `Accept`: `text/event-stream`
   - **Body** (JSON):

```json
{
  "message": "帮我生成一张赛博朋克风格的城市夜景图片，要有霓虹灯和雨天效果",
  "agent_type": "planner_supervisor",
  "deep_thinking": false
}
```

3. 点击 **"发送"** 按钮旁边的下拉箭头，选择 **"SSE"** 模式
4. 点击 **"发送"**

#### 方法 B：使用 Apifox 的实时预览

如果上面方法不生效，尝试：

1. 在请求设置中找到 **"高级设置"** 或 **"更多设置"**
2. 开启 **"流式响应"** 或 **"实时预览"** 选项
3. 发送请求

**预期 SSE 输出流**：

```
event: start
data: {"event": "start", "thread_id": "xxx-xxx-xxx"}

event: token
data: {"event": "token", "content": "好的"}

event: token
data: {"event": "token", "content": "，我来"}

event: token
data: {"event": "token", "content": "帮您"}

event: tool_start
data: {"event": "tool_start", "tool_name": "image_edit_banana_pro"}

event: tool_end
data: {"event": "tool_end", "tool_name": "image_edit_banana_pro", "output": "任务已创建..."}

event: token
data: {"event": "token", "content": "图片生成任务已提交..."}

event: end
data: {"event": "end", "thread_id": "xxx-xxx-xxx"}
```

---

## 测试用例

### 用例 1：简单图片生成

```json
{
  "message": "生成一张日落海边的图片",
  "agent_type": "planner_supervisor"
}
```

### 用例 2：复杂多步骤任务

```json
{
  "message": "帮我创作一个《你的名字》风格的场景：黄昏时分，男主角站在天桥上看着远方的城市，要有流星划过天空的效果",
  "agent_type": "planner_supervisor",
  "deep_thinking": true
}
```

### 用例 3：图片编辑任务

```json
{
  "message": "把上一张图片的天空改成星空效果",
  "agent_type": "planner_supervisor",
  "thread_id": "之前返回的thread_id"
}
```

### 用例 4：视频生成任务

```json
{
  "message": "把这张图片转换成一段5秒的视频，添加微风吹动的效果",
  "agent_type": "planner_supervisor"
}
```

### 用例 5：查询任务状态

```json
// POST /api/task/status
{
  "task_id": "从对话响应中获取的task_id",
  "task_type": "image"
}
```

---

## Apifox 接口集合导入

为了方便测试，你可以直接导入以下接口集合配置：

### 快速创建接口集合

在 Apifox 中创建以下接口：

| 接口名称 | Method | URL | 说明 |
|----------|--------|-----|------|
| 健康检查 | GET | `/api/health` | 检查服务状态 |
| 普通对话 | POST | `/api/chat` | 非流式对话 |
| 流式对话 | POST | `/api/chat/stream` | SSE 流式对话 |
| 查询任务状态 | POST | `/api/task/status` | 查询生成任务 |
| 获取任务状态 | GET | `/api/task/{task_id}` | 路径参数查询 |
| 获取配置 | GET | `/api/config` | 获取全局配置 |
| 更新配置 | PUT | `/api/config` | 更新全局配置 |

---

## 完整测试流程示例

### 场景：生成新海诚风格图片并转视频

**第一步：发起图片生成请求**

```
POST {{base_url}}/api/chat/stream
Content-Type: application/json
Accept: text/event-stream

{
  "message": "帮我生成一张新海诚风格的黄昏城市天际线图片，要有火烧云的效果",
  "agent_type": "planner_supervisor"
}
```

**观察 SSE 流输出**，记录返回的 `thread_id` 和 `task_id`。

**第二步：查询任务状态**

```
GET {{base_url}}/api/task/task_xxx?task_type=image
```

等待状态变为 `completed`，获取 `result_url`。

**第三步：继续对话 - 转换为视频**

```
POST {{base_url}}/api/chat/stream
Content-Type: application/json
Accept: text/event-stream

{
  "message": "把刚才生成的图片转换成视频，添加云层流动的效果",
  "agent_type": "planner_supervisor",
  "thread_id": "第一步返回的thread_id"
}
```

**第四步：查询视频任务状态**

```
POST {{base_url}}/api/task/status
Content-Type: application/json

{
  "task_id": "video_task_xxx",
  "task_type": "video"
}
```

---

## 使用 SDK 接口（推荐）

如果需要 **保存对话历史**，请使用 v2 接口。这些接口通过 LangGraph SDK 调用 `langgraph dev` 服务，自动持久化所有 Thread 状态。

### 前置条件

1. **必须先启动 `langgraph dev`**（端口 2024）
2. 然后启动我们的 FastAPI 服务（端口 8000）

```bash
# 终端 1：启动 LangGraph 服务
langgraph dev

# 终端 2：启动 FastAPI 服务
python -m service.api
```

### 完整测试流程（保存历史）

#### 第一步：创建 Thread

```
POST http://localhost:8000/api/v2/threads
```

**响应**:
```json
{
  "success": true,
  "message": "Thread 创建成功",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-12-17T10:30:00Z",
  "metadata": {}
}
```

**记住返回的 `thread_id`！**

#### 第二步：发送第一条消息

```
POST http://localhost:8000/api/v2/chat/stream
Content-Type: application/json
Accept: text/event-stream

{
  "message": "帮我生成一张新海诚风格的夕阳图片",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "planner_supervisor"
}
```

#### 第三步：继续对话（历史已保存）

```
POST http://localhost:8000/api/v2/chat/stream
Content-Type: application/json
Accept: text/event-stream

{
  "message": "把颜色改暖一些",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_type": "planner_supervisor"
}
```

**Agent 会记住之前的对话内容！**

#### 第四步：查看历史消息

```
GET http://localhost:8000/api/v2/threads/550e8400-e29b-41d4-a716-446655440000/history
```

**响应**:
```json
{
  "success": true,
  "message": "获取成功",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {"type": "human", "content": "帮我生成一张新海诚风格的夕阳图片"},
    {"type": "ai", "content": "好的，我来帮您生成..."},
    {"type": "human", "content": "把颜色改暖一些"},
    {"type": "ai", "content": "已经调整了图片的色调..."}
  ]
}
```

### SDK 接口列表

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v2/threads` | POST | 创建新 Thread |
| `/api/v2/threads/{id}` | GET | 获取 Thread 信息 |
| `/api/v2/threads/{id}` | DELETE | 删除 Thread |
| `/api/v2/threads/{id}/history` | GET | 获取历史消息 |
| `/api/v2/chat` | POST | 对话（非流式） |
| `/api/v2/chat/stream` | POST | 对话（流式 SSE）⭐ |

### Apifox 配置 SDK 接口

在 Apifox 中添加以下请求：

```
┌─────────────────────────────────────────────────────────┐
│  1. 创建 Thread                                         │
├─────────────────────────────────────────────────────────┤
│  POST  │  {{base_url}}/api/v2/threads                   │
│  Body: (无)                                             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  2. 流式对话 (SDK)                                      │
├─────────────────────────────────────────────────────────┤
│  POST  │  {{base_url}}/api/v2/chat/stream               │
│  Headers:                                               │
│  ├─ Content-Type: application/json                      │
│  └─ Accept: text/event-stream                           │
│  Body:                                                  │
│  {                                                      │
│    "message": "你的消息",                                │
│    "thread_id": "之前创建的ID",                          │
│    "agent_type": "planner_supervisor"                   │
│  }                                                      │
│  发送模式: SSE                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  3. 查看历史                                            │
├─────────────────────────────────────────────────────────┤
│  GET  │  {{base_url}}/api/v2/threads/{thread_id}/history│
└─────────────────────────────────────────────────────────┘
```

---

## 常见问题

### Q1: 服务启动失败

**错误**: `ModuleNotFoundError: No module named 'fastapi'`

**解决**: 安装依赖

```bash
pip install -r requirements.txt
```

### Q2: SSE 流没有输出

**可能原因**:
1. Apifox 没有开启 SSE 模式
2. 请求头缺少 `Accept: text/event-stream`

**解决**:
- 确保选择 SSE 发送模式
- 添加正确的请求头

### Q3: Agent 返回错误

**错误**: `"success": false, "message": "Agent 加载失败"`

**解决**: 检查 `.env` 配置，确保 API Key 正确

### Q4: 任务状态一直是 pending

**可能原因**: 后端服务（KIE/PPIO）未正确配置

**解决**: 检查 `.env` 中的服务 API Key

### Q5: 如何使用 curl 测试流式接口？

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"message": "生成一张日落图片", "agent_type": "planner_supervisor"}' \
  --no-buffer
```

### Q6: v2 接口报错 "连接被拒绝"

**错误**: `Connection refused` 或 `创建 Thread 失败`

**解决**: 确保 `langgraph dev` 正在运行（端口 2024）

```bash
# 检查端口是否被监听
netstat -an | findstr "2024"

# 如果没有，启动 langgraph 服务
langgraph dev
```

### Q7: 为什么 v1 接口不保存历史？

v1 接口 (`/api/chat`) 直接调用编译后的图，没有使用 LangGraph 的 Checkpointer 持久化机制。

v2 接口 (`/api/v2/chat`) 通过 LangGraph SDK 调用 `langgraph dev` 服务，该服务内置了 SQLite Checkpointer，自动保存所有 Thread 状态。

### Q8: 如何在生产环境使用持久化？

生产环境建议：
1. 使用 PostgreSQL 作为 Checkpointer 后端
2. 配置 `langgraph.json` 中的存储设置
3. 或者使用 LangGraph Cloud 服务

---

## 附录：Apifox SSE 测试截图指引

### 设置请求

```
┌─────────────────────────────────────────────────────────┐
│  POST  │  {{base_url}}/api/chat/stream                  │
├─────────────────────────────────────────────────────────┤
│  Headers                                                │
│  ├─ Content-Type: application/json                      │
│  └─ Accept: text/event-stream                           │
├─────────────────────────────────────────────────────────┤
│  Body (JSON)                                            │
│  {                                                      │
│    "message": "生成一张新海诚风格的图片",                 │
│    "agent_type": "planner_supervisor"                   │
│  }                                                      │
├─────────────────────────────────────────────────────────┤
│  [发送 ▼] ← 点击下拉选择 "SSE"                          │
└─────────────────────────────────────────────────────────┘
```

### 查看 SSE 响应

```
┌─────────────────────────────────────────────────────────┐
│  SSE Events                                             │
├─────────────────────────────────────────────────────────┤
│  ● event: start                                         │
│    data: {"event":"start","thread_id":"xxx"}            │
│  ─────────────────────────────────────────────────────  │
│  ● event: token                                         │
│    data: {"event":"token","content":"好的"}             │
│  ─────────────────────────────────────────────────────  │
│  ● event: token                                         │
│    data: {"event":"token","content":"，我来帮您"}       │
│  ─────────────────────────────────────────────────────  │
│  ● event: tool_start                                    │
│    data: {"event":"tool_start","tool_name":"image..."}  │
│  ─────────────────────────────────────────────────────  │
│  ● event: end                                           │
│    data: {"event":"end","thread_id":"xxx"}              │
└─────────────────────────────────────────────────────────┘
```

---

> 💡 **提示**: 如果 Apifox 的 SSE 功能不够直观，也可以使用浏览器开发者工具的 Network 面板查看 EventStream 响应。

