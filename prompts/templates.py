"""
集中存放所有 System Prompt (正文、建议等)
支持:
1. Python 字符串常量 (现有方式)
2. Markdown 模板文件 (.md) - 用于 Planner/Supervisor 等复杂提示词

对标 LangManus 实现：
- apply_prompt_template 返回消息列表 (包含 system prompt + state messages)
- RESPONSE_FORMAT 用于格式化执行者输出
- TEAM_MEMBERS 从 state 中动态获取，支持运行时配置
"""

import os
import re
from datetime import datetime
from typing import Any

from langchain_core.prompts import PromptTemplate

from state.schemas import (
    AgentState, 
    TEAM_MEMBERS as DEFAULT_TEAM_MEMBERS,
    DEFAULT_EXECUTOR_TOOLS,
)


# ============================================================
# 对标 LangManus: RESPONSE_FORMAT
# ============================================================

RESPONSE_FORMAT = "Response from {}:\n\n<response>\n{}\n</response>\n\n*请执行下一步。*"


# ============================================================
# Markdown 模板加载工具函数 (对标 LangManus)
# ============================================================

def get_prompt_template(prompt_name: str) -> str:
    """
    从 prompts/ 目录加载 .md 模板文件 (对标 LangManus)
    
    Args:
        prompt_name: 模板名称 (不含 .md 后缀)
        
    Returns:
        处理后的模板字符串，使用 {VAR} 格式占位符
        
    对标 LangManus:
    - 转义花括号 { } → {{ }}
    - 替换 <<VAR>> → {VAR}
    """
    template = open(os.path.join(os.path.dirname(__file__), f"{prompt_name}.md"), encoding="utf-8").read()
    # 对标 LangManus: 转义花括号，替换 <<VAR>> 为 {VAR}
    template = template.replace("{", "{{").replace("}", "}}")
    template = re.sub(r"<<([^>>]+)>>", r"{\1}", template)
    return template


def apply_prompt_template(prompt_name: str, state: AgentState) -> list:
    """
    加载并应用提示词模板 (完全对标 LangManus)
    
    Args:
        prompt_name: 模板名称 (不含 .md 后缀)
        state: Agent 状态，包含 messages 和其他变量
        
    Returns:
        消息列表 [{"role": "system", "content": ...}, ...messages...]
        
    对标 LangManus:
    - 使用 PromptTemplate.format() 进行变量替换
    - 返回格式: [system_message] + state["messages"]
    - TEAM_MEMBERS 从 state 中动态获取 (支持动态工具加载)
    - EXECUTOR_TOOLS 支持最小颗粒度的工具配置
    """
    # 从 state 获取动态配置，如果没有则使用默认值
    team_members = state.get("TEAM_MEMBERS", DEFAULT_TEAM_MEMBERS)
    executor_tools = state.get("EXECUTOR_TOOLS", DEFAULT_EXECUTOR_TOOLS)
    
    # 准备模板变量 (对标 LangManus: 简洁)
    template_vars = {
        # 动态配置 (从 state 获取，支持运行时配置)
        "TEAM_MEMBERS": ", ".join(team_members) if isinstance(team_members, list) else str(team_members),
        
        # Reporter 模板变量
        "STEP_RESULTS": format_step_results(state.get("step_results")),
    }
    
    # 对标 LangManus: 使用 PromptTemplate.format()
    system_prompt = PromptTemplate(
        input_variables=["CURRENT_TIME"],
        template=get_prompt_template(prompt_name),
    ).format(
        CURRENT_TIME=datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **template_vars
    )
    
    # 返回消息列表 (对标 LangManus)
    return [{"role": "system", "content": system_prompt}] + list(state.get("messages", []))


def get_tools_for_executor(
    executor_name: str,
    executor_tools: dict[str, list[str]] | None = None
) -> list[str]:
    """
    获取指定执行者的可用工具列表
    
    Args:
        executor_name: 执行者名称
        executor_tools: 工具配置，如果为 None 则使用默认配置
        
    Returns:
        工具名称列表
        
    用法:
        # 使用默认配置
        tools = get_tools_for_executor("image_executor")
        
        # 使用自定义配置
        custom_tools = {"image_executor": ["text_to_image"]}
        tools = get_tools_for_executor("image_executor", custom_tools)
    """
    if executor_tools is None:
        executor_tools = DEFAULT_EXECUTOR_TOOLS
    
    return executor_tools.get(executor_name, [])


def apply_prompt_template_str(prompt_name: str, variables: dict[str, Any] | None = None) -> str:
    """
    加载并应用变量到模板 (返回字符串，兼容旧用法)
    
    Args:
        prompt_name: 模板名称 (不含 .md 后缀)
        variables: 要替换的变量字典
        
    Returns:
        替换变量后的完整提示词字符串
    """
    template_path = os.path.join(os.path.dirname(__file__), f"{prompt_name}.md")
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Prompt template not found: {template_path}")
    
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    
    # 默认变量
    default_vars = {
        "CURRENT_TIME": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    # 合并变量 (用户变量优先)
    all_vars = {**default_vars, **(variables or {})}
    
    # 替换 <<VAR>> 格式的占位符
    for key, value in all_vars.items():
        placeholder = f"<<{key}>>"
        template = template.replace(placeholder, str(value))
    
    return template


def format_step_results(step_results: list[dict] | None) -> str:
    """
    格式化步骤执行结果，用于 Reporter 模板
    
    Args:
        step_results: 步骤执行结果列表
        
    Returns:
        格式化的结果字符串
    """
    if not step_results:
        return "暂无执行结果"
    
    lines = []
    for result in step_results:
        status = result.get("status", "unknown")
        status_text = "成功" if status == "success" else "失败" if status == "failed" else "处理中"
        
        lines.append(f"### 步骤 {result.get('step_index', '?')}: {result.get('executor', 'unknown')}")
        lines.append(f"- **状态**: {status_text}")
        
        if result.get("task_id"):
            lines.append(f"- **任务ID**: {result.get('task_id')}")
        if result.get("result_url"):
            lines.append(f"- **结果链接**: {result.get('result_url')}")
        if result.get("summary"):
            lines.append(f"- **摘要**: {result.get('summary')}")
        
        lines.append("")
    
    return "\n".join(lines)


# ============================================================
# 便捷函数：为各角色生成完整提示词字符串 (兼容旧用法)
# ============================================================

def get_planner_prompt(team_members: list[str] | None = None) -> str:
    """
    获取 Planner 的完整提示词 (字符串格式)
    
    Args:
        team_members: 团队成员列表，默认为标准执行者
        
    Returns:
        完整的 Planner 提示词
    """
    if team_members is None:
        team_members = ["image_executor", "video_executor", "general_executor", "reporter"]
    
    return apply_prompt_template_str("planner", {
        "TEAM_MEMBERS": ", ".join(team_members)
    })


def get_supervisor_prompt(team_members: list[str] | None = None) -> str:
    """
    获取 Supervisor 的完整提示词 (字符串格式)
    
    Args:
        team_members: 团队成员列表
        
    Returns:
        完整的 Supervisor 提示词
        
    Note:
        Supervisor 从 messages 中获取计划和执行历史，不需要额外参数
    """
    if team_members is None:
        team_members = ["image_executor", "video_executor", "general_executor", "reporter"]
    
    return apply_prompt_template_str("supervisor", {
        "TEAM_MEMBERS": ", ".join(team_members),
    })


def get_coordinator_prompt() -> str:
    """获取 Coordinator 的完整提示词 (字符串格式)"""
    return apply_prompt_template_str("coordinator", {})


def get_reporter_prompt(step_results: list[dict] | None = None) -> str:
    """
    获取 Reporter 的完整提示词 (字符串格式)
    
    Args:
        step_results: 已执行步骤的结果
        
    Returns:
        完整的 Reporter 提示词
    """
    return apply_prompt_template_str("reporter", {
        "STEP_RESULTS": format_step_results(step_results)
    })


def get_executor_prompt(executor_type: str) -> str:
    """
    获取指定执行者的完整提示词 (字符串格式)
    
    Args:
        executor_type: 执行者类型 (image_executor, video_executor, general_executor)
        
    Returns:
        完整的执行者提示词
    """
    valid_executors = ["image_executor", "video_executor", "general_executor"]
    if executor_type not in valid_executors:
        raise ValueError(f"Invalid executor type: {executor_type}. Must be one of {valid_executors}")
    
    return apply_prompt_template_str(executor_type, {})


# ============================================================
# KIE 工具描述和操作指南配置文件 (保持原有内容)
# ============================================================

# 文本生成图像工具描述
TEXT_TO_IMAGE_DESC = """
Use the seedream-v4-text-to-image model (API provided by KIE) to create a task that generates an image. Returns the Task ID.
Arguments:
- prompt (str): The user's image description.
- resolution (str): Image resolution. Options: ["1K", "2K", "4K"].
- aspect_ratio (str): Image aspect ratio (e.g., "landscape_16_9").
"""

# 图像编辑工具描述
IMAGE_EDIT_DESC = """
Use the seedream-v4-edit model (API provided by KIE) to create an image editing task. If users want to generate images based on reference pictures, must invoke this tool. Returns the Task ID only.
Arguments:
- prompt (str): Describe ONLY the latest user's query. DO NOT include any other CONTEXT. Always append a clause such as “保持其余元素不变。”
- image_urls (list[str]): URLs of the reference images.
- seed (int): Random number. CHANGE THIS whenever the user asks to “retry” or “regenerate”.
- resolution (str): Image resolution. Options: ["1K", "2K", "4K"].
- aspect_ratio (str): Image aspect ratio. (e.g., "landscape_16_9").
"""

# Banana Pro 图像编辑工具描述
IMAGE_EDIT_BANANA_PRO_DESC = """
Use the Nano Banana Pro model (API provided by PPIO) to create an image editing task.
CRITICAL: This tool REQUIRES a reference image.
Arguments:
- prompt (str): Describe ONLY the latest user's query. DO NOT include any other CONTEXT. Always append a clause such as “保持其余元素不变。”
- image_urls (list[str]): The source image URLs. MUST retrieve from the `[REFERENCES]` section in context if available.
- seed (int): Random number. CHANGE THIS whenever the user asks to “retry” or “regenerate”.
- resolution (str): Image resolution. MUST be one of: ["1K", "2K", "4K"].
- aspect_ratio (str): Image aspect ratio. MUST be one of: ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"].
"""

# 统一任务状态查询工具描述
GET_TASK_STATUS_DESC = """
Returns the status and result URL of the task (supports both KIE and PPIO tasks).
Arguments:
- task_id (str): The ID of the task to check.
- 
Returns:
- If the task is successful: Returns the URL of the generated image.
- If processing: Returns "Task is processing..."
- If failed/not found: Returns error message.
"""

# 文本生成视频工具描述
TEXT_TO_VIDEO_DESC = """
Use the 'sora-2-text-to-video' model to create a task that generates a 10-second video. If users want to generate videos based on text description, must invoke this tool. Returns the Task ID.
Arguments:
- prompt (str): The user's video description.
- seed (int): A random number. CHANGE THIS whenever the user asks to "retry" or "regenerate".
- resolution (str): Video resolution (e.g., "720P", "1080P").
- aspect_ratio (str): Video aspect ratio. Options: ["landscape", "portrait"]. If the user use the default value "16:9", you should use the aspect ratio parameter "landscape". If the user use the default value "9:16", you should use the aspect ratio parameter "portrait".
- n_frames (str): Number of frames. Options: ["10", "15"].
"""

# 首帧生成视频工具描述
FIRST_FRAME_TO_VIDEO_DESC = """
Use the sora-2-image-to-video model (API provided by KIE) to create a task that generates a 10/15-second video using a provided image as the first frame. If users want to generate videos based on reference images, must invoke this tool. Returns the Task ID.
Arguments:
- image_source (list[str]): The reference image (URL or file path) to serve as the start frame.
- prompt (str): Description of the video.
- seed (int): A random number. CHANGE THIS whenever the user asks to "retry" or "regenerate".
- aspect_ratio (str): Video aspect ratio. Options: ["landscape", "portrait"]. If the user use the default value "16:9", you should use the aspect ratio parameter "landscape". If the user use the default value "9:16", you should use the aspect ratio parameter "portrait".
- n_frames (str): Number of frames. Options: ["10", "15"].
"""

# 去除水印工具描述
REMOVE_WATERMARK_DESC = """
Use the seedream-v4-edit model (API provided by KIE) to remove the watermark from the image. Returns the Task ID.
Arguments:
- prompt (str): The user's description of the image.
- image_urls (list[str]): A list of URLs of the reference images.
- seed (int): A random number. CHANGE THIS whenever the user asks to "retry" or "regenerate".
"""

# AI 助手的系统提示词
Your_Name_SYSTEM_PROMPT_PREFIX = """
### Role & Context
- You are an AI video creation assistant for the sequel to the anime "Your Name" (《你的名字》).
    - **LANGUAGE REQUIREMENT**: You MUST interact with the user in **Chinese (中文)**.
    - Your tone should be encouraging, creative, and helpful, like a professional director guiding a user.

"""

SUGGESTION_SYSTEM_PROMPT = """
You are a helpful assistant. Based on the conversation above, provide 3 short, relevant follow-up suggestions for the user to continue the story or creation process. Return the suggestions in a list of strings.

### Suggestion Logic (in 'suggestions' key)
Always provide exactly 3 strings in the list:
- Option 1 & 2: **Refinement** (e.g., "Fix face details", "Change lighting to sunset").
- Option 3: **Advance** (e.g., "Confirm and generate video", "Next step").
"""

Custom_SYSTEM_PROMPT_PREFIX = """
### Role & Context
- You are an AI video creation assistant for the user's custom request.
    - **LANGUAGE REQUIREMENT**: You MUST interact with the user in **Chinese (中文)**.
    - Your tone should be encouraging, creative, and helpful, like a professional director guiding a user.

"""


SYSTEM_PROMPT_SUFFIX = """
### ⚠️ Critical Execution Rules (MUST FOLLOW)
1. **CONFIG PROTOCOL**:
   - **Config**: You MUST apply the values from `[GLOBAL CONFIG]` (e.g., resolution, aspect_ratio, art_style) to every tool call, overriding default values. Except the user explicitly mentions them in query.

2. **Direct Action Protocol (NO CHATTER)**: 
   - If the user provides sufficient intent and parameters (e.g., Prompt + necessary reference), **IMMEDIATELY CALL THE TOOL**.
   - **ONE TOOL PER TURN**: You may ONLY call ONE tool in each conversation turn. After the tool returns, stop immediately and provide your answer to the user.
   - **REFERENCE HANDLING**: 
     - **TRUST THE PROMPT**: If the user's message contains a URL (even if injected by system), USE IT.
     - **Exception**: Only ask for clarification if you absolutely CANNOT find a reference image for an editing task.
     - **RETRY POLICY**: When retrying/regenerating, you MUST change the 'seed' parameter to a new random integer.

3. **Post-Tool Execution Protocol (Hiding Tech Details)**:
   - **EXECUTION CRITERIA**: You MUST consider a task as executed ONLY when you receive a returned `task_id`.
   - When a tool returns a `task_id`, treat it as a SUCCESS signal.
   - **FORBIDDEN**: Do NOT output the `task_id` or any technical identifiers in your answer.
   - **REQUIRED**: Simply inform the user that the generation task has started and the result will automatically appear in the "创作中心".
   - **STOP IMMEDIATELY**: After calling ONE tool, you MUST stop and wait for the user's next instruction. Do NOT call the same tool again. Do NOT call other tools in the same turn.
"""

Your_Name_SYSTEM_PROMPT = Your_Name_SYSTEM_PROMPT_PREFIX + SYSTEM_PROMPT_SUFFIX

Custom_SYSTEM_PROMPT = Custom_SYSTEM_PROMPT_PREFIX + SYSTEM_PROMPT_SUFFIX

