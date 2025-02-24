import os
import sys
import asyncio
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any
import json
import time
from pyngrok import ngrok

# ロギングの設定
def setup_logging(base_path: Path) -> None:
    """ロギングの初期化"""
    log_dir = base_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "aituber.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger("AItuber")
    return logger

logger = setup_logging(Path("/content/drive/MyDrive/AItuber"))

class AITuberSystem:
    def __init__(self):
        """システムの初期化"""
        try:
            self.base_path = Path("/content/drive/MyDrive/AItuber")
            self.setup_directories()
            self.load_config()
            self.setup_services()
            logger.info("AITuber System initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing AITuber System: {e}")
            raise

    def setup_directories(self) -> None:
        """必要なディレクトリの作成"""
        directories = ["config", "data", "videos", "logs"]
        for dir_name in directories:
            dir_path = self.base_path / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {dir_path}")

    def load_config(self) -> None:
        """設定ファイルの読み込み"""
        try:
            config_path = self.base_path / "config/system_config.json"
            if not config_path.exists():
                default_config = {
                    "youtube_api_key": os.getenv("YOUTUBE_API_KEY", "AIzaSyCrUyPB8QEp4BGTHxYs6g7lOeIeagFUwgk"),
                    "gemini_api_key": os.getenv("GEMINI_API_KEY", "AIzaSyAix73Np5KqTAZViijaqL9FgCuVZ7Gkwm8"),
                    "aivis_url": os.getenv("AIVIS_URL", "http://localhost:50021"),
                    "cache_settings": {
                        "response_cache_size": 100,
                        "response_cache_ttl": 3600,
                        "audio_cache_size": 50,
                        "audio_cache_ttl": 7200
                    }
                }
                config_path.write_text(json.dumps(default_config, indent=2, ensure_ascii=False), encoding="utf-8")
                self.config = default_config
            else:
                self.config = json.loads(config_path.read_text(encoding="utf-8"))
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    def setup_services(self) -> None:
        """各サービスの初期化"""
        try:
            from services.youtube_service import YouTubeService
            from services.gemini_service import GeminiService
            from services.aivis_service import AIVISService
            from services.cache_manager import CacheManager
            from services.video_manager import VideoManager
            from services.sync_manager import SyncManager

            # キャッシュマネージャーの初期化
            cache_config = self.config["cache_settings"]
            self.response_cache = CacheManager(
                "responses",
                max_size=cache_config["response_cache_size"],
                ttl=cache_config["response_cache_ttl"]
            )
            self.audio_cache = CacheManager(
                "audio",
                max_size=cache_config["audio_cache_size"],
                ttl=cache_config["audio_cache_ttl"]
            )

            # 各サービスの初期化
            self.youtube = YouTubeService(self.config["youtube_api_key"])
            self.gemini = GeminiService(self.config["gemini_api_key"])
            self.aivis = AIVISService(self.config["aivis_url"])
            self.video_manager = VideoManager(self.base_path / "videos")
            self.sync_manager = SyncManager()

            # スレッドプールの初期化
            self.executor = ThreadPoolExecutor(max_workers=4)
            logger.info("All services initialized successfully")
        except Exception as e:
            logger.error(f"Error setting up services: {e}")
            raise

    async def process_comment(self, comment_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """コメントの処理"""
        try:
            # キャッシュキーの生成
            cache_key = f"{comment_data['message']}_{comment_data.get('user_id', '')}"
            
            # キャッシュから応答を取得
            response = self.response_cache.get(cache_key)
            if response is None:
                # Geminiでの応答生成
                response = await self.gemini.generate_response(
                    comment_data["message"],
                    comment_data.get("username", "unknown")
                )
                if response:
                    self.response_cache.set(cache_key, response)
            
            if not response:
                logger.error("Failed to generate response")
                return None

            # 音声合成
            audio_key = f"audio_{response}"
            audio_data = self.audio_cache.get(audio_key)
            if audio_data is None:
                audio_data = await self.aivis.synthesize_speech(response)
                if audio_data:
                    self.audio_cache.set(audio_key, audio_data)

            if not audio_data:
                logger.error("Failed to synthesize speech")
                return None

            # 動画の選択と準備
            video_path = self.video_manager.get_talking_video(len(response))
            video_info = await self.video_manager.prepare_video(video_path)

            if not video_info:
                logger.error("Failed to prepare video")
                return None

            # 同期再生の準備
            await self.sync_manager.sync_media(video_info, audio_data)

            return {
                "response": response,
                "video_info": video_info,
                "has_audio": True
            }

        except Exception as e:
            logger.error(f"Error processing comment: {e}", exc_info=True)
            return None

    async def run_monitoring(self) -> None:
        """YouTubeライブのモニタリング"""
        try:
            while True:
                comments = await self.youtube.get_comments()
                for comment in comments:
                    response = await self.process_comment(comment)
                    if response:
                        logger.info(f"Processed comment successfully: {comment['message'][:30]}...")
                await asyncio.sleep(10)  # ポーリング間隔
        except Exception as e:
            logger.error(f"Error in monitoring: {e}", exc_info=True)

    async def cleanup(self) -> None:
        """リソースのクリーンアップ"""
        try:
            self.executor.shutdown(wait=True)
            await self.sync_manager.stop_playback()
            self.response_cache.save_cache()
            self.audio_cache.save_cache()
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)

    async def run(self) -> None:
        """システムの実行"""
        try:
            # ngrokの設定
            public_url = ngrok.connect(8501)
            logger.info(f"Public URL: {public_url}")

            # モニタリングタスクの開始
            monitoring_task = asyncio.create_task(self.run_monitoring())

            # アイドル動画の再生
            idle_task = asyncio.create_task(self.video_manager.run_idle_loop())

            # タスクの実行
            await asyncio.gather(monitoring_task, idle_task)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            await self.cleanup()
            ngrok.disconnect(public_url)
            logger.info("System shutdown complete")

if __name__ == "__main__":
    # システムの起動
    try:
        system = AITuberSystem()
        asyncio.run(system.run())
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)