import requests
import json
import http.client
import uuid
import threading
from typing import List, Union, Annotated
from langchain_core.tools import tool
from dotenv import load_dotenv
import os
from supabase import create_client, Client
from tool_prompts import *
from langgraph.prebuilt import InjectedState
from logger_util import get_logger

load_dotenv()
kie_api_key = os.getenv("KIE_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")
supabase_url = os.getenv("VITE_SUPABASE_URL") or "https://rgmbmxczzgjtinoncdor.supabase.co"
supabase_key = os.getenv("VITE_SUPABASE_ANON_KEY")
logger = get_logger("mynamechat.kie_tools")

# 初始化 Supabase
supabase: Client = create_client(supabase_url, supabase_key) if supabase_key else None

# API 配置常量
API_BASE_URL = "https://api.kie.ai/api/v1"
CREATE_TASK_URL = f"{API_BASE_URL}/jobs/createTask"
RECORD_INFO_URL = f"{API_BASE_URL}/jobs/recordInfo"
GEMINI_API_HOST = "api.ppinfra.com"
GEMINI_API_PATH = "/v3/gemini-3-pro-image-edit"
CALLBACK_URL = None

# 图像生成默认配置
DEFAULT_SeedDream_IMAGE_SIZE = "landscape_16_9"  # https://kie.ai/seedream-api
DEFAULT_NanoPro_IMAGE_SIZE = "16:9"  # 16:9, 9:16, 1:1, 4:3, 3:4, 21:9
DEFAULT_IMAGE_RESOLUTION = "1K"  # 1K, 2K, 4K
DEFAULT_MAX_IMAGES = 1

# 视频生成默认配置
DEFAULT_ASPECT_RATIO = "landscape"  # portrait
DEFAULT_N_FRAMES = "10"  # 10, 15


def _get_headers(content_type="application/json"):
    """获取请求头"""
    headers = {"Authorization": f"Bearer {kie_api_key}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _get_headers_gemini():
    headers = {
        'Authorization': f'Bearer {gemini_api_key}',
        'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'Host': GEMINI_API_HOST,
        'Connection': 'keep-alive'
    }
    return headers

@tool(description=TEXT_TO_IMAGE_DESC)
def text_to_image_by_kie_seedream_v4_create_task(
    prompt: str, 
    resolution: str = DEFAULT_IMAGE_RESOLUTION, 
    aspect_ratio: str = DEFAULT_SeedDream_IMAGE_SIZE
    ) -> str:
    payload = {
        "model": "bytedance/seedream-v4-text-to-image",
        "callBackUrl": CALLBACK_URL,
        "input": {
            "prompt": prompt,
            "image_size": aspect_ratio or DEFAULT_SeedDream_IMAGE_SIZE,
            "image_resolution": resolution or DEFAULT_IMAGE_RESOLUTION,
            "max_images": DEFAULT_MAX_IMAGES
        }
    }

    response = requests.post(CREATE_TASK_URL, headers=_get_headers(), data=json.dumps(payload))
    result = response.json()

    if not result or "data" not in result or not result["data"]:
        logger.error(f"KIE API Error in text_to_image_by_kie_seedream_v4_create_task: {result}")
        return f"Error creating task: {result.get('msg', 'Unknown error')} (Response: {result})"

    return {
        "task_id": result["data"]["taskId"],
        "status": "Task created successfully!",
        "model": "seedream-v4-text"
    }


@tool(description=IMAGE_EDIT_DESC)
def image_edit_by_kie_seedream_v4_create_task(
    prompt: str,
    image_urls: list[str],  
    seed: int, 
    resolution: str = DEFAULT_IMAGE_RESOLUTION,
    aspect_ratio: str = DEFAULT_SeedDream_IMAGE_SIZE
    ) -> str:
    payload = {
        "model": "bytedance/seedream-v4-edit",
        "callBackUrl": CALLBACK_URL,
        "input": {
            "prompt": prompt,
            "image_urls": image_urls,
            "image_size": aspect_ratio or DEFAULT_SeedDream_IMAGE_SIZE,
            "image_resolution": resolution or DEFAULT_IMAGE_RESOLUTION,
            "max_images": DEFAULT_MAX_IMAGES
        }
    }

    response = requests.post(CREATE_TASK_URL, headers=_get_headers(), data=json.dumps(payload))
    result = response.json()
    
    if not result or "data" not in result or not result["data"]:
        logger.error(f"KIE API Error in image_edit: {result}")
        return f"Error creating task: {result.get('msg', 'Unknown error')} (Response: {result})"

    return {
        "task_id": result["data"]["taskId"],
        "status": "Task created successfully!",
        "model": "seedream-v4-edit-image"
    }


@tool(description=IMAGE_EDIT_BANANA_PRO_DESC)
def image_edit_by_ppio_banana_pro_create_task(
    prompt: str,
    image_urls: list[str],  
    seed: int, 
    resolution: str = DEFAULT_IMAGE_RESOLUTION, 
    aspect_ratio: str = DEFAULT_NanoPro_IMAGE_SIZE
    ) -> str:
    # 1. 生成本地 Task ID
    task_id = str(uuid.uuid4())

    # 2. 立即入库占位 (URL为空)
    if supabase:
        try:
            db_data = {
                "id": task_id,
                "url": ""  # 初始为空，等待后台更新
            }
            supabase.table("ppio_task_status").insert(db_data).execute()
        except Exception as db_e:
            logger.warning("Error initializing task in Supabase: %s", db_e)
    
    # 3. 定义后台任务函数
    def run_background_task(tid, p_prompt, p_urls, p_resolution, p_aspect_ratio):
        try:
            # 执行耗时的 API 请求
            conn = http.client.HTTPSConnection(GEMINI_API_HOST)
            
            payload = json.dumps({
                "prompt": p_prompt,
                "image_urls": p_urls,
                "aspect_ratio": p_aspect_ratio or DEFAULT_NanoPro_IMAGE_SIZE,
                "size": p_resolution or DEFAULT_IMAGE_RESOLUTION
            })
            
            headers = _get_headers_gemini()
            
            conn.request("POST", GEMINI_API_PATH, payload, headers)
            
            res = conn.getresponse()
            data = res.read()
            result = json.loads(data.decode("utf-8"))
            
            image_url = ""
            # 解析返回的 Image URL
            if "image_urls" in result and isinstance(result["image_urls"], list) and len(result["image_urls"]) > 0:
                image_url = result["image_urls"][0]
            
            # --- 图片转存 ---
            if image_url:
                try:
                    transfer_conn = http.client.HTTPSConnection("oss-trar-server-vwsitywsrq.cn-hangzhou.fcapp.run")
                    transfer_payload = json.dumps({"url": image_url})
                    transfer_headers = {
                        'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
                        'Content-Type': 'application/json',
                        'Accept': '*/*',
                        'Connection': 'keep-alive'
                    }
                    transfer_conn.request("POST", "/transfer", transfer_payload, transfer_headers)
                    transfer_res = transfer_conn.getresponse()
                    transfer_data = transfer_res.read()
                    transfer_result = json.loads(transfer_data.decode("utf-8"))
                    
                    if "url" in transfer_result:
                        image_url = transfer_result["url"]
                        logger.info("Image transferred successfully: %s", image_url)
                    else:
                        logger.warning("Transfer failed, using original URL. Response: %s", transfer_result)
                        
                except Exception as transfer_e:
                    logger.warning("Transfer error: %s", transfer_e)
                    # 如果转存失败，继续使用原始 URL
                
            # 更新 Supabase (更新 URL)
            if supabase and image_url:
                try:
                    # 根据 ID 更新 URL
                    supabase.table("ppio_task_status").update({"url": image_url}).eq("id", tid).execute()
                except Exception as db_e:
                    logger.warning("Error updating Supabase: %s", db_e)
                    
        except Exception as e:
            logger.error("Background task error: %s", e)

    # 4. 启动后台线程
    thread = threading.Thread(
        target=run_background_task,
        args=(task_id, prompt, image_urls, resolution, aspect_ratio)
    )
    thread.start()
    
    # 5. 立即返回 ID
    return {
        "task_id": task_id,
        "status": "Task created successfully!",
        "model": "ppio-banana-pro"
    }


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

    if not result or "data" not in result or not result["data"]:
        logger.error(f"KIE API Error in text_to_video: {result}")
        return f"Error creating task: {result.get('msg', 'Unknown error')} (Response: {result})"

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

    if not result or "data" not in result or not result["data"]:
        logger.error(f"KIE API Error in first_frame_to_video: {result}")
        return f"Error creating task: {result.get('msg', 'Unknown error')} (Response: {result})"

    return {
        "task_id": result["data"]["taskId"],
        "status": "Task created successfully!",
        "model": "sora2-image-to-video"
    }


@tool(description=REMOVE_WATERMARK_DESC)
def remove_watermark_from_image_by_kie_seedream_v4_create_task(
    prompt: str, 
    image_urls: list[str], 
    seed: int, 
    ) -> str:
    payload = {
        "model": "bytedance/seedream-v4-edit",
        "callBackUrl": CALLBACK_URL,
        "input": {
            "prompt": prompt,
            "image_urls": image_urls,
            "max_images": DEFAULT_MAX_IMAGES
        }
    }

    response = requests.post(CREATE_TASK_URL, headers=_get_headers(), data=json.dumps(payload))
    result = response.json()
    
    if not result or "data" not in result or not result["data"]:
        logger.error(f"KIE API Error in remove_watermark: {result}")
        return f"Error creating task: {result.get('msg', 'Unknown error')} (Response: {result})"

    return {
        "task_id": result["data"]["taskId"],
        "status": "Task created successfully!",
        "model": "seedream-v4-edit-image"
    }

# --- 内部 Helper Functions (非 Tool) ---

def _get_kie_task_status_impl(task_id: str) -> Union[str, dict]:
    try:
        params = {"taskId": task_id}
        response = requests.get(RECORD_INFO_URL, headers=_get_headers(content_type=None), params=params)
        
        if response.status_code != 200:
            return f"API Error: HTTP {response.status_code}"
            
        result = response.json()

        if not result or "data" not in result or not result["data"]:
            return "Task ID not found in KIE system."

        data = result["data"]
        state = data.get("state")

        if state == "success":
            # 安全解析 JSON
            try:
                result_json = json.loads(data.get('resultJson', '{}'))
                if 'resultUrls' in result_json and result_json['resultUrls']:
                    return result_json['resultUrls'][0]
                else:
                    return "Task succeeded but no result URL found."
            except json.JSONDecodeError:
                return "Task succeeded but resultJson is invalid."
        else:
            return {
                "status": state,
                "code": data.get("failCode"),
                "message": data.get("failMsg")
            }
            
    except Exception as e:
        return f"Error checking KIE task status: {str(e)}"


def _get_ppio_task_status_impl(task_id: str, max_retries: int = 60, delay: float = 2.0) -> str:
    """
    查询 PPIO 任务状态的内部实现。
    
    Args:
        task_id: 任务 ID
        max_retries: 最大重试次数 (默认 10 次)
        delay: 每次重试间隔秒数 (默认 2.0 秒)
        
    总等待时间 ≈ max_retries * delay (默认 20秒)
    """
    if not supabase:
        return "Database connection failed."
        
    import time
    
    for attempt in range(max_retries):
        try:
            # 查询 Supabase
            response = supabase.table("ppio_task_status").select("url").eq("id", task_id).execute()
            
            if not response.data:
                # 如果刚创建还没入库（极少见），或者 ID 错误
                if attempt < 3: # 前几次允许容错
                    time.sleep(1)
                    continue
                return "Task ID not found in PPIO database."
                
            record = response.data[0]
            url = record.get("url")
            
            # 1. 成功获取到 URL
            if url and isinstance(url, str) and url.strip():
                return url
            
            # 2. URL 为空，说明还在生成中，等待后重试
            # 使用简单的线性等待，避免阻塞太久，但给予足够的时间窗口
            if attempt < max_retries - 1:
                time.sleep(delay)
                
        except Exception as e:
            logger.warning(f"Error querying Supabase (attempt {attempt+1}/{max_retries}): {e}")
            # 网络错误也进行简短避让后重试
            time.sleep(1)
            
    return "Task is processing."


@tool(description=GET_TASK_STATUS_DESC)
def get_task_status(task_id: str, state: Annotated[dict, InjectedState]) -> Union[str, dict]:
    """
    Unified task status checker.
    Dispatches to the correct API (KIE or PPIO) based on the tool used to create the task.
    """
    last_tool = state.get("last_tool_name", "").lower()
    
    # 简单的分发逻辑
    if "ppio" in last_tool or "banana" in last_tool:
        return _get_ppio_task_status_impl(task_id)
    else:
        # Default to KIE or check if it's a KIE tool
        return _get_kie_task_status_impl(task_id)
