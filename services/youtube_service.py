# services/youtube_service.py
import logging
from typing import List, Dict, Optional
from googleapiclient.discovery import build
import time

logger = logging.getLogger('AItuber.youtube')

class YouTubeService:
    def __init__(self, api_key: str):
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.live_chat_id = None
        self.next_page_token = None
        self.last_request_time = 0
        self.min_request_interval = 1.0

    def _rate_limit(self) -> None:
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        self.last_request_time = time.time()

    async def get_live_chat_id(self, video_id: str) -> Optional[str]:
        try:
            self._rate_limit()
            request = self.youtube.videos().list(
                part="liveStreamingDetails",
                id=video_id
            )
            response = request.execute()
            
            if not response.get('items'):
                return None
                
            details = response['items'][0].get('liveStreamingDetails')
            if not details or 'activeLiveChatId' not in details:
                return None
                
            self.live_chat_id = details['activeLiveChatId']
            return self.live_chat_id
        except Exception as e:
            logger.error(f"Error getting live chat ID: {e}")
            return None

    async def get_comments(self) -> List[Dict]:
        if not self.live_chat_id:
            return []
            
        try:
            self._rate_limit()
            request = self.youtube.liveChatMessages().list(
                liveChatId=self.live_chat_id,
                part="snippet,authorDetails",
                pageToken=self.next_page_token
            )
            response = request.execute()
            
            self.next_page_token = response.get('nextPageToken')
            return response.get('items', [])
        except Exception as e:
            logger.error(f"Error getting comments: {e}")
            return []