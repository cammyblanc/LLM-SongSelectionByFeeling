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

    def get_recommendations(self, references, mood, count=10):
        """参考曲リストと気分に基づいて指定された曲数を推薦し、カジュアルな思考プロセスの要約も返す"""
        prompt = f"以下の参考曲（アーティストと曲名）の雰囲気をベースにして、今の気分が「{mood}」な人が聴きたくなりそうな曲を{count}曲選んでください。\n\n"
        prompt += "【選曲の条件】\n"
        prompt += "・参考曲がリリースされた年代の楽曲から、ごく最近の最新曲まで、幅広い年代の楽曲をバランスよく混ぜて選曲してください。\n"
        prompt += "・ジャンルやテイストは参考曲の雰囲気に合わせつつ、年代の幅をもたせることが重要です。\n\n"
        prompt += "【参考曲】\n" + "\n".join(references) + "\n\n"
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
            
            message = response.choices[0].message
            content = message.content.strip()
            
            # 1. reasoning_contentの抽出 (LM Studioの仕様に依存するため複数パターン対応)
            reasoning = getattr(message, 'reasoning_content', '')
            if not reasoning and hasattr(message, 'model_extra') and message.model_extra:
                reasoning = message.model_extra.get('reasoning_content', '')
            
            # 2. <think>タグが含まれている場合の抽出と除去
            import re
            if not reasoning:
                think_match = re.search(r'<think>(.*?)</think>', content, flags=re.DOTALL)
                if think_match:
                    reasoning = think_match.group(1).strip()
                    
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            # 3. 思考プロセスのカジュアル要約 (2回目のLLM呼び出し)
            casual_reasoning = ""
            if reasoning:
                summary_prompt = f"以下のAIの思考プロセスを要約し、Discordのユーザーに向けてカジュアルで親しみやすい言葉に変換してください。\n例：「〜と考えて選びました！」「〜な曲を集めてみました！」など。\n\n思考プロセス:\n{reasoning}\n\n【制約】\n・100字~150字程度で短くまとめる\n・カジュアルなトーンにする\n・AIが話しているようなメタ発言（「ユーザーは〜を求めている」等）は避ける\n・<think>タグは含めない"
                try:
                    res_summary = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": summary_prompt}],
                        temperature=0.7
                    )
                    casual_reasoning = res_summary.choices[0].message.content.strip()
                    casual_reasoning = re.sub(r'<think>.*?</think>', '', casual_reasoning, flags=re.DOTALL).strip()
                except Exception as e:
                    print(f"Error summarizing reasoning: {e}")
            
            # 行ごとに分割してリスト化
            recs = [line.strip() for line in content.split('\n') if line.strip()]
            return recs[:count], casual_reasoning
        except Exception as e:
            print(f"Error calling LM Studio: {e}")
            return [], ""

if __name__ == "__main__":
    # Test
    # handler = LLMHandler()
    # print(handler.get_recommendations(["Taylor Swift", "BTS"], "Happy"))
    pass
