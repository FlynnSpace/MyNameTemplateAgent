# 🎬 MyNameChat - AI 视频/图像连续创作助手

基于 **LangGraph** 构建的智能创作助手，专为《你的名字》(君の名は) 续集创作设计。本项目采用状态机架构，支持**连续修图**、**自动上下文加载**以及**多模态生成**（图像/视频）。

## ✨ 核心特性

- **🧠 智能状态管理**
  - **自动加载 (Auto-Load)**：无需重复上传，Agent 会自动检测并加载上一轮生成的图片作为新任务的参考素材。
  - **连续创作**：支持基于上一轮结果进行 "Retry"（重绘）或 "Edit"（修图）。
  - **全局配置**：持久化风格、分辨率配置。

- **🎨 高级图像引擎 (PPIO / Banana Pro)**
  - 集成 **PPIO Nano Banana Pro** 模型，支持高质量图像生成与局部重绘。
  - 采用 **异步 + 数据库 (Supabase)** 架构，稳定追踪耗时任务状态。
  - 支持多种画幅比例 (16:9, 9:16, 1:1 等) 和分辨率 (1K/2K/4K)。

- **🎬 视频生成 (Sora-2)**
  - **Text-to-Video**：基于文本描述生成 10-15秒 视频。
  - **Image-to-Video**：支持**首帧驱动**，将生成的图像转化为动态视频。

- **🤖 模型驱动**
  - 核心决策模型：**GPT-5-nano** (OpenAI)。
  - 严格的 Prompt 工程，确保工具调用的准确性和参数一致性。

## 🏗️ 技术栈

- **Orchestration**: [LangGraph](https://langchain-ai.github.io/langgraph/) (StateGraph 状态机)
- **Framework**: [LangChain](https://python.langchain.com/)
- **LLM**: OpenAI GPT-5-nano
- **Image Generation**: PPIO (Banana Pro) / KIE (Seedream v4)
- **Video Generation**: KIE (Sora-2)
- **Database**: Supabase (用于 PPIO 任务状态持久化)

## 📋 前置要求

确保拥有以下服务的 API Key：
- **OpenAI**: 用于驱动 Agent 对话 (`gpt-5-nano`)
- **KIE.AI**: 用于视频生成和部分图像服务
- **PPIO / Gemini**: 用于 Banana Pro 图像生成
- **Supabase**: 用于任务状态存储

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
在项目根目录创建 `.env` 文件，填入以下配置：

```env
# LLM
OPENAI_API_KEY=sk-your-openai-api-key

# KIE Services (Video/Image)
KIE_API_KEY=your-kie-api-key

# PPIO / Gemini Services (Main Image Engine)
GEMINI_API_KEY=your-ppio-api-key

# Supabase (Task Status DB)
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

### 4. 运行应用

**命令行交互模式（推荐）：**
```bash
python MyNameTemplate.py
```
*注：原 `example.py` 已重构为 `MyNameTemplate.py`*

## 📚 项目结构

```
MyNameChat/
├── MyNameTemplate.py    # [核心] LangGraph 状态机定义、主程序入口
├── KIE_tools.py         # [工具] KIE & PPIO API 封装、Supabase 交互
├── tool_prompts.py      # [配置] 系统提示词 (System Prompt) 与工具描述
├── logger_util.py       # [工具] 日志模块
├── langgraph.json       # LangGraph 部署配置
└── requirements.txt     # Python 依赖
```

## 📝 可用工具 (Agent Tools)

Agent 会根据对话上下文自动选择以下工具：

| 工具名称 | 功能描述 | 关键参数 |
|---------|----------|----------|
| `image_edit_by_ppio_banana_pro_create_task` | **[主力]** 图像生成/编辑 | `prompt`, `image_urls`, `seed` |
| `text_to_video_by_kie_sora2_create_task` | 文本生成视频 | `prompt`, `n_frames` |
| `first_frame_to_video_by_kie_sora2_create_task` | 图片转视频 (首帧) | `image_urls`, `prompt` |
| `remove_watermark_from_image_by_kie_seedream_v4_create_task` | 去除水印 | `image_urls` |
| `get_task_status` | 统一任务状态查询 (支持 KIE & PPIO) | `task_id` |

*(注：`text_to_image_by_seedream` 目前已禁用，统一使用 PPIO 接口)*

## 🔄 工作流逻辑

1. **Initial Prep**: 解析用户输入 (JSON/Text)，检查是否有上一轮任务。
2. **Auto-Load Check**: 如果用户未提供参考图，自动检查 `last_task_id`，尝试从 Supabase/KIE 拉取上一轮结果。
3. **Agent Reasoning**: GPT-5-nano 决定是否调用工具。
4. **Tool Execution**: 
   - **PPIO**: 异步提交 -> 写入 DB -> 后台线程轮询 API -> 更新 DB。
   - **KIE**: 同步/回调提交。
5. **Recorder**: 记录本次生成的 `task_id` 和配置，为下一轮 "Retry" 做准备。

## 🤝 贡献
欢迎提交 Pull Request 或 Issue。

## 📄 许可证
MIT License
