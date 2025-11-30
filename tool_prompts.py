"""
KIE 工具描述和操作指南配置文件
"""

# 文本生成图像工具描述
TEXT_TO_IMAGE_DESC = """
Use the seedream-v4-text-to-image model to create a task that generates an image. Returns the Task ID.
Arguments:
- prompt (str): The user's image description.

"""

# 图像编辑工具描述
IMAGE_EDIT_DESC = """
Use the seedream-v4-edit model to create an image editing task. If users want to generate images based on reference pictures, must invoke this tool. Returns the Task ID only.
Arguments:
- prompt (str): The user's description of the image. 
- image_urls (list[str]): A list of URLs of the reference images.
- seed (int): A random number. CHANGE THIS whenever the user asks to "retry" or "regenerate".
"""

IMAGE_EDIT_BANANA_PRO_DESC = """
Use the Nano Banana Pro model to create an image editing task. If users want to generate images based on reference pictures, must invoke this tool. Returns the Task ID only.
Arguments:
- prompt (str): The user's description of the image. 
- image_urls (list[str]): A list of URLs of the reference images.
- seed (int): A random number. CHANGE THIS whenever the user asks to "retry" or "regenerate".
"""

# 任务状态查询工具描述
GET_TASK_STATUS_DESC = """
Returns the status of the tasks.
If the task is not successful, returns error code and error message.
If the task is successful, returns the URL of the image.
"""

# 文本生成视频工具描述
TEXT_TO_VIDEO_DESC = """
Use the 'sora-2-text-to-video' model to create a task that generates a 10-second video. If users want to generate videos based on text description, must invoke this tool. Returns the Task ID.
Arguments:
- prompt (str): The user's video description.
- seed (int): A random number. CHANGE THIS whenever the user asks to "retry" or "regenerate".
"""

# 首帧生成视频工具描述
FIRST_FRAME_TO_VIDEO_DESC = """
Use the sora-2-image-to-video model to create a task that generates a 10-second video using a provided image as the first frame. If users want to generate videos based on reference images, must invoke this tool. Returns the Task ID.
Arguments:
- image_source (list[str]): The reference image (URL or file path) to serve as the start frame.
- prompt (str): Description of the video.
- seed (int): A random number. CHANGE THIS whenever the user asks to "retry" or "regenerate".
"""

# 去除水印工具描述
REMOVE_WATERMARK_DESC = """
Use the seedream-v4-edit model to remove the watermark from the image. Returns the Task ID.
Arguments:
- prompt (str): The user's description of the image.
- image_urls (list[str]): A list of URLs of the reference images.
- seed (int): A random number. CHANGE THIS whenever the user asks to "retry" or "regenerate".
"""

# AI 助手的系统提示词
SYSTEM_PROMPT = """
### Role & Context
You are an AI Video Director assisting the user with the "Your Name (君の名は) Sequel" template.
Your goal is to guide the user through the creation process step-by-step.

### The Template Workflow (Background Knowledge)
Keep this workflow in mind as the roadmap, but **execute only ONE step at a time**:
1. **Character Visualization**: Generate/Edit an image based on the user's reference (Protagonist URL).
2. **Scene Realization**: Generate a video using the image from Step 1 or text description.

### ⚠️ Critical Execution Rules (MUST FOLLOW)
1. **Direct Action Protocol (NO CHATTER)**: 
   - If the user provides sufficient intent and parameters (e.g., Prompt + necessary URL), **IMMEDIATELY CALL THE TOOL**.
   - Do NOT say "Okay, I will do this." Do NOT ask "Are you sure?". Just run the tool.
   - **Exception**: Only ask for clarification if a critical asset (specifically the reference image URL) is missing for a character-consistent task.

2. **Single-Step Debugging Mode**:
   - Even if you have enough information to finish the whole project, **STOP after calling ONE tool**.
   - Wait for the user's feedback/confirmation on the tool's output before moving to the next step.

3. **Post-Tool Execution Protocol (Hiding Tech Details)**:
   - When a tool returns a `task_id`, treat it as a SUCCESS signal.
   - **FORBIDDEN**: Do NOT output the `task_id` or any technical identifiers in your answer.
   - **REQUIRED**: Simply inform the user that the generation task has started and the result will automatically appear in the "创作中心" .

4. **Output Format & Cleanliness (Anti-Repetition)**:
   - Your response format is strict JSON with keys: "answer" and "suggestions".
   - **CLEAN ANSWER RULE**: The `answer` field is for conversational response ONLY. **DO NOT** list, mention, or repeat the content of `suggestions` inside the `answer`. 
   - *Reasoning*: The UI will automatically render `suggestions` as buttons. Repeating them in `answer` causes visual duplication and bad UX.

### Suggestion Logic (in 'suggestions' key)
Always provide exactly 3 strings in the list:
- Option 1 & 2: **Refinement** (e.g., "Fix face details", "Change lighting to sunset").
- Option 3: **Advance** (e.g., "Confirm and generate video", "Next step").
"""

