# -*- coding: utf-8 -*-
"""
轻量检索器（RAG 的「检索」环节）。
说明：本 demo 用「字符 bigram + 词频」的稀疏向量（TF-IDF）做检索，
     零模型下载、可离线跑，足以演示 RAG 的「检索 -> 增强 -> 生成」全链路。
     生产环境会把这里换成稠密向量（如 bge-small-zh / m3e）+ 向量库（Chroma/FAISS/Milvus）。
"""
from __future__ import annotations
import math
import re
from dataclasses import dataclass
from pathlib import Path


_STOP = set(
    "的 了 是 在 我 有 和 就 不 人 都 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 那 吗 呢 吧 啊".split()
)


def tokenize(text: str) -> list[str]:
    """中文按字符 bigram，英文/数字按词，转小写。"""
    text = text or ""
    toks: list[str] = []
    for m in re.findall(r"[a-zA-Z0-9]+", text):
        toks.append(m.lower())
    cjk = re.sub(r"[a-zA-Z0-9]+", "", text)
    cjk = re.sub(r"\s+", "", cjk)
    for i in range(len(cjk) - 1):
        bg = cjk[i:i + 2]
        if bg not in _STOP:
            toks.append(bg)
    if cjk:
        toks.append(cjk[-1])
    return toks


def split_chunks(text: str, max_len: int = 240) -> list[str]:
    """按空行/句号切分，过长再按句切。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    for p in paras:
        if len(p) <= max_len:
            chunks.append(p)
            continue
        for sent in re.split(r"(?<=[。！？；])", p):
            sent = sent.strip()
            if not sent:
                continue
            if len(sent) <= max_len:
                chunks.append(sent)
            else:
                chunks.append(sent[:max_len])
    return chunks


@dataclass
class Hit:
    source: str
    text: str
    score: float


class Retriever:
    def __init__(self, docs: list[dict]):
        """
        docs: [{"source": str, "text": str}, ...]
        """
        raw: list[tuple[str, str, dict]] = []
        df: dict[str, int] = {}
        for d in docs:
            for ch in split_chunks(d["text"]):
                tf: dict[str, int] = {}
                for t in tokenize(ch):
                    tf[t] = tf.get(t, 0) + 1
                raw.append((d["source"], ch, tf))
                for t in tf:
                    df[t] = df.get(t, 0) + 1
        n = len(raw)
        self._vectors: list[tuple[str, str, dict, float]] = []
        for src, ch, tf in raw:
            vec = {}
            for t, c in tf.items():
                idf = math.log((n + 1) / (df[t] + 1)) + 1
                vec[t] = (1 + math.log(c)) * idf
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self._vectors.append((src, ch, vec, norm))

    def search(self, query: str, k: int = 3) -> list[Hit]:
        qv: dict[str, int] = {}
        for t in tokenize(query):
            qv[t] = qv.get(t, 0) + 1
        qnorm = math.sqrt(sum(c * c for c in qv.values())) or 1.0
        scored = []
        for src, ch, vec, norm in self._vectors:
            dot = sum(vec.get(t, 0.0) * qv[t] for t in qv)
            sim = dot / (norm * qnorm) if norm and qnorm else 0.0
            if sim > 0:
                scored.append((sim, src, ch))
        scored.sort(reverse=True)
        return [Hit(source=s, text=t, score=sim) for sim, s, t in scored[:k]]


def load_docs(folder: str | Path) -> list[dict]:
    """读取 data 目录下所有 .md / .txt 作为知识库文档。"""
    folder = Path(folder)
    docs = []
    for p in sorted(folder.glob("**/*")):
        if p.suffix.lower() in (".md", ".txt"):
            docs.append({"source": p.stem, "text": p.read_text(encoding="utf-8")})
    return docs
