import asyncio
from typing import List, Any
from src.data_ingestion import Tick

class DatabaseAdapter:
    async def connect(self):
        raise NotImplementedError
    async def write_tick(self, tick: Tick):
        raise NotImplementedError
    async def query_history(self, symbol: str, limit: int) -> List[Tick]:
        raise NotImplementedError

class MockDatabase(DatabaseAdapter):
    def __init__(self):
        self.store = []

    async def connect(self):
        print("Connected to Mock Database (In-Memory)")

    async def write_tick(self, tick: Tick):
        self.store.append(tick)
        # Keep memory usage low for the mock
        if len(self.store) > 5000:
            self.store.pop(0)

    async def query_history(self, symbol: str, limit: int) -> List[Tick]:
        return [t for t in self.store if t.symbol == symbol][-limit:]
