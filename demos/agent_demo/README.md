# Agent Demo —— 工具调用型自主代理

**证明能力：Agent 任务拆解与工作流编排（基于 Function Calling）**

## 运行
```bash
# 在项目根 ai模拟作业/ 下（需配置 DEEPSEEK_API_KEY）
python demos/agent_demo/main.py
# 也可传自定义目标：python demos/agent_demo/main.py "你的问题"
```

## 说明
- `tools.py`：声明工具（OpenAI function calling 格式）+ 本地执行器 `dispatch()`；
- `main.py`：ReAct 思路循环——模型根据目标**自主决定调用哪些工具、按什么顺序**，
  执行后把结果回传，直到得出最终答案。

## 看点
输出会打印每一步模型「决定调用哪个工具、参数、工具返回」，最后给出综合答案。
例如内置目标会先后调用 `knowledge_search`（查岗位要求、查答题框架）和 `calc`（4 个月≈120 天），
体现了「模型=大脑、工具=手脚」的 Agent 编排本质。
