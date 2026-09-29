# Mockwise Demos —— RAG / MCP / Agent 能力实证

本目录是 **简历声明的可运行证据**：证明「大模型应用：Prompt 工程、RAG、Function Calling、MCP、Agent 编排（均有 demo 支撑）」中的 RAG / MCP / Agent 三项已真正跑通，而非只写在简历上。

> 关联的 Mockwise 主项目：../backend（FastAPI + DeepSeek + 讯飞 ASR，已端到端交付）。

---

## 目录结构

```
demos/
├─ common/            # 三个 demo 共用的底层能力
│  ├─ config.py      # 读取 backend/.env 的 DeepSeek 凭证（不写死、不提交）
│  ├─ llm.py         # DeepSeek 客户端封装（chat / chat_json / chat_with_tools）
│  └─ retrieval.py   # 轻量检索器（RAG 的「检索」环节，稀疏 TF-IDF）
├─ kb/               # 共享知识库（5 篇 Markdown，面试/FDE/大模型常识）
├─ rag_demo/         # RAG：检索增强生成
├─ mcp_demo/         # MCP：标准 Model Context Protocol 服务端 + 客户端
└─ agent_demo/       # Agent：基于 function calling 的多步自主代理
```

---

## 环境准备

```bash
pip install openai python-dotenv "mcp<2"
```

凭证：demo 会自动读取 `../backend/.env` 里的 `DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL`，
**密钥不会写进任何 demo 文件，也不会被提交**。也可直接设置同名环境变量。

运行位置：在项目根目录 `ai模拟作业/` 下执行（脚本内部用相对路径定位 `common/` 与 `kb/`）。

---

## 三个 Demo 与简历的对应关系

| 简历能力项 | Demo | 运行命令 | 证明点 |
|---|---|---|---|
| RAG 检索增强生成 | `rag_demo` | `python demos/rag_demo/main.py "你的问题"` | 检索 top-k → 拼 Prompt → 大模型生成带出处引用的答案 |
| MCP（模型上下文协议） | `mcp_demo` | `python demos/mcp_demo/client.py` | 服务端用官方 MCP SDK 暴露工具，客户端按协议 stdio 列工具/调用 |
| Agent 编排 / Function Calling | `agent_demo` | `python demos/agent_demo/main.py` | 模型自主决定调用哪些工具、按什么顺序，多步推理后给出答案 |

---

## 关于「检索」实现

为做到**零模型下载、可离线演示**，RAG / MCP / Agent 共享的检索器采用字符 bigram + TF-IDF 的**稀疏向量**。
这足以演示「检索 → 增强 → 生成」的完整链路，也是真实可解释的实现。
生产环境会把 `common/retrieval.py` 中的 `Retriever` 替换为**稠密向量**（如 `bge-small-zh` / `m3e`）+ **向量库**（Chroma / FAISS / Milvus），
接口（`search(query, k)`）保持不变，上层 demo 无需改动。

---

## 一键自检

```bash
python demos/rag_demo/main.py "RAG 是什么"          # 需要联网调用大模型
python demos/mcp_demo/client.py                     # 纯本地，无需大模型
python demos/agent_demo/main.py                     # 需要联网调用大模型
```
