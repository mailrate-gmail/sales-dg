"""轻量 ASR 标点恢复。

FunASR streaming 与部分短音频 ASR 输出常缺少标点。本模块不依赖本地 LLM，
只做保守的规则修复：

- 已有句末标点则不重复追加；
- 按常见中文连接词补少量逗号；
- 按“标点敏感度”拆分过长分句；
- 根据疑问词补问号，否则补句号。

这不是完整的语义标点模型，但能显著改善实时会话区“整段无标点”的可读性，
且不会引入额外模型加载或网络延迟。
"""

import re


SENTENCE_END = "。！？!?；;"
ANY_PUNCTUATION = "，,。.!！?？；;：:、"
CLAUSE_SEPARATORS = "，,；;：:、"

QUESTION_MARKERS = [
    "吗",
    "呢",
    "么",
    "什么",
    "为什么",
    "怎么",
    "如何",
    "是否",
    "能否",
    "能不能",
    "可不可以",
    "有没有",
    "多少",
    "什么时候",
    "请问",
]

COMMA_MARKERS = [
    "但是",
    "不过",
    "所以",
    "因此",
    "然后",
    "另外",
    "同时",
    "而且",
    "如果",
    "其实",
    "比如",
    "例如",
    "也就是说",
    "一方面",
    "另一方面",
    "首先",
    "其次",
    "最后",
]

SPLIT_CANDIDATES = [
    "因为",
    "所以",
    "但是",
    "然后",
    "另外",
    "同时",
    "如果",
    "我们",
    "客户",
    "现在",
    "目前",
    "这个",
    "那个",
    "可以",
    "需要",
    "希望",
    "已经",
    "就是",
    "的话",
    "的时候",
    "之后",
]


def clamp_sensitivity(value: float | int | None) -> float:
    if value is None:
        return 0.6
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.6
    return max(0.0, min(1.0, number))


def max_clause_length(sensitivity: float) -> int:
    """敏感度越高，允许的无标点分句越短。"""
    sensitivity = clamp_sensitivity(sensitivity)
    if sensitivity <= 0.05:
        return 9999
    # 0.1 -> 44 左右；0.6 -> 28 左右；1.0 -> 16。
    return int(round(48 - sensitivity * 32))


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def has_punctuation(text: str) -> bool:
    return any(ch in ANY_PUNCTUATION for ch in text)


def is_question_like(text: str) -> bool:
    if "?" in text or "？" in text:
        return True
    return any(marker in text for marker in QUESTION_MARKERS)


def ensure_sentence_end(text: str) -> str:
    if not text:
        return text
    if text[-1] in SENTENCE_END:
        return text
    return text + ("？" if is_question_like(text) else "。")


def insert_commas(text: str, sensitivity: float = 0.6) -> str:
    """按连接词补少量中文逗号。

    只在连接词不是句首且前一个字符不是标点时插入，避免破坏已有标点。
    """
    if not text:
        return text

    result = text
    sensitivity = clamp_sensitivity(sensitivity)
    active_markers = COMMA_MARKERS
    if sensitivity < 0.35:
        # 低敏感度：只对最明显的转折/顺承词补逗号。
        active_markers = ["但是", "不过", "所以", "因此", "然后"]

    for marker in active_markers:
        # (?<![标点]) 表示 marker 前一个字符不是标点；(.+) 保证不是句首。
        result = re.sub(
            rf"(?<![{re.escape(ANY_PUNCTUATION)}])({re.escape(marker)})",
            rf"，\1",
            result,
        )
    return result.lstrip("，,")


def split_long_plain_clause(clause: str, limit: int) -> str:
    if limit <= 0 or len(clause) <= limit:
        return clause

    parts: list[str] = []
    rest = clause
    while len(rest) > limit:
        window_start = max(8, limit - 8)
        window_end = min(len(rest), limit + 8)
        split_at = -1
        for marker in SPLIT_CANDIDATES:
            idx = rest.rfind(marker, window_start, window_end)
            if idx > 6:
                split_at = idx
                break
        if split_at <= 6:
            split_at = limit
        parts.append(rest[:split_at])
        rest = rest[split_at:]
    if rest:
        parts.append(rest)
    return "，".join(part for part in parts if part)


def split_long_clauses(text: str, sensitivity: float = 0.6) -> str:
    limit = max_clause_length(sensitivity)
    if limit > 1000:
        return text

    result: list[str] = []
    current: list[str] = []
    for char in text:
        if char in ANY_PUNCTUATION:
            if current:
                result.append(split_long_plain_clause("".join(current), limit))
                current = []
            result.append(char)
        else:
            current.append(char)
    if current:
        result.append(split_long_plain_clause("".join(current), limit))
    return "".join(result)


def restore_punctuation(text: str, sensitivity: float = 0.6) -> str:
    """给 ASR final 文本补充基础中文标点。

    `sensitivity` 范围 0~1：
    - 0：极保守，基本只补句末标点；
    - 0.6：默认，连接词补逗号，较长分句补逗号；
    - 1：更激进，更短分句也会补逗号。
    """
    text = normalize_spaces(text)
    if not text:
        return ""

    sensitivity = clamp_sensitivity(sensitivity)
    if sensitivity > 0.05 and (not has_punctuation(text) or sensitivity >= 0.75):
        text = insert_commas(text, sensitivity)
    text = split_long_clauses(text, sensitivity)
    return ensure_sentence_end(text)
