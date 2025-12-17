# LoopSkill Agent API 接口文档

> 版本: 1.0.0  
> 基础路径: `http://localhost:8000`  
> 交互式文档: `/api/docs` (Swagger UI) | `/api/redoc` (ReDoc)

---

## 目录

- [快速开始](#快速开始)
- [通用说明](#通用说明)
- [接口列表](#接口列表)
  - [系统接口](#系统接口)
  - [对话接口](#对话接口)
  - [任务接口](#任务接口)
  - [配置接口](#配置接口)
  - [历史记录接口](#历史记录接口)
- [数据模型](#数据模型)
- [错误码说明](#错误码说明)
- [前端集成示例](#前端集成示例)

---

## 快速开始

### 启动服务

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 API 服务
python -m service.api

# 或使用 uvicorn (支持热重载)
uvicorn service.api:app --host 0.0.0.0 --port 8000 --reload
```

### 快速测试

```bash
# 健康检查
curl http://localhost:8000/api/health

# 发送对话
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我生成一张新海诚风格的夕阳图片"}'
```

---

## 通用说明

### 请求格式

- **Content-Type**: `application/json`
- **字符编码**: UTF-8

### 响应格式

所有接口返回 JSON 格式，包含以下通用字段：

```json
{
  "success": true,
  "message": "操作成功"
}
```

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 500 | 服务器内部错误 |

---

## 接口列表

### 系统接口

#### 健康检查

检查服务运行状态和各 Agent 可用性。

- **URL**: `/api/health`
- **Method**: `GET`
- **Tags**: 系统

**响应示例**

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

**状态说明**

| status | 说明 |
|--------|------|
| `healthy` | 所有 Agent 正常 |
| `degraded` | 部分 Agent 不可用 |
| `unhealthy` | 所有 Agent 不可用 |

---

### 对话接口

#### 发送对话消息

向 Agent 发送消息并获取回复。

- **URL**: `/api/chat`
- **Method**: `POST`
- **Tags**: 对话

**请求参数**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| message | string | ✅ | - | 用户消息内容 |
| thread_id | string | ❌ | null | 对话线程ID，用于追踪上下文 |
| agent_type | string | ❌ | `planner_supervisor` | Agent 类型: `react` / `planner_supervisor` |
| deep_thinking | boolean | ❌ | false | 是否启用深度思考模式 |
| style_preset | string | ❌ | null | 风格预设 (如: `your_name`) |

**请求示例**

```json
{
  "message": "帮我生成一张新海诚风格的夕阳场景图片",
  "agent_type": "planner_supervisor",
  "deep_thinking": false,
  "style_preset": "your_name"
}
```

**响应示例**

```json
{
  "success": true,
  "message": "对话完成",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "answer": "我已经为您创建了一张新海诚风格的夕阳场景图片...",
  "suggestions": [
    "调整图片的色调更暖一些",
    "在画面中添加一对情侣的剪影",
    "将这张图片转换为视频"
  ],
  "plan": {
    "title": "生成新海诚风格夕阳图片",
    "thought": "用户希望生成一张新海诚风格的夕阳场景图片，需要使用图片生成工具，并确保风格符合新海诚动画的特点：色彩鲜艳、光影效果突出、云层细腻。",
    "total_steps": 1,
    "steps": [
      {
        "index": 0,
        "executor": "image_executor",
        "title": "生成夕阳场景图片",
        "description": "使用 Banana Pro 生成新海诚风格的夕阳场景，要求色彩饱满、光影层次分明、云层细腻",
        "depends_on": []
      }
    ]
  },
  "execution": {
    "current_step_index": 1,
    "completed_steps": 1,
    "step_results": [
      {
        "step_index": 0,
        "executor": "image_executor",
        "status": "success",
        "task_id": "task_abc123",
        "result_url": "https://example.com/image.png",
        "summary": "图片生成成功，任务ID: task_abc123"
      }
    ]
  },
  "task_ids": ["task_abc123"],
  "media_urls": ["https://example.com/image.png"]
}
```

---

#### 流式对话 (SSE)

使用 Server-Sent Events 实现流式输出。

- **URL**: `/api/chat/stream`
- **Method**: `POST`
- **Tags**: 对话
- **Content-Type**: `text/event-stream`

**请求参数**

与 `/api/chat` 相同。

**SSE 事件类型**

| event | 说明 | data 示例 |
|-------|------|-----------|
| `start` | 对话开始 | `{"event": "start", "thread_id": "xxx"}` |
| `token` | LLM 输出 token | `{"event": "token", "content": "你好"}` |
| `tool_start` | 工具开始执行 | `{"event": "tool_start", "tool_name": "image_edit"}` |
| `tool_end` | 工具执行完成 | `{"event": "tool_end", "tool_name": "image_edit", "output": "..."}` |
| `end` | 对话结束 | `{"event": "end", "thread_id": "xxx"}` |
| `error` | 发生错误 | `{"event": "error", "error": "错误信息"}` |

**前端接入示例 (JavaScript)**

```javascript
const eventSource = new EventSource('/api/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: '你好' })
});

// 使用 fetch + ReadableStream 更灵活
async function streamChat(message) {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  });
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const text = decoder.decode(value);
    const lines = text.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        console.log('Event:', data.event, data);
      }
    }
  }
}
```

---

### 任务接口

#### 查询任务状态 (POST)

通过请求体查询任务状态。

- **URL**: `/api/task/status`
- **Method**: `POST`
- **Tags**: 任务

**请求参数**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| task_id | string | ✅ | - | 任务ID |
| task_type | string | ❌ | `image` | 任务类型: `image` / `video` |

**请求示例**

```json
{
  "task_id": "task_abc123",
  "task_type": "image"
}
```

**响应示例**

```json
{
  "success": true,
  "message": "查询成功",
  "task_id": "task_abc123",
  "status": "completed",
  "progress": 100,
  "result_url": "https://example.com/result.png",
  "error_message": null
}
```

---

#### 查询任务状态 (GET)

通过路径参数查询任务状态。

- **URL**: `/api/task/{task_id}`
- **Method**: `GET`
- **Tags**: 任务

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务ID |

**查询参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| task_type | string | `image` | 任务类型 |

**请求示例**

```
GET /api/task/task_abc123?task_type=image
```

**任务状态说明**

| status | 说明 |
|--------|------|
| `pending` | 任务排队中 |
| `processing` | 任务处理中 |
| `completed` | 任务已完成 |
| `failed` | 任务失败 |

---

### 配置接口

#### 获取全局配置

获取当前的全局配置参数。

- **URL**: `/api/config`
- **Method**: `GET`
- **Tags**: 配置

**响应示例**

```json
{
  "success": true,
  "message": "获取成功",
  "config": {
    "style": "your_name",
    "resolution": "1024x1024",
    "aspect_ratio": "1:1"
  }
}
```

---

#### 更新全局配置

更新全局配置参数。

- **URL**: `/api/config`
- **Method**: `PUT`
- **Tags**: 配置

**请求参数**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| style | string | ❌ | 默认风格 |
| resolution | string | ❌ | 默认分辨率 (如: `1024x1024`) |
| aspect_ratio | string | ❌ | 默认宽高比 (如: `16:9`) |

**请求示例**

```json
{
  "style": "ghibli",
  "resolution": "1920x1080",
  "aspect_ratio": "16:9"
}
```

**响应示例**

```json
{
  "success": true,
  "message": "配置更新成功",
  "config": {
    "style": "ghibli",
    "resolution": "1920x1080",
    "aspect_ratio": "16:9"
  }
}
```

---

### 历史记录接口

#### 获取对话历史列表

分页获取对话历史记录。

- **URL**: `/api/history`
- **Method**: `GET`
- **Tags**: 历史

**查询参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 (从 1 开始) |
| page_size | int | 20 | 每页数量 (1-100) |

**响应示例**

```json
{
  "success": true,
  "message": "获取成功",
  "conversations": [
    {
      "thread_id": "550e8400-e29b-41d4-a716-446655440000",
      "messages": [
        {"role": "user", "content": "帮我生成一张图片"},
        {"role": "assistant", "content": "好的，我来帮您生成..."}
      ],
      "created_at": "2024-12-17T10:30:00Z",
      "updated_at": "2024-12-17T10:35:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

---

#### 删除对话历史

删除指定的对话历史记录。

- **URL**: `/api/history/{thread_id}`
- **Method**: `DELETE`
- **Tags**: 历史

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| thread_id | string | 对话线程ID |

**响应示例**

```json
{
  "success": true,
  "message": "对话 550e8400-e29b-41d4-a716-446655440000 已删除"
}
```

---

## 数据模型

### ChatMessage

单条消息对象。

```typescript
interface ChatMessage {
  role: "user" | "assistant" | "system";  // 消息角色
  content: string;                         // 消息内容
}
```

### ChatRequest

对话请求对象。

```typescript
interface ChatRequest {
  message: string;                         // 用户消息内容
  thread_id?: string;                      // 对话线程ID
  agent_type?: "react" | "planner_supervisor";  // Agent 类型
  deep_thinking?: boolean;                 // 深度思考模式
  style_preset?: string;                   // 风格预设
}
```

### ChatResponse

对话响应对象，包含完整的执行过程信息。

```typescript
interface ChatResponse {
  success: boolean;        // 请求是否成功
  message: string;         // 响应消息
  thread_id: string;       // 对话线程ID
  answer: string;          // Agent 最终回复内容 (来自 Reporter)
  suggestions: string[];   // 后续操作建议
  
  // ============ Planner 信息 ============
  plan: PlanInfo | null;   // 执行计划详情
  
  // ============ Executor 信息 ============
  execution: ExecutionInfo | null;  // 执行过程详情
  
  // ============ 任务汇总 ============
  task_ids: string[];      // 生成的任务ID列表
  media_urls: string[];    // 生成的媒体URL列表
}

// Planner 生成的执行计划
interface PlanInfo {
  title: string;           // 任务标题
  thought: string;         // Planner 对任务的理解和分析
  total_steps: number;     // 总步骤数
  steps: PlanStepInfo[];   // 执行步骤列表
}

// 单个执行步骤
interface PlanStepInfo {
  index: number;           // 步骤索引 (从 0 开始)
  executor: string;        // 执行者: image_executor, video_executor, general_executor
  title: string;           // 步骤标题
  description: string;     // 步骤描述
  depends_on: number[];    // 依赖的步骤索引
}

// 执行过程信息
interface ExecutionInfo {
  current_step_index: number;     // 当前执行到的步骤索引
  completed_steps: number;        // 已完成步骤数
  step_results: StepResultInfo[]; // 各步骤执行结果
}

// 单步执行结果
interface StepResultInfo {
  step_index: number;      // 步骤索引
  executor: string;        // 执行者名称
  status: "success" | "failed" | "pending";  // 执行状态
  task_id: string | null;  // 任务ID (异步任务)
  result_url: string | null; // 结果URL
  summary: string;         // 执行摘要
}
```

### TaskStatusResponse

任务状态响应对象。

```typescript
interface TaskStatusResponse {
  success: boolean;
  message: string;
  task_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress?: number;       // 进度百分比 (0-100)
  result_url?: string;     // 结果URL
  error_message?: string;  // 错误信息
}
```

---

## 错误码说明

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| INVALID_REQUEST | 400 | 请求参数无效 |
| AGENT_ERROR | 500 | Agent 执行错误 |
| TASK_NOT_FOUND | 404 | 任务不存在 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |

**错误响应格式**

```json
{
  "success": false,
  "message": "错误描述",
  "error_code": "AGENT_ERROR",
  "detail": "详细错误信息..."
}
```

---

## 前端集成示例

### React + TypeScript 示例

```typescript
// api.ts
const API_BASE = 'http://localhost:8000';

interface ChatRequest {
  message: string;
  thread_id?: string;
  agent_type?: 'react' | 'planner_supervisor';
  deep_thinking?: boolean;
}

interface ChatResponse {
  success: boolean;
  thread_id: string;
  answer: string;
  suggestions: string[];
  task_ids: string[];
  media_urls: string[];
}

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
}

// 流式对话
export async function* streamChat(request: ChatRequest) {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  
  const reader = response.body?.getReader();
  if (!reader) return;
  
  const decoder = new TextDecoder();
  let buffer = '';
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        yield JSON.parse(line.slice(6));
      }
    }
  }
}
```

### Vue 3 + Composition API 示例

```typescript
// useChat.ts
import { ref } from 'vue';

export function useChat() {
  const loading = ref(false);
  const answer = ref('');
  const suggestions = ref<string[]>([]);
  
  async function sendMessage(message: string) {
    loading.value = true;
    answer.value = '';
    
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      
      const data = await response.json();
      answer.value = data.answer;
      suggestions.value = data.suggestions;
    } finally {
      loading.value = false;
    }
  }
  
  return { loading, answer, suggestions, sendMessage };
}
```

---

## 更新日志

### v1.0.0 (2024-12-17)

- ✨ 初始版本发布
- 📝 支持对话接口 (普通 + 流式)
- 🔍 支持任务状态查询
- ⚙️ 支持全局配置管理
- 📚 支持对话历史管理

