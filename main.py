import discord
import json
import os
import asyncio
from dotenv import load_dotenv
from spotify_handler import SpotifyHandler
from llm_handler import LLMHandler

load_dotenv()

class MusicBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        with open("config.json", "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        self.target_channel_id = int(self.config.get("discord_bot_channel_id"))
        self.default_spotify_playlist_id = "1quEUu5Omrs3S08tuPA4Pa" # アーティスト取得用ソースのデフォルト
        self.target_playlist_id = self.config.get("spotify_target_playlist_id", "") # 更新先プレイリスト
        self.processing = False
        
        # 対話状態管理
        self.state = "WAITING_MOOD"
        self.session_data = {}

        print("Initializing Handlers...", flush=True)
        self.spotify = SpotifyHandler()
        self.llm = LLMHandler()

    async def on_ready(self):
        print(f'Bot is starting up...')
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        
        print(f'Looking for channel ID: {self.target_channel_id}')
        channel = self.get_channel(self.target_channel_id)
        if channel:
            print(f'Found channel: {channel.name}. Sending welcome message...')
            await channel.send("今はどんな気分？")
            print(f'Welcome message sent.')
        else:
            print(f"Error: Could not find channel with ID {self.target_channel_id}")

    async def on_message(self, message):
        # ボット自身のメッセージは無視
        if message.author == self.user:
            return

        # 指定されたチャンネル以外は無視
        if message.channel.id != self.target_channel_id:
            return

        # 処理中の場合は無視（連投防止）
        if self.processing:
            return

        text = message.content.strip()
        if not text:
            return

        if self.state == "WAITING_MOOD":
            self.session_data["mood"] = text
            self.state = "WAITING_PLAYLIST"
            await message.channel.send("気になるプレイリストは？おまかせなら「デフォルト」でおけ")
            return

        elif self.state == "WAITING_PLAYLIST":
            self.session_data["playlist_name"] = text
            self.state = "WAITING_COUNT"
            await message.channel.send("何曲ききたい？おまかせなら「デフォルト」で～")
            return

        elif self.state == "WAITING_COUNT":
            self.processing = True
            
            # 数字のみ取り出すか、エラーになればデフォルト10曲
            import re
            nums = re.findall(r'\d+', text)
            count = int(nums[0]) if nums else 10
            self.session_data["count"] = count
            
            playlist_name = self.session_data["playlist_name"]
            source_playlist_id = self.default_spotify_playlist_id
            
            if playlist_name not in ["デフォルト", "おまかせ"]:
                await message.channel.send(f"プレイリスト「{playlist_name}」を探しています...")
                found_id = await asyncio.to_thread(self.spotify.search_playlist_by_name, playlist_name)
                if found_id:
                    source_playlist_id = found_id
                else:
                    await message.channel.send(f"見つからなかったので、いつものリストを使いますね！")

            mood = self.session_data["mood"]
            count = self.session_data["count"]

            async with message.channel.typing():
                try:
                    await message.channel.send(f"「{playlist_name}」から「{mood}」の曲を {count} 曲ですね！おすすめのリストを作成します。少々お待ちください... 🎵")
                    
                    # 1. Spotify からアーティストと曲名を取得
                    references = await asyncio.to_thread(self.spotify.get_reference_tracks_from_playlist, source_playlist_id)
                    
                    # 2. LM Studio で推薦を取得
                    recs, casual_reasoning = await asyncio.to_thread(self.llm.get_recommendations, references, mood, count)
                    
                    if not recs:
                        await message.channel.send("おすすめの曲が見つけられんかった。。。")
                        return
    
                    # 3. Spotify で曲を検索
                    track_ids = await asyncio.to_thread(self.spotify.search_tracks, recs)
                    
                    if not track_ids:
                        await message.channel.send("Spotify にはないー (>o<)")
                        return
    
                    # 4. Spotify プレイリスト更新
                    if not self.target_playlist_id:
                        await message.channel.send("⚠️ `config.json` に `spotify_target_playlist_id` が設定されていません。\nSpotifyで空のプレイリストを作成し、そのIDを設定してください。")
                        return
                        
                    playlist_url = await asyncio.to_thread(self.spotify.update_playlist, self.target_playlist_id, track_ids, mood)
                    
                    # 5. Discord に報告
                    reply_msg = f"hermesのおすすめリスト♪\n"
                    if casual_reasoning:
                        reply_msg += f"\n{casual_reasoning}\n"
                    reply_msg += f"\n{playlist_url}"
                    
                    await message.channel.send(reply_msg)
                    
                except Exception as e:
                    print(f"Error in processing: {e}")
                    await message.channel.send(f"エラーが発生しました: {e}")
                finally:
                    # 状態リセット
                    self.state = "WAITING_MOOD"
                    self.session_data = {}
                    self.processing = False
                    await message.channel.send("今はどんな気分？")

def main():
    print("Program started...")
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in .env")
        return

    print("Setting up intents...")
    intents = discord.Intents.default()
    intents.message_content = True 

    print("Initializing MusicBot...")
    client = MusicBot(intents=intents)
    
    print("Running bot (this may take a moment to connect)...")
    client.run(token)

if __name__ == "__main__":
    main()
