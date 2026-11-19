import unittest

from app.services.punctuation import restore_punctuation


class TestRestorePunctuation(unittest.TestCase):
    def test_adds_period_for_statement(self):
        self.assertEqual(restore_punctuation("我们现在客户线索跟进不及时"), "我们现在客户线索跟进不及时。")

    def test_adds_question_mark_for_question(self):
        self.assertEqual(restore_punctuation("你们这个系统能不能和我们CRM打通"), "你们这个系统能不能和我们CRM打通？")

    def test_keeps_existing_sentence_end(self):
        self.assertEqual(restore_punctuation("这个问题可以理解。"), "这个问题可以理解。")
        self.assertEqual(restore_punctuation("你们支持吗？"), "你们支持吗？")

    def test_inserts_comma_before_connector(self):
        self.assertEqual(
            restore_punctuation("我们现在流程比较复杂但是还是希望尽快上线"),
            "我们现在流程比较复杂，但是还是希望尽快上线。",
        )

    def test_does_not_duplicate_commas_when_punctuation_exists(self):
        self.assertEqual(
            restore_punctuation("我们现在流程比较复杂，但是还是希望尽快上线"),
            "我们现在流程比较复杂，但是还是希望尽快上线。",
        )

    def test_empty_text(self):
        self.assertEqual(restore_punctuation(""), "")
        self.assertEqual(restore_punctuation("   "), "")

    def test_sensitivity_controls_long_clause_splitting(self):
        text = "我们现在客户线索进来以后销售一般两三天才会跟进这个过程比较慢经常会漏掉一些线索"
        conservative = restore_punctuation(text, sensitivity=0.1)
        aggressive = restore_punctuation(text, sensitivity=1.0)
        self.assertGreater(aggressive.count("，"), conservative.count("，"))

    def test_zero_sensitivity_only_adds_sentence_end(self):
        text = "我们现在流程比较复杂但是希望尽快上线"
        self.assertEqual(restore_punctuation(text, sensitivity=0), "我们现在流程比较复杂但是希望尽快上线。")


if __name__ == "__main__":
    unittest.main()
