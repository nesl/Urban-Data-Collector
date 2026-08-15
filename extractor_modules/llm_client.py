"""Small extractor-local OpenAI adapter used by email normalization."""

from openai import OpenAI
from utilities.util import get_config


class OpenAIClient:
    def __init__(self, model="gpt-4o"):
        config = get_config()
        self.client = OpenAI(api_key=config["openai"]["api"])
        self.model = model
        self.message_history = []

    def send_message_to_llm_single(self, user_input, temperature=0.0):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": user_input}],
            temperature=temperature,
        )
        return response.choices[0].message.content, None

    def send_message_to_llm_historic(self, user_input, temperature=0.0):
        self.message_history.append({"role": "user", "content": user_input})
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.message_history,
            temperature=temperature,
        )
        content = response.choices[0].message.content
        self.message_history.append({"role": "assistant", "content": content})
        return content, None


LLMClient = OpenAIClient
