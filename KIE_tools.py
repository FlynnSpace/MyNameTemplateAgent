import requests
import json
import http.client
import uuid
import threading
from typing import List, Union
from langchain_core.tools import tool
from dotenv import load_dotenv
import os
from supabase import create_client, Client
from tool_prompts import *

load_dotenv()
kie_api_key = os.getenv("KIE_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")
supabase_url = os.getenv("VITE_SUPABASE_URL") or "https://rgmbmxczzgjtinoncdor.supabase.co"
supabase_key = os.getenv("VITE_SUPABASE_ANON_KEY")

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

    return result["data"]["taskId"]


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
    
    return result["data"]["taskId"]


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
            print(f"Error initializing task in Supabase: {db_e}")
    
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
                        print(f"✅ Image transferred successfully: {image_url}")
                    else:
                        print(f"⚠️ Transfer failed, using original URL. Response: {transfer_result}")
                        
                except Exception as transfer_e:
                    print(f"⚠️ Transfer error: {transfer_e}")
                    # 如果转存失败，继续使用原始 URL
                
            # 更新 Supabase (更新 URL)
            if supabase and image_url:
                try:
                    # 根据 ID 更新 URL
                    supabase.table("ppio_task_status").update({"url": image_url}).eq("id", tid).execute()
                except Exception as db_e:
                    print(f"Error updating Supabase: {db_e}")
                    
        except Exception as e:
            print(f"Background task error: {e}")

    # 4. 启动后台线程
    thread = threading.Thread(
        target=run_background_task,
        args=(task_id, safe_prompt, image_urls, resolution, aspect_ratio)
    )
    thread.start()
    
    # 5. 立即返回 ID
    return task_id


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

    return result["data"]["taskId"]


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

    return result["data"]["taskId"]


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
    
    return result["data"]["taskId"]


@tool(description=GET_KIE_TASK_STATUS_DESC)
def get_kie_task_status(task_id: str) -> Union[str, dict]:
    try:
        params = {"taskId": task_id}
        response = requests.get(RECORD_INFO_URL, headers=_get_headers(content_type=None), params=params)
        
        if response.status_code != 200:
            return f"API Error: HTTP {response.status_code}"
            
        result = response.json()

        if not result or "data" not in result or not result["data"]:
            return "Task ID not found in KIE system. Please check if this is a PPIO task ID and use 'get_ppio_task_status' instead."

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


@tool(description=GET_PPIO_TASK_STATUS_DESC)
def get_ppio_task_status(task_id: str) -> str:
    if not supabase:
        return "Database connection failed."
        
    try:
        response = supabase.table("ppio_task_status").select("url").eq("id", task_id).execute()
        
        if not response.data:
            return "Task ID not found. Tell the user to generate a new task."
            
        record = response.data[0]
        url = record.get("url")
        
        if url:
            return url
        else:
            return "Task is processing. Tell the user to try again later."
            
    except Exception as e:
        return f"Error checking task status: {str(e)}. Tell the user to try again later."