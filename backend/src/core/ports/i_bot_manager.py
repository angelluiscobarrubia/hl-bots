from abc import ABC, abstractmethod

from src.core.entities.bot import Bot, BotStatus


class IBotManager(ABC):
    @abstractmethod
    async def create_bot(
        self,
        user_id: str,
        name: str,
        strategy: str,
        config: dict,
        is_paper: bool,
    ) -> Bot:
        pass

    @abstractmethod
    async def start_bot(self, bot_id: str, api_key: str, api_secret: str) -> bool:
        pass

    @abstractmethod
    async def stop_bot(self, bot_id: str) -> bool:
        pass

    @abstractmethod
    async def get_bot_status(self, bot_id: str) -> BotStatus:
        pass

    @abstractmethod
    async def list_bots(self, user_id: str) -> list[Bot]:
        pass
