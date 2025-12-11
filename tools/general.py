import json
import requests
import time
from typing import Union, Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from prompts.templates import (
    GET_TASK_STATUS_DESC
)
from tools.utils import (
    _get_headers, 
    RECORD_INFO_URL,
    supabase,
    logger
)


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

