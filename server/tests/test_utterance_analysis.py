import unittest

from app.models import AgentMemory
from app.services.context_manager import ContextManager


def make_memory() -> AgentMemory:
    return AgentMemory(meeting_id="s1", goal="推动 CRM 集成方案确认")


class TestAnalyzeUtterance(unittest.TestCase):
    def setUp(self):
        self.cm = ContextManager()

    def test_question_triggers_reply(self):
        result = self.cm.analyze_utterance("你们这个系统能不能和我们 CRM 打通？")
        self.assertTrue(result.should_reply)
        self.assertIn("question", result.labels)
        self.assertIn("触发 AI 建议回复", result.reason)

    def test_plain_question_without_marker_triggers(self):
        result = self.cm.analyze_utterance("能否提供一份报价单")
        self.assertTrue(result.should_reply)

    def test_explanation_does_not_trigger_reply(self):
        result = self.cm.analyze_utterance("比如我们现在客户线索进来之后，销售一般要两三天才会跟进")
        self.assertFalse(result.should_reply)
        self.assertIn("context_note", result.labels)
        self.assertNotIn("question", result.labels)
        self.assertIn("不触发 AI 回复", result.reason)

    def test_example_with_question_word_still_not_triggered(self):
        # “怎么”是弱问题信号，但“比如说”表明这是举例说明，不应触发回复。
        result = self.cm.analyze_utterance("比如说你们之前是怎么处理审批流程的")
        self.assertFalse(result.should_reply)
        self.assertIn("context_note", result.labels)

    def test_negated_question_not_triggered(self):
        result = self.cm.analyze_utterance("我们没什么问题")
        self.assertFalse(result.should_reply)

    def test_pain_statement_enters_memory_without_reply(self):
        result = self.cm.analyze_utterance("线索跟进不及时，影响整体效率")
        self.assertFalse(result.should_reply)
        self.assertIn("pain_point", result.labels)
        self.assertIn("context_note", result.labels)

    def test_key_fact_label(self):
        result = self.cm.analyze_utterance("我们目前已经接入了三家客户")
        self.assertIn("key_fact", result.labels)
        self.assertFalse(result.should_reply)

    def test_empty_text(self):
        result = self.cm.analyze_utterance("")
        self.assertFalse(result.should_reply)
        self.assertEqual(result.labels, [])

    def test_importance_reflects_labels(self):
        question = self.cm.analyze_utterance("你们支持私有化部署吗")
        note = self.cm.analyze_utterance("比如这是一个示例说明")
        self.assertGreater(question.importance, note.importance)


class TestReplyTrigger(unittest.TestCase):
    def setUp(self):
        self.cm = ContextManager()

    def test_designated_speaker_question_triggers(self):
        analysis = self.cm.analyze_utterance("能否提供接口文档？")
        self.assertTrue(self.cm.should_trigger_reply(True, analysis))

    def test_non_designated_speaker_question_does_not_trigger(self):
        analysis = self.cm.analyze_utterance("能否提供接口文档？")
        self.assertFalse(self.cm.should_trigger_reply(False, analysis))

    def test_designated_speaker_explanation_does_not_trigger(self):
        # 关键需求：指定参会人说的说明性内容也不应生成 AI 回复。
        analysis = self.cm.analyze_utterance("比如我们现在是通过邮件同步线索的")
        self.assertFalse(self.cm.should_trigger_reply(True, analysis))


class TestContextDigest(unittest.TestCase):
    def setUp(self):
        self.cm = ContextManager()

    def test_update_memory_collects_context_notes_and_key_facts(self):
        from app.models import Message

        memory = make_memory()
        note = Message(
            id="m1",
            session_id="s1",
            text="比如我们现在客户线索进来之后，销售一般要两三天才会跟进",
            created_at="2026-01-01T00:00:00",
        )
        fact = Message(
            id="m2",
            session_id="s1",
            text="我们目前已经接入了三家客户",
            created_at="2026-01-01T00:00:00",
        )
        self.cm.update_memory(memory, note, save=False)
        self.cm.update_memory(memory, fact, save=False)
        self.assertTrue(any("比如" in item for item in memory.context_notes))
        self.assertTrue(any("三家客户" in item for item in memory.key_facts))

    def test_context_lists_are_bounded(self):
        from app.models import Message

        memory = make_memory()
        for i in range(40):
            msg = Message(
                id=f"m{i}",
                session_id="s1",
                text=f"比如这是第{i}条背景说明",
                created_at="2026-01-01T00:00:00",
            )
            self.cm.update_memory(memory, msg, save=False)
        self.assertEqual(len(memory.context_notes), 30)

    def test_format_context_for_llm_marks_background_as_non_question(self):
        memory = make_memory()
        memory.context_notes.append("客户：比如我们现在用邮件同步线索")
        memory.pain_points.append("客户：线索跟进不及时")
        memory.risks.append("客户：担心上线周期太长")
        memory.questions.append("客户：能否对接 CRM？")

        text = self.cm.format_context_for_llm(memory)
        self.assertIn("会晤目标：推动 CRM 集成方案确认", text)
        self.assertIn("背景说明（非问题，仅供参考）", text)
        self.assertIn("比如我们现在用邮件同步线索", text)
        self.assertIn("客户痛点", text)
        self.assertIn("风险与顾虑", text)
        self.assertIn("已捕获问题", text)


if __name__ == "__main__":
    unittest.main()
