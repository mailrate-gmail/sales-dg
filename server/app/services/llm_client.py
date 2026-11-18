import httpx

from app.config import settings


class LLMClient:
    async def suggest_reply(self, meeting_goal: str, conversation_history: str, latest_customer_message: str) -> str:
        if not settings.llm_api_key:
            return "未配置 LLM_API_KEY，无法生成 AI 建议回复。"

        prompt = f"""
你是我的商务会谈辅助助手。

本次会晤目标是：
{meeting_goal}

最近会话记录：
{conversation_history}

客户最新发言：
{latest_customer_message}

请生成一段适合我回复客户的话术。

要求：
1. 语气专业、自然；
2. 先回应客户关切，再推进会晤目标；
3. 不要过度承诺；
4. 不要编造不存在的产品能力；
5. 如信息不足，请建议进一步追问；
6. 输出不超过 150 字。
""".strip()

        url = settings.llm_base_url.rstrip("/") + "/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": "你是专业的商务会谈辅助助手。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
        }

        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()


llm_client = LLMClient()
