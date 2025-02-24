# services/video_manager.py
import cv2
import logging
import json
from pathlib import Path
from typing import Dict, Tuple, Optional, Any
import asyncio

logger = logging.getLogger('AItuber.video')

class VideoManager:
    def __init__(self, video_dir: Path):
        self.video_dir = video_dir
        self.video_info_cache: Dict[str, Dict] = {}
        self.current_idle_index = 0
        self.current_repeat = 0
        self.idle_task = None
        self.is_running = False
        self.load_config()
        self.preload_videos()

    def load_config(self) -> None:
        """設定ファイルの読み込み"""
        try:
            config_path = Path('config/video_config.json')
            if config_path.exists():
                self.config = json.loads(config_path.read_text())
            else:
                raise FileNotFoundError("Video config not found")
        except Exception as e:
            logger.error(f"Error loading video config: {e}")
            raise

    def preload_videos(self) -> None:
        """動画情報の事前読み込み"""
        logger.info("Starting video preload...")
        
        # アイドル動画の読み込み
        for video_id, filename in self.config['video_files']['idle'].items():
            path = self.video_dir / filename
            if path.exists():
                info = self.get_video_info(path)
                if info:
                    self.video_info_cache[filename] = info
                    logger.debug(f"Preloaded idle video: {filename}")
        
        # トーキング動画の読み込み
        for filename in self.config['video_files']['talking']:
            path = self.video_dir / filename
            if path.exists():
                info = self.get_video_info(path)
                if info:
                    self.video_info_cache[filename] = info
                    logger.debug(f"Preloaded talking video: {filename}")
        
        logger.info(f"Preloaded {len(self.video_info_cache)} videos")

    def get_video_info(self, video_path: Path) -> Optional[Dict[str, Any]]:
        """動画ファイルの情報を取得"""
        try:
            if video_path.suffix == '.jpg':
                # 静止画の場合
                img = cv2.imread(str(video_path))
                if img is None:
                    raise ValueError(f"Failed to load image: {video_path}")
                return {
                    'type': 'image',
                    'width': img.shape[1],
                    'height': img.shape[0],
                    'duration': 0.0
                }
            else:
                # 動画の場合
                video = cv2.VideoCapture(str(video_path))
                if not video.isOpened():
                    raise ValueError(f"Failed to open video: {video_path}")
                
                info = {
                    'type': 'video',
                    'fps': video.get(cv2.CAP_PROP_FPS),
                    'frame_count': int(video.get(cv2.CAP_PROP_FRAME_COUNT)),
                    'width': int(video.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    'height': int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
                }
                info['duration'] = info['frame_count'] / info['fps']
                video.release()
                return info
                
        except Exception as e:
            logger.error(f"Error getting video info for {video_path}: {e}")
            return None

    def get_next_idle_video(self) -> Tuple[Path, bool]:
        """次のアイドル動画を取得"""
        try:
            pattern = self.config['idle_pattern'][self.current_idle_index]
            video_name = self.config['video_files']['idle'][pattern['video']]
            video_path = self.video_dir / video_name
            
            is_pattern_end = False
            if self.current_repeat >= pattern['repeat'] - 1:
                self.current_repeat = 0
                self.current_idle_index = (self.current_idle_index + 1) % len(self.config['idle_pattern'])
                is_pattern_end = True
            else:
                self.current_repeat += 1
                
            return video_path, is_pattern_end
            
        except Exception as e:
            logger.error(f"Error getting next idle video: {e}")
            # フォールバック: 最初の動画を返す
            fallback_video = self.video_dir / self.config['video_files']['idle']['00']
            return fallback_video, True

    def get_talking_video(self, text_length: int) -> Path:
        """テキストの長さに応じた会話動画を選択"""
        try:
            talking_videos = self.config['video_files']['talking']
            
            # テキストの長さに基づいて適切な動画を選択
            if text_length < 50:
                video_name = talking_videos[0]  # 短い応答用
            elif text_length < 100:
                video_name = talking_videos[1]  # 中程度の応答用
            else:
                video_name = talking_videos[2]  # 長い応答用
                
            return self.video_dir / video_name
            
        except Exception as e:
            logger.error(f"Error getting talking video: {e}")
            # フォールバック: 最初のトーキング動画を返す
            return self.video_dir / self.config['video_files']['talking'][0]

    async def prepare_video(self, video_path: Path) -> Optional[Dict[str, Any]]:
        """動画の準備"""
        try:
            if not video_path.exists():
                raise FileNotFoundError(f"Video not found: {video_path}")
                
            video_name = video_path.name
            if video_name in self.video_info_cache:
                info = self.video_info_cache[video_name].copy()
                info['path'] = str(video_path)
                return info
                
            # キャッシュにない場合は情報を取得
            info = self.get_video_info(video_path)
            if info:
                info['path'] = str(video_path)
                self.video_info_cache[video_name] = info
                return info
                
            return None
            
        except Exception as e:
            logger.error(f"Error preparing video: {e}")
            return None

    async def run_idle_loop(self) -> None:
        """アイドル動画ループの実行"""
        self.is_running = True
        try:
            while self.is_running:
                video_path, is_pattern_end = self.get_next_idle_video()
                video_info = await self.prepare_video(video_path)
                
                if video_info:
                    # 動画の長さ分待機
                    await asyncio.sleep(video_info['duration'])
                else:
                    # エラー時は短い待機
                    await asyncio.sleep(1)
                    
        except asyncio.CancelledError:
            logger.info("Idle loop cancelled")
        except Exception as e:
            logger.error(f"Error in idle loop: {e}")
        finally:
            self.is_running = False

    def stop(self) -> None:
        """動画管理の停止"""
        self.is_running = False

    def check_status(self) -> bool:
        """状態チェック"""
        try:
            # 必要なファイルの存在確認
            for video_list in self.config['video_files'].values():
                if isinstance(video_list, dict):
                    files = video_list.values()
                else:
                    files = video_list
                
                for filename in files:
                    if not (self.video_dir / filename).exists():
                        logger.error(f"Missing video file: {filename}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking video manager status: {e}")
            return False