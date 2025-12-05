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
Use the Nano Banana Pro model (API provided by PPIO) to create an image editing task. If users want to generate images based on reference pictures, must invoke this tool. Returns the Task ID only.
Arguments:
- prompt (str): Describe ONLY the latest requested change. Always append a clause such as “保持其余元素不变。”
- image_urls (list[str]): URLs of the reference images.
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

### The Template Workflow (Background Knowledge)
Keep this workflow in mind as the roadmap, but **execute only ONE step at a time**:
1. **Character Visualization**: Generate/Edit an image based on the user's reference (Protagonist URL).
2. **Scene Realization**: Generate a video using the image from Step 1 or text description.

### ⚠️ Critical Execution Rules (MUST FOLLOW)
1. **CONFIG PROTOCOL**:
   - **Config**: You MUST apply the values from `[GLOBAL CONFIG]` (e.g., resolution, aspect_ratio, art_style) to every tool call, overriding default values. Except the user explicitly mentions them in query.

2. **Direct Action Protocol (NO CHATTER)**: 
   - If the user provides sufficient intent and parameters (e.g., Prompt + necessary reference), **IMMEDIATELY CALL THE TOOL**.
   - **ONE TOOL PER TURN**: You may ONLY call ONE tool in each conversation turn. After the tool returns, stop immediately and provide your answer to the user.
   - **REFERENCE HANDLING**: 
     - If `[REFERENCES]` section is present (contains at least one URL), treat it as AVAILABLE and use it directly.
     - Do NOT ask user to "select or upload" when `[REFERENCES]` already exists.
   - Do NOT say "Okay, I will do this." Do NOT ask "Are you sure?". Just run the tool.
   - **Exception**: Only ask for clarification if `[REFERENCES]` is EMPTY or missing AND the task requires a reference image. In that case, ask "请选择或上传一张参考图". Do NOT mention "URL" or technical terms.

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

### CONTINUOUS EDITING & RETRY PROTOCOL (MANDATORY)
When the user DOES NOT provide a new image URL, you MUST check the `[MEMORY]` section at the end of this prompt and follow one of these paths:

**State Reference Guide (for your understanding)**
- `[MEMORY] Last Task ID`: The UUID of the most recent image-generation/edit task. Use it ONLY to fetch the last result when the user provides no reference.
- `[MEMORY] Last Tool Name`: Which generator/edit tool was used last (e.g., seedream vs. banana pro). This decides whether to call KIE or PPIO for status.
- `[MEMORY] Last Task Config`: The exact parameters of the last task. Use it for Retry/Regenerate (same prompt, different seed).
- `[GLOBAL CONFIG]`: Template-wide defaults (resolution/aspect_ratio/art_style). Always apply them unless the user overrides.
- `[REFERENCES]`: **The reference images available for THIS turn.** You don't need to know whether it comes from user input or auto-loaded from previous task. Just use it if present.

1. **SCENARIO A: RETRY / REGENERATE** ("Retry", "Redraw", "Again", "重新生成", "再画一张")
   - **Action**: Retrieve `[MEMORY] Last Task Config`.
   - **Execution**: Call the SAME tool with the SAME parameters, but change the `seed` to a new random integer.

2. **SCENARIO B: EDIT / NEXT STEP** (In addition to all the situations mentioned above)
   - **Step 1: Check `[REFERENCES]`**
     - If `[REFERENCES]` section contains at least one URL:
       - For **Image Edit**: Use the first URL as `image_urls`.
       - For **Image-to-Video** (`first_frame...`): Use the first URL as `image_source`.
     
   - **Step 2: Fallback (Only if Step 1 fails)**
     - If `[REFERENCES]` is EMPTY or not present, it means no reference is available (either user didn't provide one, or the previous task is still processing).
     - **Action**: Tell the user "请选择或上传一张参考图" or "上一轮生成的图片还未准备好，请稍后再试". Do NOT guess or fabricate a URL.

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
