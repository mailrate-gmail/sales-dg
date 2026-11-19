import unittest
from unittest.mock import patch

from app.models import ModelConfig
from app.services.config_view import MASKED_API_KEY, mask_config, unmask_api_key


class TestMaskConfig(unittest.TestCase):
    def test_mask_hides_saved_key(self):
        config = ModelConfig(llm_api_key="sk-real-secret")
        masked = mask_config(config)
        self.assertEqual(masked.llm_api_key, MASKED_API_KEY)
        # 原对象不应被修改
        self.assertEqual(config.llm_api_key, "sk-real-secret")

    def test_empty_key_unchanged(self):
        config = ModelConfig(llm_api_key="")
        self.assertEqual(mask_config(config).llm_api_key, "")


class TestUnmaskApiKey(unittest.TestCase):
    def test_mask_sentinel_restores_saved_key(self):
        saved = ModelConfig(llm_api_key="sk-real-secret")
        payload = ModelConfig(llm_api_key=MASKED_API_KEY, llm_model="changed")
        with patch("app.services.config_view.runtime_config.get", return_value=saved):
            restored = unmask_api_key(payload)
        self.assertEqual(restored.llm_api_key, "sk-real-secret")
        self.assertEqual(restored.llm_model, "changed")

    def test_new_key_is_kept(self):
        payload = ModelConfig(llm_api_key="sk-new-key")
        restored = unmask_api_key(payload)
        self.assertEqual(restored.llm_api_key, "sk-new-key")

    def test_empty_key_is_kept_for_clear(self):
        payload = ModelConfig(llm_api_key="")
        restored = unmask_api_key(payload)
        self.assertEqual(restored.llm_api_key, "")


if __name__ == "__main__":
    unittest.main()
