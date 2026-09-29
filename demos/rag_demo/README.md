# RAG Demo —— 检索增强生成

**证明能力：RAG（Retrieval-Augmented Generation）检索增强生成**

## 运行
```bash
# 在项目根 ai模拟作业/ 下
python demos/rag_demo/main.py "FDE 岗位主要看什么能力？"
# 不传参数则用内置示例问题
```

## 流程
1. 加载 `../kb` 知识库，切分建索引（见 `common/retrieval.py`）；
2. 对用户问题检索 top-k 相关片段；
3. 把片段拼进 Prompt，交给 DeepSeek 生成**带出处引用**的答案。

## 看点
输出分两段：先打印「检索到的 top-3 片段」（证明检索有效），再打印「大模型基于检索内容生成的答案」（证明增强+生成）。
答案中 `(来源：xxx)` 标明了每个结论的依据，直观体现 RAG 降低幻觉的核心价值。
