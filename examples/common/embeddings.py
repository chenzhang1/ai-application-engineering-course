# EX-00-00 | examples/common/embeddings.py | 全书共享 Embedding 客户端（Mock/Real 双模式）
"""全书统一的 Embedding 基座 —— ch25 首次使用，第六部分 RAG 直接复用。

接口摘要
=========
    from examples.common.embeddings import get_embedder, cosine_similarity
    emb = get_embedder()                      # LLM_MODE=mock(默认)/real
    vecs = emb.embed(["手机充值", "电话卡"])   # list[list[float]]，均 L2 归一化
    vec = emb.embed_one("披萨")                # 单条
    sim = cosine_similarity(vecs[0], vecs[1])  # float，[-1, 1]

MockEmbedder（确定性本地向量，"相似文本 → 相似向量"）
    - 内置一个小型"概念词典"（通讯/食物/天气/订单/设备/运动 6 簇关键词）：
      命中同一概念的词映射到同一方向——等价于把"预训练词向量的语义知识"
      极简化成十几行表格，这是 Mock 能表现出"手机≈电话、手机≠披萨"的原因；
    - 未命中的片段按 2 字符切片做 sha256 哈希映射到固定维度（词袋思想），
      哈希只保证"确定性"，不携带语义——不同概念的未知词近似正交；
    - 向量做 L2 归一化，点积即余弦相似度。
    类比边界：真实 embedding 模型的语义来自大规模语料训练，同概念的两个词
    相近但不重合、还能表达"程度"与"类比"关系；Mock 只有"命中即相等"的粗粒度语义，
    换了词典外的词就不会有相似性——教学够用，勿当真模型。

RealEmbedder（openai==3.35.1，签名已核实）
    client.embeddings.create(input=..., model=...) 参数包含：
    input, model, dimensions, encoding_format, user（2026-10-19 inspect 核实）。
    缺 OPENAI_API_KEY 抛带中文指引的 RuntimeError。

红线：mock 模式绝不发起任何网络请求；real 模式未在本沙箱实际调用（无 Key），
转换代码按 SDK 类型静态核实，教材中如实标注。
"""
from __future__ import annotations

import hashlib
import os
import re

import numpy as np

__all__ = ["MockEmbedder", "RealEmbedder", "get_embedder", "cosine_similarity"]

# 默认维度：前 6 维留给概念簇（一词一方向），其余给哈希切片
_DEFAULT_DIM = 64
_CONCEPT_DIMS = 6

# 小型概念词典：仅服务于教学演示的"语义"，非任何真实模型的产物
_CONCEPTS: dict[str, list[str]] = {
    "通讯": ["手机", "电话", "通话", "短信", "拨打", "号码", "话费", "phone", "mobile", "call"],
    "食物": ["披萨", "汉堡", "外卖", "餐厅", "菜单", "面条", "米饭", "pizza", "burger", "food"],
    "天气": ["天气", "下雨", "晴天", "温度", "雨伞", "weather", "rain", "sunny"],
    "订单": ["订单", "支付", "退款", "发票", "物流", "快递", "order", "pay", "refund"],
    "设备": ["电脑", "笔记本", "屏幕", "键盘", "电池", "laptop", "screen", "keyboard"],
    "运动": ["足球", "篮球", "比赛", "球场", "跑步", "sport", "football", "basketball"],
}
_CONCEPT_LIST = list(_CONCEPTS.items())  # 概念 i 占据第 i 维

_ASCII_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")


def _hash_dim(token: str) -> int:
    """sha256(token) → [6, dim) 里的一个维度（确定性，无语义）。"""
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return _CONCEPT_DIMS + (int.from_bytes(digest[:8], "big") % (_DEFAULT_DIM - _CONCEPT_DIMS))


def _hash_sign(token: str) -> float:
    """用哈希另一比特决定正负号，降低词袋全为正带来的"跷跷板"偏差。"""
    digest = hashlib.sha256(("sign:" + token).encode("utf-8")).digest()
    return 1.0 if digest[0] % 2 == 0 else -1.0


def _tokenize_rest(text: str) -> list[str]:
    """概念未命中部分的粗切词：ASCII 单词 + 中文 2-gram。"""
    tokens: list[str] = list(_ASCII_WORD_RE.findall(text))
    for run in _CJK_RUN_RE.findall(text):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


class MockEmbedder:
    """确定性本地向量器：概念词典 + 哈希词袋 + L2 归一化。"""

    def __init__(self, dim: int = _DEFAULT_DIM) -> None:
        if dim < _CONCEPT_DIMS + 4:
            raise ValueError(f"dim 至少为 {_CONCEPT_DIMS + 4}（概念簇 + 哈希空间），收到 {dim}")
        self.dim = dim
        self.kind = f"mock:concept-hash dim={dim}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_one(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float64)
        lowered = text.lower()
        rest = lowered
        # 1) 概念词典命中：同一概念 → 同一维度 +1（语义来源）
        for idx, (_, keywords) in enumerate(_CONCEPT_LIST):
            for kw in keywords:
                kw = kw.strip()
                if kw and kw in lowered:
                    vec[idx] += 1.0
                    rest = rest.replace(kw, " ")
        # 2) 其余片段：哈希词袋（确定性，无语义）
        for token in _tokenize_rest(rest):
            if len(token) < 2:  # 单字噪声过多，跳过（教学向量的简化取舍）
                continue
            vec[_hash_dim(token)] += _hash_sign(token) * 0.5
        # 3) L2 归一化：点积即余弦相似度
        norm = float(np.linalg.norm(vec))
        if norm == 0.0:
            return vec.tolist()
        return (vec / norm).tolist()


class RealEmbedder:
    """openai 3.35.1 真实 embedding 客户端（create 签名已核实；沙箱无 Key 未实调）。"""

    def __init__(self, model: str = "text-embedding-3-small", base_url: str | None = None,
                 api_key: str | None = None, timeout: float = 60.0) -> None:
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "real 模式需要 OPENAI_API_KEY，但环境变量未设置。三种解决方式：\n"
                "  1) export OPENAI_API_KEY=sk-... 后重试；\n"
                "  2) 兼容接口服务：设置 OPENAI_BASE_URL=https://<厂商域名>/v1（以厂商文档为准）；\n"
                "  3) 没有Key就保持 LLM_MODE=mock（默认，MockEmbedder 离线可跑）。"
            )
        from openai import OpenAI

        self.model = model
        self.kind = f"real:openai model={model}"
        self._client = OpenAI(api_key=api_key,
                              base_url=base_url or os.environ.get("OPENAI_BASE_URL") or None,
                              timeout=timeout)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.embeddings.create(input=texts, model=self.model)
        data = sorted(resp.data, key=lambda d: d.index)  # 按输入顺序对齐
        return [list(d.embedding) for d in data]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


def cosine_similarity(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    """余弦相似度 = 点积 / (|a||b|)；零向量按 0.0 处理（约定，避免除零异常）。"""
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def get_embedder() -> MockEmbedder | RealEmbedder:
    """按 LLM_MODE 返回 embedder：mock（默认）/ real（缺 Key 报中文指引）。"""
    mode = os.environ.get("LLM_MODE", "mock").strip().lower()
    if mode == "mock":
        return MockEmbedder()
    if mode == "real":
        return RealEmbedder()
    raise ValueError(f"LLM_MODE 只能是 mock 或 real，当前为 {mode!r}")
