from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.models import AgentDecision, AgentMemory, Message, Session
from app.services.storage import storage


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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

    def update_with_message(self, session: Session, message: Message) -> list[AgentDecision]:
        memory = self.load_memory(session.id, session.goal)
        actions = self.update_memory(memory, message, save=False)
        memory.decisions = (memory.decisions + actions)[-80:]
        self.save_memory(memory)
        return actions

    def update_memory(self, memory: AgentMemory, message: Message, save: bool = True) -> list[AgentDecision]:
        text = message.text.strip()
        if not text:
            return []

        memory.short_term_context = (memory.short_term_context + [f"{message.speaker_name}: {text}"])[-12:]
        actions: list[AgentDecision] = []

        if self.is_question(text):
            self.add_unique(memory.questions, f"{message.speaker_name}: {text}")
            actions.append(self.decision("capture_question", "识别到客户/参会人提出问题", text, message))

        if self.has_any(text, ["痛点", "问题", "困难", "瓶颈", "不及时", "影响", "效率低", "卡点", "缺少", "无法"]):
            self.add_unique(memory.pain_points, f"{message.speaker_name}: {text}")
            actions.append(self.decision("extract_pain_point", "发言中包含痛点或业务问题", text, message))

        if self.has_any(text, ["风险", "担心", "顾虑", "预算", "价格", "太贵", "延期", "不确定", "合规", "安全"]):
            self.add_unique(memory.risks, f"{message.speaker_name}: {text}")
            actions.append(self.decision("mark_risk", "发言中包含风险、异议或顾虑", text, message))

        if self.has_any(text, ["我们会", "我方会", "承诺", "负责", "提供", "安排", "发给", "同步", "确认后"]):
            self.add_unique(memory.commitments, f"{message.speaker_name}: {text}")
            actions.append(self.decision("record_commitment", "识别到我方承诺或交付事项", text, message))

        if self.has_any(text, ["下一步", "需要", "请", "麻烦", "跟进", "确认", "安排", "待办", "后续"]):
            self.add_unique(memory.todos, f"{message.speaker_name}: {text}")
            actions.append(self.decision("record_todo", "识别到后续行动或待办", text, message))

        if not actions:
            actions.append(self.decision("ignore", "未触发结构化记忆规则，仅更新短期上下文", text, message))

        if save:
            memory.decisions = (memory.decisions + actions)[-80:]
            self.save_memory(memory)
        return actions

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
        if "?" in text or "？" in text:
            return True
        return self.has_any(text, ["吗", "什么", "为什么", "怎么", "如何", "是否", "能否", "有没有", "多少", "什么时候", "请问"])


context_manager = ContextManager()
