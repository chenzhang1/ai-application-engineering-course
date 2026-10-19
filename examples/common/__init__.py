"""examples.common —— 全书共享的 LLM 基座（第四部分 ch21~25 创建，后续章节统一 import 使用）。

模块：
- llm_client：ChatResult / MockLLM / RealLLM / chat_structured / count_tokens
- embeddings：MockEmbedder / RealEmbedder / cosine_similarity

双模式约定（全书统一）：
- LLM_MODE=mock（默认）：完全离线，不发起任何网络请求；
- LLM_MODE=real：openai SDK 真实调用，需 OPENAI_API_KEY（兼容接口可设 OPENAI_BASE_URL）。
"""
