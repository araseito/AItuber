# services/sync_manager.py

import asyncio
import logging
from typing import Optional, Dict, Any
import time

logger = logging.getLogger('AItuber.sync')

class SyncManager:
    def __init__(self):
        """同期マネージャーの初期化"""
        self.current_task: Optional[asyncio.Task] = None
        self.video_queue = asyncio.Queue()
        self.audio_queue = asyncio.Queue()
        self.is_playing = False
        self.current_video_path = None
        self.current_audio_data = None
        self.start_time = 0

    async def sync_media(self, video_data: Dict[str, Any], audio_data: bytes) -> bool:
        """動画と音声の同期再生"""
        try:
            # 現在の再生をキャンセル
            await self.stop_current_playback()

            # キューをクリア
            await self.clear_queues()

            # 新しいメディアをキューに追加
            await self.video_queue.put(video_data)
            await self.audio_queue.put(audio_data)

            # 再生タスクを開始
            self.current_task = asyncio.create_task(self._play_synced())
            self.is_playing = True
            return True

        except Exception as e:
            logger.error(f"Error in sync_media: {e}")
            return False

    async def stop_current_playback(self) -> None:
        """現在の再生を停止"""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                logger.debug("Current playback cancelled")
            except Exception as e:
                logger.error(f"Error cancelling playback: {e}")

    async def clear_queues(self) -> None:
        """キューのクリア"""
        while not self.video_queue.empty():
            await self.video_queue.get()
        while not self.audio_queue.empty():
            await self.audio_queue.get()

    async def _play_synced(self) -> None:
        """メディアの同期再生"""
        try:
            # キューからメディアを取得
            video_data = await self.video_queue.get()
            audio_data = await self.audio_queue.get()

            # 再生情報の更新
            self.current_video_path = video_data.get('path')
            self.current_audio_data = audio_data
            self.start_time = time.time()

            # 動画の長さを取得
            video_duration = video_data.get('duration', 0)
            
            logger.debug(f"Starting playback: video={self.current_video_path}, duration={video_duration}")

            # 再生時間分待機
            await asyncio.sleep(video_duration)

            # 再生終了処理
            self.is_playing = False
            self.current_video_path = None
            self.current_audio_data = None

        except asyncio.CancelledError:
            logger.info("Playback cancelled")
            self.is_playing = False
        except Exception as e:
            logger.error(f"Error in _play_synced: {e}")
            self.is_playing = False
        finally:
            # 状態のリセット
            self.current_video_path = None
            self.current_audio_data = None
            self.start_time = 0

    async def get_playback_status(self) -> Dict[str, Any]:
        """再生状態の取得"""
        current_time = time.time()
        elapsed_time = current_time - self.start_time if self.start_time > 0 else 0

        return {
            'is_playing': self.is_playing,
            'current_video': self.current_video_path,
            'has_audio': self.current_audio_data is not None,
            'elapsed_time': elapsed_time
        }

    async def stop(self) -> None:
        """同期マネージャーの停止"""
        await self.stop_current_playback()
        await self.clear_queues()
        self.is_playing = False

    async def cleanup(self) -> None:
        """リソースのクリーンアップ"""
        await self.stop()
        logger.info("Sync manager cleaned up")