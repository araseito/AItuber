# services/aivis_service.py
import aiohttp
import logging
from typing import Optional
import json

logger = logging.getLogger('AItuber.aivis')

class AIVISService:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        
    async def synthesize_speech(self, text: str) -> Optional[bytes]:
        try:
            async with aiohttp.ClientSession() as session:
                # 音声合成クエリの生成
                query_url = f"{self.base_url}/audio_query"
                async with session.post(
                    query_url,
                    params={'text': text, 'speaker': 1},
                    timeout=30
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Query error: {response.status}")
                    query_data = await response.json()
                
                # 音声合成の実行
                synthesis_url = f"{self.base_url}/synthesis"
                async with session.post(
                    synthesis_url,
                    params={'speaker': 1},
                    json=query_data,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Synthesis error: {response.status}")
                    return await response.read()
                    
        except Exception as e:
            logger.error(f"Error in synthesize_speech: {e}")
            return None