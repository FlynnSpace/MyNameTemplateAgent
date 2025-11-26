import requests
import json
from langchain_core.tools import tool
from dotenv import load_dotenv
import os
from tool_prompts import (
    TEXT_TO_IMAGE_DESC,
    IMAGE_EDIT_DESC,
    GET_TASK_STATUS_DESC,
    TEXT_TO_VIDEO_DESC,
    FIRST_FRAME_TO_VIDEO_DESC,
    REMOVE_WATERMARK_DESC
)

load_dotenv()
kie_api_key = os.getenv("KIE_API_KEY")

# API 配置常量
API_BASE_URL = "https://api.kie.ai/api/v1"
CREATE_TASK_URL = f"{API_BASE_URL}/jobs/createTask"
RECORD_INFO_URL = f"{API_BASE_URL}/jobs/recordInfo"
CALLBACK_URL = None

# 图像生成默认配置
DEFAULT_SeedDream_IMAGE_SIZE = "landscape_16_9"  # https://kie.ai/seedream-api
DEFAULT_NanoPro_IMAGE_SIZE = "16:9"
DEFAULT_IMAGE_RESOLUTION = "1K"
DEFAULT_MAX_IMAGES = 1

# 视频生成默认配置
DEFAULT_ASPECT_RATIO = "landscape"  # portrait
DEFAULT_N_FRAMES = "10"


def _get_headers(content_type="application/json"):
    """获取请求头"""
    headers = {"Authorization": f"Bearer {kie_api_key}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers

@tool(description=TEXT_TO_IMAGE_DESC)
def text_to_image_by_seedream_v4_model_create_task(prompt: str):
    payload = {
        "model": "bytedance/seedream-v4-text-to-image",
        "callBackUrl": CALLBACK_URL,
        "input": {
            "prompt": prompt,
            "image_size": DEFAULT_SeedDream_IMAGE_SIZE,
            "image_resolution": DEFAULT_IMAGE_RESOLUTION,
            "max_images": DEFAULT_MAX_IMAGES
        }
    }

    response = requests.post(CREATE_TASK_URL, headers=_get_headers(), data=json.dumps(payload))
    result = response.json()

    return result["data"]["taskId"]


@tool(description=IMAGE_EDIT_DESC)
def image_edit_by_seedream_v4_edit_create_task(prompt: str, image_urls: list[str]):
    payload = {
        "model": "bytedance/seedream-v4-edit",
        "callBackUrl": CALLBACK_URL,
        "input": {
            "prompt": prompt,
            "image_urls": image_urls,
            "image_size": DEFAULT_SeedDream_IMAGE_SIZE,
            "image_resolution": DEFAULT_IMAGE_RESOLUTION,
            "max_images": DEFAULT_MAX_IMAGES
        }
    }

    response = requests.post(CREATE_TASK_URL, headers=_get_headers(), data=json.dumps(payload))
    result = response.json()
    
    return result["data"]["taskId"]


@tool(description=GET_TASK_STATUS_DESC)
def get_task_status(task_id: str):
    params = {"taskId": task_id}
    response = requests.get(RECORD_INFO_URL, headers=_get_headers(content_type=None), params=params)
    result = response.json()

    if result["data"]["state"] == "success":
        return json.loads(result['data']['resultJson'])['resultUrls'][0]
    else:
        return {
            "status": result["data"]["state"],
            "code": result["data"]["failCode"],
            "message": result["data"]["failMsg"]
        }


@tool(description=TEXT_TO_VIDEO_DESC)
def text_to_video_by_sora2_model_create_task(prompt: str):
    payload = {
        "model": "sora-2-text-to-video",
        "callBackUrl": CALLBACK_URL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": DEFAULT_ASPECT_RATIO,
            "n_frames": DEFAULT_N_FRAMES,
            "remove_watermark": True
        }
    }

    response = requests.post(CREATE_TASK_URL, headers=_get_headers(), data=json.dumps(payload))
    result = response.json()

    return result["data"]["taskId"]


@tool(description=FIRST_FRAME_TO_VIDEO_DESC)
def  first_frame_to_video_by_sora2_model_create_task(prompt: str, image_urls: list[str]):
    payload = {
        "model": "sora-2-image-to-video",
        "callBackUrl": CALLBACK_URL,
        "input": {
                    "prompt": prompt,
                    "image_urls": image_urls,
                    "aspect_ratio": DEFAULT_ASPECT_RATIO,
                    "n_frames": DEFAULT_N_FRAMES,
                    "remove_watermark": True
        }
    }
    
    response = requests.post(CREATE_TASK_URL, headers=_get_headers(), data=json.dumps(payload))
    result = response.json()

    return result["data"]["taskId"]


@tool(description=REMOVE_WATERMARK_DESC)
def remove_watermark_from_image_by_seedream_v4_edit_create_task(prompt: str, image_urls: list[str]):
    payload = {
        "model": "bytedance/seedream-v4-edit",
        "callBackUrl": CALLBACK_URL,
        "input": {
            "prompt": prompt,
            "image_urls": image_urls,
            "image_size": DEFAULT_SeedDream_IMAGE_SIZE,
            "image_resolution": DEFAULT_IMAGE_RESOLUTION,
            "max_images": DEFAULT_MAX_IMAGES
        }
    }

    response = requests.post(CREATE_TASK_URL, headers=_get_headers(), data=json.dumps(payload))
    result = response.json()
    
    return result["data"]["taskId"]