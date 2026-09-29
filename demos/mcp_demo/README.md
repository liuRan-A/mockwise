# MCP Demo —— 标准 Model Context Protocol

**证明能力：MCP（Model Context Protocol，模型上下文协议）**

## 运行
```bash
# 在项目根 ai模拟作业/ 下（纯本地，无需调用大模型）
python demos/mcp_demo/client.py
```

## 说明
- `server.py`：用官方 **mcp SDK** 的 `FastMCP` 把能力注册为 tool（知识检索 / 计算 / 面试技巧）；
- `client.py`：通过 **stdio** 拉起服务端，按 MCP 协议 `initialize → list_tools → call_tool`。

## 看点
这正是 MCP 的标准形态：服务端把工具以统一协议暴露，任意兼容客户端都能接入，
大模型/应用无需为每个工具单独写对接代码。本 demo 的 `search_knowledge` 工具与 RAG demo 共用同一套检索器。
