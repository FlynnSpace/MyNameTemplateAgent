import json
import requests
from langchain_core.tools import tool
from prompts.templates import (
    TEXT_TO_VIDEO_DESC, 
    FIRST_FRAME_TO_VIDEO_DESC
)
from tools.utils import (
    _get_headers, 
    CREATE_TASK_URL,
    CALLBACK_URL,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_N_FRAMES
)

@tool(description=TEXT_TO_VIDEO_DESC)
def text_to_video_by_kie_sora2_create_task(
    prompt: str, 
    seed: int,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO, 
    n_frames: str = DEFAULT_N_FRAMES
    ) -> str:
    payload = {
        "model": "sora-2-text-to-video",
        "callBackUrl": CALLBACK_URL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio or DEFAULT_ASPECT_RATIO,
            "n_frames": n_frames or DEFAULT_N_FRAMES,
            "remove_watermark": True
        }
    }

    response = requests.post(CREATE_TASK_URL, headers=_get_headers(), data=json.dumps(payload))
    result = response.json()

    return {
        "task_id": result["data"]["taskId"],
        "status": "Task created successfully!",
        "model": "sora2-text-to-video"
    }


@tool(description=FIRST_FRAME_TO_VIDEO_DESC)
def  first_frame_to_video_by_kie_sora2_create_task(
    prompt: str, 
    image_urls: list[str], 
    seed: int, 
    aspect_ratio: str = DEFAULT_ASPECT_RATIO, 
    n_frames: str = DEFAULT_N_FRAMES
    ) -> str:
    payload = {
        "model": "sora-2-image-to-video",
        "callBackUrl": CALLBACK_URL,
        "input": {
                    "prompt": prompt,
                    "image_urls": image_urls,
                    "aspect_ratio": aspect_ratio or DEFAULT_ASPECT_RATIO,
                    "n_frames": n_frames or DEFAULT_N_FRAMES,
                    "remove_watermark": True
        }
    }
    
    response = requests.post(CREATE_TASK_URL, headers=_get_headers(), data=json.dumps(payload))
    result = response.json()

    return {
        "task_id": result["data"]["taskId"],
        "status": "Task created successfully!",
        "model": "sora2-image-to-video"
    }

