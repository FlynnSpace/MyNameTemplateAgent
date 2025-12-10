import json
import uuid
import threading
import http.client
import requests
from langchain_core.tools import tool
from prompts.templates import (
    TEXT_TO_IMAGE_DESC, 
    IMAGE_EDIT_DESC, 
    IMAGE_EDIT_BANANA_PRO_DESC
)
from tools.utils import (
    _get_headers, 
    _get_headers_gemini,
    CREATE_TASK_URL,
    CALLBACK_URL,
    DEFAULT_SeedDream_IMAGE_SIZE,
    DEFAULT_IMAGE_RESOLUTION,
    DEFAULT_MAX_IMAGES,
    DEFAULT_NanoPro_IMAGE_SIZE,
    GEMINI_API_HOST,
    GEMINI_API_PATH,
    supabase,
    logger
)

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

