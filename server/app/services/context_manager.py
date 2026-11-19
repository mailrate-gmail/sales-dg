"""本地会话分析与 Agent 上下文管理。

全部分析基于关键词规则，不依赖本地 LLM。主要职责：
- 对单条 ASR 发言打标签，判断是否需要触发 AI 回复；
- 说明/示例/解释等非问题内容只进入上下文摘要，不触发回复；
- 维护结构化记忆，并提供给远程 LLM 的上下文拼装方法。
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.models import AgentDecision, AgentMemory, Message, Session, UtteranceAnalysis
from app.services.storage import storage


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# 问题判定词。强信号直接判为问题；弱信号需在没有“说明性”标记时才判为问题。
QUESTION_STRONG = [
    "?", "？", "吗", "请问", "能否", "是否", "能不能", "可不可以",
    "你们能", "你们支持", "贵司", "报价多少", "多少钱", "周期多久",
]
QUESTION_WEAK = ["什么", "怎么", "如何", "为什么", "多少", "什么时候", "有没有", "呢"]
# 这些表达表示“没什么问题”，用于抑制弱信号的误判。
QUESTION_NEGATED = ["没什么", "没问题", "没有问题", "不是什么"]
# 说明/示例/解释/背景标记。
CONTEXT_MARKERS = [
    "比如", "例如", "举例", "比如说", "例如说", "就是说", "也就是说",
    "我们的流程是", "目前的流程是", "目前的情况是", "现在主要是", "现状是",
    "我介绍一下", "我说明一下", "我解释一下", "一般来说", "通常", "之前", "以前",
]
# 明确的事实/确认表达，作为关键事实保留。
FACT_MARKERS = [
    "我们目前", "目前我们", "我们现在", "现在我们", "现状是", "目前已经",
    "已经确认", "确认使用", "我们采用", "目标是", "主要是", "主要问题",
    "客户是", "我们这边",
]
PAIN_KEYWORDS = ["痛点", "问题", "困难", "瓶颈", "不及时", "影响", "效率低", "卡点", "缺少", "无法"]
RISK_KEYWORDS = ["风险", "担心", "顾虑", "预算", "价格", "太贵", "延期", "不确定", "合规", "安全"]
COMMITMENT_KEYWORDS = ["我们会", "我方会", "承诺", "负责", "提供", "安排", "发给", "同步", "确认后"]
TODO_KEYWORDS = ["下一步", "需要", "请", "麻烦", "跟进", "确认", "安排", "待办", "后续"]

LABEL_WEIGHTS = {
    "question": 3,
    "key_fact": 2,
    "pain_point": 2,
    "risk": 2,
    "commitment": 2,
    "todo": 1,
    "context_note": 1,
}


class ContextManager:
    def memory_file(self, meeting_id: str) -> Path:
        return storage.sessions_dir / f"{meeting_id}.memory.json"

    def load_memory(self, meeting_id: str, goal: str = "") -> AgentMemory:
        path = self.memory_file(meeting_id)
        data = storage.read_json(path)
        if data:
            return AgentMemory(**data)
        return AgentMemory(meeting_id=meeting_id, goal=goal, updated_at=now_iso())

    def save_memory(self, memory: AgentMemory) -> AgentMemory:
        memory.updated_at = now_iso()
        storage.write_json(self.memory_file(memory.meeting_id), memory.model_dump())
        return memory

    def rebuild(self, session: Session) -> AgentMemory:
        memory = AgentMemory(meeting_id=session.id, goal=session.goal, updated_at=now_iso())
        actions: list[AgentDecision] = []
        for message in session.messages:
            actions.extend(self.update_memory(memory, message, save=False))
        memory.decisions = actions[-80:]
        return self.save_memory(memory)

    def update_with_message(
        self,
        session: Session,
        message: Message,
        analysis: UtteranceAnalysis | None = None,
    ) -> list[AgentDecision]:
        memory = self.load_memory(session.id, session.goal)
        actions = self.update_memory(memory, message, save=False, analysis=analysis)
        memory.decisions = (memory.decisions + actions)[-80:]
        self.save_memory(memory)
        return actions

    def update_memory(
        self,
        memory: AgentMemory,
        message: Message,
        save: bool = True,
        analysis: UtteranceAnalysis | None = None,
    ) -> list[AgentDecision]:
        text = message.text.strip()
        if not text:
            return []

        analysis = analysis or self.analyze_utterance(text)
        labels = set(analysis.labels)

        memory.short_term_context = (memory.short_term_context + [f"{message.speaker_name}: {text}"])[-12:]
        actions: list[AgentDecision] = []

        if "question" in labels:
            self.add_unique(memory.questions, f"{message.speaker_name}: {text}")
            actions.append(self.decision("capture_question", "识别到问题或明确请求", text, message))

        if "context_note" in labels:
            self.add_unique(memory.context_notes, f"{message.speaker_name}: {text}")
        if "key_fact" in labels:
            self.add_unique(memory.key_facts, f"{message.speaker_name}: {text}")

        if "pain_point" in labels:
            self.add_unique(memory.pain_points, f"{message.speaker_name}: {text}")
            actions.append(self.decision("extract_pain_point", "发言中包含痛点或业务问题", text, message))

        if "risk" in labels:
            self.add_unique(memory.risks, f"{message.speaker_name}: {text}")
            actions.append(self.decision("mark_risk", "发言中包含风险、异议或顾虑", text, message))

        if "commitment" in labels:
            self.add_unique(memory.commitments, f"{message.speaker_name}: {text}")
            actions.append(self.decision("record_commitment", "识别到我方承诺或交付事项", text, message))

        if "todo" in labels:
            self.add_unique(memory.todos, f"{message.speaker_name}: {text}")
            actions.append(self.decision("record_todo", "识别到后续行动或待办", text, message))

        if not actions:
            if "context_note" in labels:
                reason = "说明/示例/背景内容，仅纳入上下文参考，不触发 AI 回复"
            else:
                reason = "未触发结构化记忆规则，仅更新短期上下文"
            actions.append(self.decision("ignore", reason, text, message))

        if save:
            memory.decisions = (memory.decisions + actions)[-80:]
            self.save_memory(memory)
        return actions

    def analyze_utterance(self, text: str) -> UtteranceAnalysis:
        """本地规则分析单条发言，判断是否触发 AI 回复并标注语义标签。

        说明性内容（示例、解释、背景）只打 context_note，不触发回复；
        问题或明确请求才设置 should_reply=True。ASR 文本可能有误，判断保持保守。
        """
        text = (text or "").strip()
        if not text:
            return UtteranceAnalysis()

        has_strong = self.has_any(text, QUESTION_STRONG)
        has_weak = self.has_any(text, QUESTION_WEAK)
        has_context = self.has_any(text, CONTEXT_MARKERS)
        has_negated = self.has_any(text, QUESTION_NEGATED)

        is_question = has_strong or (has_weak and not has_context and not has_negated)

        labels: list[str] = []
        if is_question:
            labels.append("question")
        else:
            labels.append("context_note")
        if has_context and "context_note" not in labels:
            labels.append("context_note")
        if self.has_any(text, FACT_MARKERS):
            labels.append("key_fact")
        # “没什么问题/没问题”里的“问题”不是痛点， negation 命中时排除该词。
        pain_keywords = [k for k in PAIN_KEYWORDS if not (has_negated and k == "问题")]
        if self.has_any(text, pain_keywords):
            labels.append("pain_point")
        if self.has_any(text, RISK_KEYWORDS):
            labels.append("risk")
        # 疑问句中出现的“提供/安排”等是请求，不是我方承诺。
        if not is_question and self.has_any(text, COMMITMENT_KEYWORDS):
            labels.append("commitment")
        if self.has_any(text, TODO_KEYWORDS):
            labels.append("todo")

        importance = sum(LABEL_WEIGHTS.get(label, 1) for label in labels)
        if is_question:
            reason = "识别为问题或明确请求，触发 AI 建议回复"
        else:
            reason = "说明/示例/背景等非问题内容，仅作为上下文参考，不触发 AI 回复"

        return UtteranceAnalysis(
            labels=labels,
            should_reply=is_question,
            importance=importance,
            reason=reason,
        )

    def should_trigger_reply(self, speaker_need_reply: bool, analysis: UtteranceAnalysis) -> bool:
        """AI 回复触发规则：指定参会人 + 本地判断为问题/明确请求。"""
        return bool(speaker_need_reply and analysis.should_reply)

    def format_context_for_llm(self, memory: AgentMemory) -> str:
        """将结构化记忆拼成供远程 LLM 使用的文本。

        说明性内容单独列出并标注“非问题”，确保它被当作背景参考，而不是当前提问。
        """
        sections: list[str] = []
        if memory.goal:
            sections.append(f"会晤目标：{memory.goal}")

        def add(title: str, items: list[str], limit: int = 10) -> None:
            if not items:
                return
            lines = "\n".join(f"- {item}" for item in items[-limit:])
            sections.append(f"{title}：\n{lines}")

        add("已确认事实/背景", memory.key_facts)
        add("背景说明（非问题，仅供参考）", memory.context_notes)
        add("客户痛点", memory.pain_points)
        add("风险与顾虑", memory.risks)
        add("我方承诺", memory.commitments)
        add("待办事项", memory.todos)
        add("已捕获问题", memory.questions)
        return "\n\n".join(sections)

    def decision(self, action_type: str, reason: str, content: str, message: Message) -> AgentDecision:
        return AgentDecision(
            id=f"decision_{uuid4().hex[:10]}",
            type=action_type,  # type: ignore[arg-type]
            reason=reason,
            content=content,
            message_id=message.id,
            speaker_name=message.speaker_name,
            created_at=now_iso(),
        )

    def add_unique(self, items: list[str], value: str, limit: int = 30) -> None:
        if value not in items:
            items.append(value)
        del items[:-limit]

    def has_any(self, text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    def is_question(self, text: str) -> bool:
        """兼容旧调用的简化问题判断。"""
        return self.analyze_utterance(text).should_reply


context_manager = ContextManager()
