import json
from typing import Callable, List
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from state.schemas import AgentState
from tools.general import _get_ppio_task_status_impl, _get_kie_task_status_impl
from utils.logger import get_logger

logger = get_logger("mynamechat.nodes.core")

def log_system_message(message: str, echo: bool = False) -> None:
    logger.info(message)
    if echo:
        print(message)

def create_model_node(llm: BaseChatModel, system_prompt_template: str, tools: List[BaseTool]) -> Callable[[AgentState], dict]:
    """
    Factory to create the core model calling node.
    Encapsulates the complex logic of auto-loading previous task results.
    
    Args:
        llm: The language model to use (should be bound with tools if needed, or binding happens inside?)
             NOTE: To support "no tools" mode properly, we might need to handle binding here or pass two LLMs.
             But a cleaner way is to unbind tools dynamically or pass a raw LLM and bind it here.
             
             Let's assume 'llm' passed here is the RAW model. We bind it inside.
    """
    
    # Pre-bind tools to the LLM
    structured_llm = llm.bind_tools(tools)
    structured_llm_no_tools = llm # Raw model has no tools bound

    def model_call(state: AgentState) -> dict:
        """模型调用节点：负责构建 Prompt 并调用 LLM，同时处理自动加载逻辑"""

        def _snapshot(tag: str):
            refs = state.get("references") or []
            log_system_message(
                f"[STATE:{tag}] msgs={state.get('messages')}, \n================================================\n"
                f"refs={state.get('references')},"
                f"last_task_id={state.get('last_task_id')}, last_tool_name={state.get('last_tool_name')}",          
                echo=False,
            )
        _snapshot("enter")
        
        # --- 计数器自增 ---
        current_count = state.get("model_call_count", 0) + 1
        log_system_message(f"[Step] Model Call Count: {current_count}", echo=False)

        # --- 自动加载上一轮生成结果 (Auto-Load Logic) ---
        current_refs = state.get("references", [])
        last_tid = state.get("last_task_id")
        last_tool = state.get("last_tool_name")
        
        # [FIX] 增加判定：如果用户 Prompt 中已经包含 url 链接，则认为用户提供了素材，不进行自动 Hack
        last_human_msg = state["messages"][-1] if state["messages"] and isinstance(state["messages"][-1], HumanMessage) else None
        user_provided_url_in_text = False
        if last_human_msg and ("http://" in last_human_msg.content or "https://" in last_human_msg.content):
            user_provided_url_in_text = True
        
        # 如果当前没有引用，且有上一轮任务，且上一轮是图像编辑任务，尝试自动加载
        if current_count%2 == 1 and not current_refs and not user_provided_url_in_text and last_tid and last_tool:
            if "image_edit" in last_tool.lower():
                fetched_url = None
                log_system_message(f"[系统] 尝试自动加载上一轮任务结果 (ID: {last_tid})...", echo=False)
                
                # 根据 Last Tool Name 决定调用哪个查询函数
                if "ppio" in last_tool.lower() or "banana" in last_tool.lower():
                    try:
                        res = _get_ppio_task_status_impl(last_tid)
                        if isinstance(res, str) and res.startswith("http"):
                            fetched_url = res
                        log_system_message(f"PPIO 查询成功: {fetched_url}", echo=False)
                    except Exception as e:
                        log_system_message(f"[系统] PPIO 查询失败: {e}", echo=False)
                else:
                    try:
                        res = _get_kie_task_status_impl(last_tid)
                        if isinstance(res, str) and res.startswith("http"):
                            fetched_url = res
                        log_system_message(f"KIE 查询成功: {fetched_url}", echo=False)
                    except Exception as e:
                         log_system_message(f"[系统] KIE 查询失败: {e}", echo=False)
                
                if fetched_url:
                    log_system_message(f"[系统] ✅ 成功加载上一轮结果: {fetched_url}", echo=False)
                    # 直接更新 state，本轮生效
                    state["references"] = [{"url": fetched_url, "desc": "Last Generation Result (Auto-loaded)"}]
                    
                    # --- Hack 用户 Prompt ---
                    messages = state["messages"]
                    if messages and isinstance(messages[-1], HumanMessage):
                        original_content = messages[-1].content
                        # 避免重复添加
                        if "系统自动注入" not in original_content:
                            new_content = f"（系统自动注入：请使用上一次的编辑结果 {fetched_url} 作为参考图。）\n" + original_content
                            messages[-1].content = new_content
                            log_system_message(f"[Hack] 修改用户 Prompt: {new_content[:100]}...", echo=False)
                else:
                    log_system_message("[系统] ⏳ 上一轮任务仍在处理中或无法获取结果。", echo=False)
            else:
                log_system_message(f"跳过自动加载: refs={current_refs} last_tid={last_tid} last_tool={last_tool}", echo=False)

        # 1. 注入动态上下文
        context_str = ""
        
        # 注入素材库 (使用本轮的 references，可能来自用户输入或自动加载)
        if state.get("references"):
            context_str += "\n### [REFERENCES]\n"
            for idx, asset in enumerate(state["references"]):
                context_str += f"{idx+1}. {asset.get('desc', 'Image')}: {asset.get('url')}\n"

        # 注入全局风格配置
        if state.get("global_config"):
            context_str += f"\n### [GLOBAL CONFIG]\n{json.dumps(state['global_config'], ensure_ascii=False)}\n"
            context_str += "INSTRUCTION: Always reference these parameters (resolution, aspect_ratio, art_style, etc.) when calling tools unless the user explicitly overrides them in query.\n"

        # 2. 组合 Prompt
        # system_prompt_template 中应该包含 {tools_description} 占位符
        final_system_content = system_prompt_template.format(tools_description=str([tool.name for tool in tools])) + context_str
        system_prompt = SystemMessage(content=final_system_content)
        
        # 3. 调用模型
        # [FIX] 强制单步执行逻辑：如果是第二轮（工具执行回来后），不再提供工具，强制只生成回复
        # if current_count > 1:
        #     log_system_message("[系统] 检测到多轮对话，强制切换为无工具模式 (Final Answer Mode)", echo=False)
        #     response = structured_llm_no_tools.invoke([system_prompt] + state["messages"])
        # else:
        response = structured_llm.invoke([system_prompt] + state["messages"])

        _snapshot("exit")
        return {
            "messages": [response], 
            "model_call_count": current_count,
            }

    return model_call

