import unittest

from app.models import ModelConfig
from app.services.llm_client import llm_client


class TestApiUrl(unittest.TestCase):
    def _url(self, base: str, api_type: str) -> str:
        return llm_client.api_url(
            ModelConfig(llm_base_url=base, llm_api_type=api_type)  # type: ignore[arg-type]
        )

    def test_host_only_appends_version_and_endpoint(self):
        self.assertEqual(
            self._url("https://api.deepseek.com", "chat_completions"),
            "https://api.deepseek.com/v1/chat/completions",
        )
        self.assertEqual(
            self._url("https://api.openai.com", "responses"),
            "https://api.openai.com/v1/responses",
        )

    def test_version_only_appends_endpoint(self):
        self.assertEqual(
            self._url("https://host/v1", "chat_completions"),
            "https://host/v1/chat/completions",
        )
        self.assertEqual(
            self._url("https://host/v1", "responses"),
            "https://host/v1/responses",
        )

    def test_full_endpoint_not_duplicated(self):
        self.assertEqual(
            self._url("https://host/v1/chat/completions", "chat_completions"),
            "https://host/v1/chat/completions",
        )
        self.assertEqual(
            self._url("https://host/v1/responses", "responses"),
            "https://host/v1/responses",
        )

    def test_oci_full_action_path_not_duplicated(self):
        base = "https://inference.generativeai.us-ashburn-1.oci.oraclecloud.com/20231130/actions/v1/responses"
        self.assertEqual(self._url(base, "responses"), base)

    def test_trailing_slash_is_stripped(self):
        self.assertEqual(
            self._url("https://api.deepseek.com/", "chat_completions"),
            "https://api.deepseek.com/v1/chat/completions",
        )


if __name__ == "__main__":
    unittest.main()
