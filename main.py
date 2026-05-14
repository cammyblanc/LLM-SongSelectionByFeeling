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
        self.spotify_playlist_id = "1quEUu5Omrs3S08tuPA4Pa" # アーティスト取得用ソース
        self.target_playlist_id = self.config.get("spotify_target_playlist_id", "") # 更新先プレイリスト
        self.processing = False

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

        mood = message.content.strip()
        if not mood:
            return

        self.processing = True
        async with message.channel.typing():
            try:
                await message.channel.send(f"「{mood}」ですね！おすすめのリストを作成します。少々お待ちください... 🎵")
                
                # 1. Spotify からアーティストを取得 (スレッドで実行してフリーズ防止)
                artists = await asyncio.to_thread(self.spotify.get_artists_from_playlist, self.spotify_playlist_id)
                
                # 2. LM Studio で推薦を取得
                recs = await asyncio.to_thread(self.llm.get_recommendations, artists, mood)
                
                if not recs:
                    await message.channel.send("申し訳ありません。おすすめの曲を見つけることができませんでした。")
                    self.processing = False
                    return

                # 3. Spotify で曲を検索
                track_ids = await asyncio.to_thread(self.spotify.search_tracks, recs)
                
                if not track_ids:
                    await message.channel.send("Spotify で該当する曲が見つかりませんでした。")
                    self.processing = False
                    return

                # 4. Spotify プレイリスト更新
                if not self.target_playlist_id:
                    await message.channel.send("⚠️ `config.json` に `spotify_target_playlist_id` が設定されていません。\nSpotifyで空のプレイリストを作成し、そのIDを設定してください。")
                    self.processing = False
                    return
                    
                playlist_url = await asyncio.to_thread(self.spotify.update_playlist, self.target_playlist_id, track_ids, mood)
                
                # 5. Discord に報告
                await message.channel.send(f"hermesのおすすめリスト♪\n{playlist_url}")
                
            except Exception as e:
                print(f"Error in processing: {e}")
                await message.channel.send(f"エラーが発生しました: {e}")
            finally:
                self.processing = False

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
