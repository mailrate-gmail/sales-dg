import unittest

from app.services.text_merge import merge_stream_text


class TestMergeStreamText(unittest.TestCase):
    def test_empty_inputs(self):
        self.assertEqual(merge_stream_text("", "你好"), "你好")
        self.assertEqual(merge_stream_text("你好", ""), "你好")
        self.assertEqual(merge_stream_text("", ""), "")

    def test_incoming_extends_current(self):
        self.assertEqual(merge_stream_text("我们", "我们的"), "我们的")

    def test_incoming_already_contained(self):
        self.assertEqual(merge_stream_text("你好世界", "世界"), "你好世界")
        self.assertEqual(merge_stream_text("你好", "你好"), "你好")

    def test_overlap_merges_without_duplicate(self):
        self.assertEqual(merge_stream_text("线索跟进不", "跟进不及时"), "线索跟进不及时")

    def test_no_overlap_appends(self):
        self.assertEqual(merge_stream_text("你好", "世界"), "你好世界")

    def test_single_char_overlap_not_treated_as_overlap(self):
        # 单字不算重叠，避免误删合法叠字
        self.assertEqual(merge_stream_text("人", "人们"), "人们")
        self.assertEqual(merge_stream_text("各", "各位"), "各位")


if __name__ == "__main__":
    unittest.main()
