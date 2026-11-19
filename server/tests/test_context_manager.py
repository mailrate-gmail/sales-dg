import unittest

from app.models import Message, Session
from app.services.context_manager import ContextManager


def make_message(text: str, name: str = "客户") -> Message:
    return Message(
        id="m1",
        session_id="s1",
        speaker_name=name,
        text=text,
        created_at="2026-01-01T00:00:00",
    )


class TestRules(unittest.TestCase):
    def setUp(self):
        self.cm = ContextManager()

    def test_is_question(self):
        self.assertTrue(self.cm.is_question("这个怎么操作？"))
        self.assertTrue(self.cm.is_question("能否提供报价"))
        self.assertFalse(self.cm.is_question("我们下周安排演示"))

    def test_has_any(self):
        self.assertTrue(self.cm.has_any("系统效率低", ["效率", "瓶颈"]))
        self.assertFalse(self.cm.has_any("系统很好用", ["效率", "瓶颈"]))

    def test_add_unique_is_bounded(self):
        items: list[str] = []
        for i in range(40):
            self.cm.add_unique(items, f"item-{i}", limit=30)
        self.assertEqual(len(items), 30)
        self.assertIn("item-39", items)
        self.assertNotIn("item-0", items)


class TestUpdateMemory(unittest.TestCase):
    def setUp(self):
        self.cm = ContextManager()
        self.session = Session(id="s1", goal="推动调研", started_at="2026-01-01T00:00:00")

    def test_extracts_pain_point_and_question(self):
        from app.models import AgentMemory

        memory = AgentMemory(meeting_id="s1", goal="推动调研")
        actions = self.cm.update_memory(memory, make_message("线索跟进不及时，这会影响效率吗？"), save=False)
        types = {a.type for a in actions}
        self.assertIn("capture_question", types)
        self.assertIn("extract_pain_point", types)
        self.assertTrue(any("跟进不及时" in p for p in memory.pain_points))

    def test_short_term_context_bounded(self):
        from app.models import AgentMemory

        memory = AgentMemory(meeting_id="s1")
        for i in range(20):
            self.cm.update_memory(memory, make_message(f"第{i}条发言"), save=False)
        self.assertEqual(len(memory.short_term_context), 12)


if __name__ == "__main__":
    unittest.main()
