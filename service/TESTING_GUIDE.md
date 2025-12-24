# LoopSkill Agent 测试指南

## 快速开始

### 1. 启动服务

```bash
# 终端 1: 启动 LangGraph 服务
langgraph dev

# 终端 2: 启动 FastAPI 服务 (可选，如果需要通过 HTTP 调用)
cd service
uvicorn api:app --reload --port 8000
```

### 2. 验证服务

```bash
# 检查 LangGraph 服务
curl http://localhost:2024/ok

# 检查 FastAPI 服务
curl http://localhost:8000/api/docs
```

---

## 测试方法

### 方法 1: 使用 curl 测试 SSE

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}' \
  --no-buffer
```

### 方法 2: 使用 Python 测试

```python
import httpx

async def test_chat():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/api/chat/stream",
            json={"message": "帮我生成一张图片"},
            timeout=60.0
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    print(data)

import asyncio
asyncio.run(test_chat())
```

### 方法 3: 使用 JavaScript 测试

```javascript
// 使用 fetch + EventSource (需要 eventsource 库)
const response = await fetch('http://localhost:8000/api/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: '帮我生成一张图片' })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  console.log(decoder.decode(value));
}
```

---

## 测试用例

### 1. 简单问候 (Coordinator 直接回复)

```json
{"message": "你好"}
```

**预期响应流程**:
```
start → delta → end
```

**预期 delta 内容**: 包含问候语

---

### 2. 图片生成 (完整流程)

```json
{"message": "帮我生成一张赛博朋克风格的城市夜景图片"}
```

**预期响应流程**:
```
start → thought → tool_name+tool_result → delta → end
```

**预期字段**:
- `thought`: 包含 "Thought:" 和步骤列表
- `tool_name`: `text_to_image`
- `tool_result`: 包含 `task_id`
- `delta`: Reporter 的报告内容

---

### 3. 视频生成

```json
{"message": "帮我生成一段海边日落的视频"}
```

**预期 tool_name**: `text_to_video`

---

### 4. 多轮对话

```json
// 第一轮
{"message": "帮我生成一张图片"}

// 第二轮 (使用返回的 thread_id)
{"message": "把图片改成黑白的", "thread_id": "xxx"}
```

## 响应示例

### 简单问题

```
event: message
data: {"type": "start", "thread_id": "abc123"}

event: message
data: {"delta": "你好！我是 AI 创作助手，很高兴为你服务！"}

event: message
data: {"type": "end", "thread_id": "abc123"}
```

### 复杂任务 (逐字流式)

```
event: message
data: {"type": "start", "thread_id": "abc123"}

# thought 逐字流式
event: message
data: {"thought": "T"}
event: message
data: {"thought": "h"}
event: message
data: {"thought": "o"}
...
event: message
data: {"thought": "\n"}
event: message
data: {"thought": "1"}
event: message
data: {"thought": "."}
...

# 工具结果一次性返回
event: message
data: {"tool_name": "text_to_image", "tool_result": "{\"step_index\": 0, \"status\": \"success\", \"task_id\": \"task_xxx\", \"summary\": \"执行了一个工具调用\"}"}

# delta 逐字流式 (Reporter)
event: message
data: {"delta": "太"}
event: message
data: {"delta": "棒"}
event: message
data: {"delta": "了"}
...

event: message
data: {"type": "end", "thread_id": "abc123"}
```

### 环境变量配置

```bash
# 控制逐字输出延迟 (秒)，默认 0.02
STREAM_DELAY=0.02

# 设为 0 则无延迟
STREAM_DELAY=0
```

