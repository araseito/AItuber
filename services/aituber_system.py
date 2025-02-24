import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from .youtube_service import YouTubeService
from .gemini_service import GeminiService
from .aivis_service import AIVISService
from .cache_manager import CacheManager
from .video_manager import VideoManager
from .sync_manager import SyncManager

logger = logging.getLogger("AItuber")

class AITuberSystem:
    def __init__(self):
        self.base_path = Path("/content/drive/MyDrive/AItuber")
        self.setup_services()
        logger.info("AITuber System initialized")
        
    def setup_services(self):
        try:
            self.response_cache = CacheManager("responses")
            self.audio_cache = CacheManager("audio")
            self.youtube = YouTubeService(os.getenv("YOUTUBE_API_KEY", ""))
            self.gemini = GeminiService(os.getenv("GEMINI_API_KEY", ""))
            self.aivis = AIVISService(os.getenv("AIVIS_URL", "http://localhost:50021"))
            self.video_manager = VideoManager(self.base_path / "videos")
            self.sync_manager = SyncManager()
            logger.info("All services initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            raise

    async def run(self):
        try:
            idle_task = asyncio.create_task(self.video_manager.run_idle_loop())
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("System shutdown requested")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        try:
            await self.sync_manager.cleanup()
            self.video_manager.stop()
            self.response_cache.save_cache()
            self.audio_cache.save_cache()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def emergency_cleanup(self):
        try:
            self.video_manager.stop()
            self.response_cache.save_cache()
            self.audio_cache.save_cache()
            logger.info("Emergency cleanup completed")
        except Exception as e:
            logger.error(f"Error during emergency cleanup: {e}")