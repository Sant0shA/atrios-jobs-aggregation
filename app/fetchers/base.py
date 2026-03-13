from abc import ABC, abstractmethod


class BaseFetcher(ABC):
    source_name: str

    @abstractmethod
    async def fetch(self) -> list[dict]:
        raise NotImplementedError
