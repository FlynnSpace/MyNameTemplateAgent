# LoopSkill Agent API 文档

## 概述

本 API 提供 AI 视频/图像创作助手的流式对话接口。

- **基础路径**: `http://localhost:8000`
- **API 文档**: `/api/docs` (Swagger UI)
- **依赖服务**: 需要先启动 `langgraph dev` (端口 2024)

---

## 接口列表

### POST /api/chat/stream

流式对话接口 (SSE)

#### 请求

```json
{
  "message": "帮我生成一张赛博朋克风格的城市图片",
  "thread_id": "可选，用于多轮对话",
  "agent_type": "planner_supervisor",
  "deep_thinking": false
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | ✅ | 用户消息内容 |
| `thread_id` | string | ❌ | Thread ID，用于多轮对话上下文 |
| `agent_type` | string | ❌ | Agent 类型: `react` 或 `planner_supervisor` (默认) |
| `deep_thinking` | boolean | ❌ | 是否启用深度思考模式 (默认 false) |

#### 响应 (SSE 流)

所有事件的 `event` 字段统一为 `"message"`，通过 `data` 内部字段区分类型。

##### 1. 开始事件

```json
{"type": "start", "thread_id": "abc123"}
```

##### 2. 文本回复 (Coordinator 或 Reporter) - 逐字流式

```json
{"delta": "你"}
{"delta": "好"}
{"delta": "！"}
...
```

##### 3. 思考过程 (Planner) - 逐字流式

```json
{"thought": "T"}
{"thought": "h"}
{"thought": "o"}
{"thought": "u"}
{"thought": "g"}
{"thought": "h"}
{"thought": "t"}
{"thought": ":"}
...
```

##### 4. 工具执行结果 (Executor)

```json
{
  "tool_name": "text_to_image",
  "tool_result": "{\"step_index\": 0, \"status\": \"success\", \"task_id\": \"xxx\", \"summary\": \"...\"}"
}
```

##### 5. 结束事件

```json
{"type": "end", "thread_id": "abc123"}
```

##### 6. 错误事件

```json
{"type": "error", "error": "错误信息"}
```

---

## 对话流程

### 简单问题

```
用户: "你好"
↓
start → delta (Coordinator 直接回复) → end
```

### 复杂任务

```
用户: "帮我生成一张图片"
↓
start → thought (Planner 思考) → tool_name+tool_result (Executor 执行) → delta (Reporter 报告) → end
```

---

## 字段说明

| 字段 | 来源 | 处理方式 |
|------|------|----------|
| `delta` | Coordinator / Reporter | **逐字累加**拼接显示 (打字机效果) |
| `thought` | Planner | **逐字累加**显示在思考区域 |
| `tool_name` + `tool_result` | Executor | 渲染工具卡片 (一次性) |
| `type: start` | 系统 | 保存 thread_id |
| `type: end` | 系统 | 对话结束 |
| `type: error` | 系统 | 显示错误 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STREAM_DELAY` | `0.02` | 逐字输出延迟 (秒)，设为 `0` 则无延迟 |
| `LANGGRAPH_URL` | `http://localhost:2024` | LangGraph 服务地址 |

---

## 前端示例代码

```javascript
const eventSource = new EventSource('/api/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: '帮我生成一张图片' })
});

let fullContent = '';
let thinkingContent = '';
let threadId = '';

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.delta) {
    // 文本回复 → 累加拼接
    fullContent += data.delta;
    updateTextArea(fullContent);
  } 
  else if (data.thought) {
    // 思考过程 → 显示在思考区域
    thinkingContent += data.thought;
    showThinking(thinkingContent);
  } 
  else if (data.tool_name) {
    // 工具结果 → 渲染卡片
    const result = JSON.parse(data.tool_result);
    renderToolCard(data.tool_name, result);
  }
  else if (data.type === 'start') {
    threadId = data.thread_id;
  }
  else if (data.type === 'end') {
    eventSource.close();
  }
  else if (data.type === 'error') {
    showError(data.error);
    eventSource.close();
  }
};
```

---

## 工具名称列表

| tool_name | 说明 |
|-----------|------|
| `text_to_image` | 文字生成图片 |
| `image_edit` | 图片编辑 |
| `image_edit_banana_pro` | Banana Pro 图片编辑 |
| `remove_watermark` | 去除水印 |
| `text_to_video` | 文字生成视频 |
| `first_frame_to_video` | 首帧生成视频 |
| `get_task_status` | 查询任务状态 |

