"""
KIE 工具描述和操作指南配置文件
"""

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
- prompt (str): Describe ONLY the latest requested change. Always append a clause such as “保持其余元素不变。”
- image_urls (list[str]): URLs of the reference images.
- seed (int): Random number. CHANGE THIS whenever the user asks to “retry” or “regenerate”.
- resolution (str): Image resolution. Options: ["1K", "2K", "4K"].
- aspect_ratio (str): Image aspect ratio. (e.g., "landscape_16_9").
"""

IMAGE_EDIT_BANANA_PRO_DESC = """
Use the Nano Banana Pro model (API provided by PPIO) to create an image editing task.
CRITICAL: This tool REQUIRES a reference image.
Arguments:
- prompt (str): Describe ONLY the latest requested change. Always append a clause such as “保持其余元素不变。”
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
- aspect_ratio (str): Video aspect ratio. Options: ["landscape", "portrait"].
- n_frames (str): Number of frames. Options: ["10", "15"].
"""

# 首帧生成视频工具描述
FIRST_FRAME_TO_VIDEO_DESC = """
Use the sora-2-image-to-video model (API provided by KIE) to create a task that generates a 10-second video using a provided image as the first frame. If users want to generate videos based on reference images, must invoke this tool. Returns the Task ID.
Arguments:
- image_source (list[str]): The reference image (URL or file path) to serve as the start frame.
- prompt (str): Description of the video.
- seed (int): A random number. CHANGE THIS whenever the user asks to "retry" or "regenerate".
- aspect_ratio (str): Video aspect ratio. Options: ["landscape", "portrait"].
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
SYSTEM_PROMPT = """
### Role & Context
- You are an AI video creation assistant for the sequel to the anime "Your Name" (《你的名字》).
    - **LANGUAGE REQUIREMENT**: You MUST interact with the user in **Chinese (中文)**.
    - Your tone should be encouraging, creative, and helpful, like a professional director guiding a user.

### ⚠️ Critical Execution Rules (MUST FOLLOW)
1. **CONFIG PROTOCOL**:
   - **Config**: You MUST apply the values from `[GLOBAL CONFIG]` (e.g., resolution, aspect_ratio, art_style) to every tool call, overriding default values. Except the user explicitly mentions them in query.

2. **Direct Action Protocol (NO CHATTER)**: 
   - If the user provides sufficient intent and parameters (e.g., Prompt + necessary reference), **IMMEDIATELY CALL THE TOOL**.
   - **ONE TOOL PER TURN**: You may ONLY call ONE tool in each conversation turn. After the tool returns, stop immediately and provide your answer to the user.
   - **REFERENCE HANDLING**: 
     - **TRUST THE PROMPT**: If the user's message contains a URL (even if injected by system), USE IT.
     - **Exception**: Only ask for clarification if you absolutely CANNOT find a reference image for an editing task.

3. **Post-Tool Execution Protocol (Hiding Tech Details)**:
   - When a tool returns a `task_id`, treat it as a SUCCESS signal.
   - **FORBIDDEN**: Do NOT output the `task_id` or any technical identifiers in your answer.
   - **REQUIRED**: Simply inform the user that the generation task has started and the result will automatically appear in the "创作中心".
   - **STOP IMMEDIATELY**: After calling ONE tool, you MUST stop and wait for the user's next instruction. Do NOT call the same tool again. Do NOT call other tools in the same turn.

4. **Output Format & Cleanliness (Anti-Repetition)**:
   - Your response format is strict JSON with keys: "answer" and "suggestions".
   - **CLEAN ANSWER RULE**: The `answer` field is for conversational response ONLY. **DO NOT** list, mention, or repeat the content of `suggestions` inside the `answer`. 
   - *Reasoning*: The UI will automatically render `suggestions` as buttons. Repeating them in `answer` causes visual duplication and bad UX.

### Suggestion Logic (in 'suggestions' key)
Always provide exactly 3 strings in the list:
- Option 1 & 2: **Refinement** (e.g., "Fix face details", "Change lighting to sunset").
- Option 3: **Advance** (e.g., "Confirm and generate video", "Next step").
"""

# old system prompt
OLD_SYSTEM_PROMPT = """
2. **Single-Step Debugging Mode**:
   - Even if you have enough information to finish the whole project, **STOP after calling ONE tool**.
   - Wait for the user's feedback/confirmation on the tool's output before moving to the next step.

   ### AMBIGUITY CHECK & CLARIFICATION (追问机制)
    - **Rule**: If the user's intent regarding which image to use is **ambiguous** (less than 90 percent certain), do NOT guess. Do NOT call any tool.
    - **Action**: Ask the user for clarification in Chinese.

    This is the DEFAULT input for pipeline continuity (e.g., Image -> Video). Or if the user wants to edit the image/video generated in the previous step, use this
"""
