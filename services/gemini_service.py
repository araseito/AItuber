import logging
from typing import Optional
from google.generativeai import GenerativeModel, configure
import json

logger = logging.getLogger("AItuber.gemini")

class GeminiService:
    def __init__(self, api_key: str):
        configure(api_key=api_key)
        self.model = GenerativeModel("gemini-pro")
        self.load_character_config()

    def load_character_config(self) -> None:
        """キャラクター設定の読み込み"""
        try:
            with open("config/character_config.json", "r", encoding="utf-8") as f:
                self.character_config = json.load(f)
        except Exception as e:
            logger.error(f"Error loading character config: {e}")
            self.character_config = {"prompt": ""}

    async def generate_response(
        self,
        message: str,
        username: str,
        is_first_time: bool = False,
        is_today_first: bool = False
    ) -> Optional[str]:
        try:
            context = f"""
            {self.character_config["prompt"]}
            
            現在の状況:
            ユーザー名: {username}
            {"初めてのコメントです。" if is_first_time else ""}
            {"今日初めてのコメントです。" if is_today_first else ""}
            
            ユーザーのコメント: {message}
            """
            
            response = await self.model.generate_content(context)
            return response.text
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return None