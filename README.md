# 🎬 MyNameChat - AI 视频/图像生成助手

基于 LangGraph 构建的 AI 助手，专为《你的名字》(君の名は) 续集创作设计，提供图像生成、编辑和视频生成功能。

## ✨ 功能特性

- 🖼️ **图像生成**：基于 Seedream-v4 模型生成高质量图像
- 🎨 **图像编辑**：根据参考图和提示词编辑图像
- 🎬 **视频生成**：
  - 文本转视频 (Text-to-Video)
  - 首帧转视频 (First-frame-to-Video)
- 💬 **智能对话**：AI 助手引导创作流程
- 🔄 **Token 级流式输出**：实时查看 AI 响应

## 🏗️ 技术栈

- **LangGraph**: 工作流编排
- **LangChain**: AI 应用框架
- **OpenAI GPT**: 对话模型
- **KIE.AI API**: 图像/视频生成服务

## 📋 前置要求

- Python 3.11+
- OpenAI API Key
- KIE.AI API Key

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/MyNameChat.git
cd MyNameChat
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

创建 `.env` 文件：

```env
OPENAI_API_KEY=sk-your-openai-api-key-here
KIE_API_KEY=your-kie-api-key-here
```

### 4. 运行应用

**方式 1：命令行对话（推荐）**
```bash
python example.py
```

**方式 2：启动 API 服务**
```bash
langgraph dev
```

访问：
- API 文档: http://localhost:2024/docs
- LangSmith Studio: https://smith.langchain.com/studio/?baseUrl=http://localhost:2024

## 📚 项目结构

```
MyNameChat/
├── example.py              # 主程序 - 包含 LangGraph 工作流和对话界面
├── KIE_tools.py           # KIE.AI API 工具封装
├── langgraph.json         # LangGraph 配置文件
├── requirements.txt       # Python 依赖
├── KIE API doc.md        # KIE API 文档
├── .env                   # 环境变量（需自己创建）
└── README.md             # 项目说明
```

## 🎯 使用示例

### 对话示例

```
你: 帮我生成一张东京夜景的图片

AI: 好的，我将帮你生成一张东京夜景的图片。

[🔧 调用工具: text_to_image_by_seedream_v4_model_create_task]
[✓ 工具执行完成]

AI: 图片生成任务已创建，任务ID: task_12345678
我现在帮你查询生成状态...

[🔧 调用工具: get_task_status]
[✓ 工具执行完成]

AI: 图片已生成完成！
图片链接: https://...
```

### API 调用示例

```python
import requests

response = requests.post(
    "http://localhost:2024/runs/stream",
    json={
        "assistant_id": "my_name_chat_agent",
        "input": {
            "messages": [
                {"role": "user", "content": "生成一张猫的图片"}
            ]
        }
    }
)

for line in response.iter_lines():
    print(line.decode())
```

## 🔧 配置说明

### langgraph.json

```json
{
  "dependencies": ["."],
  "graphs": {
    "my_name_chat_agent": "./example.py:app"
  },
  "env": ".env",
  "python_version": "3.11",
  "host": "0.0.0.0",
  "port": 2024
}
```

### 工作流程

```
用户输入
  ↓
our_agent (GPT-4 决策)
  ↓
需要调用工具?
  ├─ 是 → tools (执行工具) → our_agent
  └─ 否 → END (返回结果)
```

## 🌐 部署

### 本地开发

```bash
langgraph dev
```

### 部署到 LangGraph Cloud

```bash
langgraph deploy
```

## 📝 可用工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `text_to_image_by_seedream_v4_model_create_task` | 文本生成图像 | `prompt` |
| `image_to_image_by_seedream_v4_edit_model_create_task` | 编辑图像 | `prompt`, `image_url` |
| `text_to_video_by_sora2_model_create_task` | 文本生成视频 | `prompt` |
| `first_frame_to_video_by_sora2_model_create_task` | 首帧生成视频 | `prompt`, `image_url` |
| `get_task_status` | 查询任务状态 | `task_id` |

## ⚙️ 高级配置

### 修改默认参数

在 `KIE_tools.py` 中修改：

```python
# 图像生成默认配置
DEFAULT_IMAGE_SIZE = "square_hd"      # 图像尺寸
DEFAULT_IMAGE_RESOLUTION = "1K"       # 分辨率
DEFAULT_MAX_IMAGES = 1                # 生成数量

# 视频生成默认配置
DEFAULT_ASPECT_RATIO = "landscape"    # 宽高比
DEFAULT_N_FRAMES = "10"              # 帧数
```

### 更换模型

在 `example.py` 中修改：

```python
model = ChatOpenAI(model="gpt-4").bind_tools(tools)
```

## 🐛 故障排查

### 问题：模块导入错误
```bash
pip install -r requirements.txt
```

### 问题：API Key 无效
检查 `.env` 文件中的 API Key 是否正确配置。

### 问题：端口被占用
修改 `langgraph.json` 中的 `port` 配置。

### 问题：无法访问 LangSmith Studio
使用 Swagger API 文档代替：`http://localhost:2024/docs`

## 📖 相关文档

- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [LangChain 文档](https://python.langchain.com/)
- [KIE.AI API](https://kie.ai/)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 👨‍💻 作者

你的名字

## 🙏 致谢

- LangChain 团队
- KIE.AI 团队
- OpenAI

---

**⚠️ 注意**：本项目仅供学习和研究使用。使用 API 服务时请遵守相关服务条款。

