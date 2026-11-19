"""流式 ASR 文本合并工具。

FunASR 的 partial 结果是"截至当前的完整文本"，需与已累积文本做去重拼接，
避免叠字。独立于 main.py 便于单元测试。
"""


def merge_stream_text(current: str, incoming: str) -> str:
    incoming = incoming.strip()
    if not incoming:
        return current
    if not current:
        return incoming
    if incoming == current or current.endswith(incoming):
        return current
    if incoming.startswith(current):
        return incoming

    max_overlap = min(len(current), len(incoming))
    # 至少 2 个字符才算重叠，避免把合法的中文叠字/重复误删。
    for size in range(max_overlap, 1, -1):
        if current.endswith(incoming[:size]):
            return current + incoming[size:]
    return current + incoming
