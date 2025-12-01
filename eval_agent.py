from langsmith import Client
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import ToolNode
from MyNameTemplate import app  # 导入你的 LangGraph 应用
import json

# 1. 定义数据集 (实际使用中通常在 LangSmith 网页端管理，这里为了演示写在代码里)
examples = [
    {
        "inputs": {"text": "帮我用这张参考图生成视频: http://fake.url/img.jpg"},
        "expected_tool": "first_frame_to_video_by_kie_sora2_create_task"
    },
    {
        "inputs": {"text": "查看一下任务 id-12345 的状态"},
        "expected_tool": "get_ppio_task_status" # 确保它优先调用新的 PPIO 查询
    }
]

# 2. 定义目标函数 (运行 Agent)
def target_agent(inputs: dict):
    # 模拟用户输入
    state = {"messages": [HumanMessage(content=inputs["text"])]}
    
    # 运行 Graph，拿到最后的结果
    # 注意：这里我们可能不想真的调用 API (费钱)，通常会 Mock 工具，
    # 或者只运行到 'our_agent' 节点结束，看它想调用什么工具
    
    # 这里简单演示，运行一步看看
    result = app.invoke(state)
    last_message = result["messages"][-1]
    
    # 提取它试图调用的工具
    tool_calls = getattr(last_message, "tool_calls", [])
    called_tools = [t["name"] for t in tool_calls]
    
    return {"called_tools": called_tools, "response": last_message.content}

# 3. 定义评估逻辑 (自定义 Evaluator)
def tool_selection_evaluator(run, example):
    # 获取预测结果
    predicted_tools = run.outputs.get("called_tools", [])
    # 获取预期结果
    expected_tool = example.outputs.get("expected_tool")
    
    # 判定逻辑
    score = 1 if expected_tool in predicted_tools else 0
    
    return {
        "key": "tool_selection_accuracy",
        "score": score,
        "comment": f"Expected {expected_tool}, got {predicted_tools}"
    }

# 4. 运行评估 (使用 LangSmith SDK)
# 这一步通常需要配置 LangSmith API Key
# client = Client()
# client.evaluate(
#     target_agent,
#     data=examples, # 这里需要适配 Dataset 格式
#     evaluators=[tool_selection_evaluator]
# )