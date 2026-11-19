"""配置对外视图与安全处理。

将 API Key 的掩码逻辑集中在这里，便于复用与单元测试，且不引入 ASR 等重型依赖。
"""

from app.models import ModelConfig
from app.services.runtime_config import runtime_config

MASKED_API_KEY = "__MASKED__"


def mask_config(config: ModelConfig) -> ModelConfig:
    """返回对外安全的配置副本：隐藏已保存的 API Key，避免明文回显。"""
    if config.llm_api_key:
        return config.model_copy(update={"llm_api_key": MASKED_API_KEY})
    return config


def unmask_api_key(payload: ModelConfig) -> ModelConfig:
    """PUT/测试时若收到掩码哨兵，则用已保存的真实 key 还原，避免把掩码写入配置。"""
    if payload.llm_api_key == MASKED_API_KEY:
        real_key = runtime_config.get().llm_api_key
        return payload.model_copy(update={"llm_api_key": real_key})
    return payload
