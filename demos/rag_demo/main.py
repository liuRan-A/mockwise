# -*- coding: utf-8 -*-
"""
RAG Demo：检索增强生成
流程：加载知识库 -> 切分建索引 -> 检索 top-k -> 拼进 Prompt -> 大模型生成带引用的答案。

运行（在项目根 ai模拟作业/ 下）：
    python demos/rag_demo/main.py "无领导小组讨论怎么拿高分"
不传参数则用内置示例问题。
"""
from __future__ import annotations
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "common"))

import config
from retrieval import Retriever, load_docs
from llm import chat


KB_DIR = os.path.join(_HERE, "..", "kb")
DEFAULT_Q = "FDE 岗位主要看什么能力？我一段门店接管的经历能作为证据吗？"


def answer(query: str, k: int = 3) -> dict:
    docs = load_docs(KB_DIR)
    retriever = Retriever(docs)
    hits = retriever.search(query, k=k)

    context = "\n\n".join(
        f"[资料 {i+1}] 来源：{h.source}\n{h.text}" for i, h in enumerate(hits)
    )
    system = (
        "你是一名面试辅导助手。只能依据[资料]中的内容回答问题，"
        "不要编造资料之外的信息。回答时在每个关键结论后用(来源：xxx)标注出处。"
    )
    user = f"[资料]\n{context}\n\n[问题]\n{query}\n\n请给出简洁、有依据的答案。"

    msg = chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
    return {"query": query, "hits": hits, "answer": msg}


def main() -> None:
    if not config.has_key():
        print("[跳过] 未配置 DEEPSEEK_API_KEY，无法调用大模型。但检索环节仍可离线验证（见下方 top-k 片段）。")
    query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_Q
    print(f"\n问题：{query}\n")

    docs = load_docs(KB_DIR)
    retriever = Retriever(docs)
    hits = retriever.search(query, k=3)
    print("=== 检索到的 top-3 片段（RAG 的『检索』环节）===")
    for i, h in enumerate(hits):
        print(f"[{i+1}] 来源：{h.source}  相似度：{h.score:.3f}")
        print(f"    {h.text[:80]}...")

    if not config.has_key():
        return
    print("\n=== 大模型基于检索内容生成的答案（RAG 的『增强+生成』环节）===")
    res = answer(query, k=3)
    print(res["answer"])


if __name__ == "__main__":
    main()
