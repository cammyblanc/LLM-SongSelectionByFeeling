import json
import os
from openai import OpenAI

class LLMHandler:
    def __init__(self, config_path="config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        self.client = OpenAI(
            base_url=self.config.get("llm_host", "http://localhost:1234/v1"),
            api_key="lm-studio"  # LM Studio doesn't usually require a real API key
        )
        self.model = self.config.get("chat_model", "google/gemma-4-e4b")

    def get_recommendations(self, artists, mood):
        """アーティストリストと気分に基づいて10曲を推薦する"""
        prompt = f"以下のアーティストを参考に、今の気分「{mood}」にぴったりの曲を10曲選んでください。\n\n"
        prompt += "【参考アーティスト】\n" + ", ".join(artists) + "\n\n"
        prompt += "【制約】\n・出力は必ず「Artist - Song Title」の形式のみにしてください。\n・説明文や挨拶は一切含めないでください。"
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたはプロの音楽キュレーターです。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            content = response.choices[0].message.content.strip()
            # 行ごとに分割してリスト化
            recs = [line.strip() for line in content.split('\n') if line.strip()]
            return recs[:10]
        except Exception as e:
            print(f"Error calling LM Studio: {e}")
            return []

if __name__ == "__main__":
    # Test
    # handler = LLMHandler()
    # print(handler.get_recommendations(["Taylor Swift", "BTS"], "Happy"))
    pass
