from state.schemas import AgentState

def should_continue(state: AgentState): 
    """判断是否继续调用工具"""
    messages = state["messages"]
    last_message = messages[-1]
    if hasattr(last_message, 'tool_calls') and not last_message.tool_calls: 
        return "end"
    else:
        return "continue"

