import os
from dotenv import load_dotenv
from supabase import create_client, Client
from utils.logger import logger_proxy as logger

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
DEFAULT_IMAGE_RESOLUTION = "2K"  # 1K, 2K, 4K
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

