import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class SpotifyHandler:
    def __init__(self):
        # 必要な権限を全てリストとして指定します
        scopes = [
            "playlist-modify-public",
            "playlist-modify-private",
            "playlist-read-private",
            "playlist-read-collaborative",
            "user-read-private",
            "user-read-email",
            "user-library-modify",
            "user-library-read"
        ]
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.getenv("SPOTIPY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
            scope=" ".join(scopes),
            cache_path=".cache",
            open_browser=True
        ))
        try:
            user_info = self.sp.me()
            print(f"Logged in Spotify user: {user_info.get('display_name')} ({user_info.get('email')})", flush=True)
        except Exception as e:
            print(f"Spotify authentication failed: {e}\nPlease check your browser and complete the login. If it fails, delete the .cache file and restart.", flush=True)

    def search_playlist_by_name(self, name):
        """ユーザー自身のプレイリストの中から名前で検索し、一致するIDを返す"""
        try:
            print(f"Searching user's own playlists for: {name}", flush=True)
            playlists = self.sp.current_user_playlists(limit=50)
            while playlists:
                for playlist in playlists['items']:
                    if playlist and name.lower() in playlist['name'].lower():
                        print(f"Found playlist: {playlist['name']} (ID: {playlist['id']})", flush=True)
                        return playlist['id']
                if playlists['next']:
                    playlists = self.sp.next(playlists)
                else:
                    break
            print("Playlist not found in user's library.", flush=True)
            return None
        except Exception as e:
            print(f"Error searching for playlist: {e}", flush=True)
            return None

    def get_artists_from_playlist(self, playlist_id):
        """指定されたプレイリストからアーティスト名のリストを取得する"""
        results = self.sp.playlist_tracks(playlist_id)
        tracks = results.get('items', [])
        print(f"Retrieved {len(tracks)} items from playlist.", flush=True)
        artists = set()
        for pl_item in tracks:
            # Spotify APIの仕様変更により、'track' ではなく 'item' というキー名で返ってくる場合がある
            track = pl_item.get('track') or pl_item.get('item')
            if track:
                for artist in track.get('artists', []):
                    artists.add(artist['name'])
        return list(artists)

    def search_tracks(self, recommendations):
        """推薦された 'Artist - Song' リストから Spotify のトラック ID を検索する"""
        try:
            print(f"Searching for tracks based on: {recommendations}", flush=True)
        except UnicodeEncodeError:
            print("Searching for tracks (contains special characters)...", flush=True)
        
        track_ids = []
        for rec in recommendations:
            try:
                # 1. そのまま検索
                results = self.sp.search(q=rec, limit=1, type='track')
                if results['tracks']['items']:
                    track_ids.append(results['tracks']['items'][0]['id'])
                    continue
                
                # 2. " - " で分割して検索を試みる
                if " - " in rec:
                    parts = rec.split(" - ")
                    # アーティスト名と曲名を入れ替えてみたり、片方だけで検索してみたりする
                    query = f"track:{parts[1]} artist:{parts[0]}"
                    results = self.sp.search(q=query, limit=1, type='track')
                    if results['tracks']['items']:
                        track_ids.append(results['tracks']['items'][0]['id'])
                        continue

                try:
                    print(f"Could not find track: {rec}", flush=True)
                except UnicodeEncodeError:
                    print("Could not find track (contains special characters)", flush=True)
            except Exception as e:
                print(f"Error searching for {rec}: {e}", flush=True)
        return track_ids

    def update_playlist(self, playlist_id, track_ids, mood):
        """既存のプレイリストの曲を入れ替える（Spotifyの新しいAPI制限に対応）"""
        # テスト：お気に入りの曲に追加できるか確認
        if track_ids:
            try:
                self.sp.current_user_saved_tracks_add([track_ids[0]])
                print("Successfully added a track to Liked Songs as a test.", flush=True)
            except Exception as e:
                print(f"Liked Songs test failed: {e}", flush=True)

        try:
            print(f"Updating existing playlist: {playlist_id}", flush=True)
            
            # 既存のプレイリストの曲を一旦すべて上書き（入れ替え）する
            if track_ids:
                print(f"Replacing with {len(track_ids)} tracks...", flush=True)
                self.sp.playlist_replace_items(playlist_id, track_ids)
                
                # プレイリストの名前を気分に合わせて変更（もし可能なら。所有権が必要）
                try:
                    new_name = f"Hermes: {mood} 🎵"
                    self.sp.playlist_change_details(playlist_id, name=new_name)
                except Exception as detail_e:
                    print(f"Could not rename playlist (ignoring): {detail_e}")
                    
            # プレイリストのURLを取得して返す
            playlist = self.sp.playlist(playlist_id)
            return playlist['external_urls']['spotify']
        except Exception as e:
            print(f"Playlist update failed: {e}", flush=True)
            raise e

if __name__ == "__main__":
    # Test (requires .env to be filled)
    # handler = SpotifyHandler()
    # artists = handler.get_artists_from_playlist("1quEUu5Omrs3S08tuPA4Pa")
    # print(artists)
    pass
