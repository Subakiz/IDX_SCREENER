import asyncio
import sqlite3
import aiosqlite
from typing import List
from src.data_ingestion import Tick

class DatabaseAdapter:
    async def connect(self):
        raise NotImplementedError
    async def write_tick(self, tick: Tick):
        raise NotImplementedError
    async def query_history(self, symbol: str, limit: int) -> List[Tick]:
        raise NotImplementedError

class MockDatabase(DatabaseAdapter):
    def __init__(self, db_path="market_data.db"):
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS ticks (
                timestamp REAL,
                symbol TEXT,
                price REAL,
                volume INTEGER,
                bid_vol INTEGER,
                ask_vol INTEGER
            )
        ''')
        await self.conn.commit()
        print(f"Connected to Mock Database (SQLite) at {self.db_path}")

    async def write_tick(self, tick: Tick):
        if not self.conn:
            await self.connect()

        await self.conn.execute(
            'INSERT INTO ticks (timestamp, symbol, price, volume, bid_vol, ask_vol) VALUES (?, ?, ?, ?, ?, ?)',
            (tick.timestamp, tick.symbol, tick.price, tick.volume, tick.bid_vol, tick.ask_vol)
        )
        await self.conn.commit()

    async def query_history(self, symbol: str, limit: int) -> List[Tick]:
        if not self.conn:
            await self.connect()

        cursor = await self.conn.execute(
            'SELECT symbol, price, volume, timestamp, bid_vol, ask_vol FROM ticks WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?',
            (symbol, limit)
        )
        rows = await cursor.fetchall()
        # Sort back to ascending time
        rows = rows[::-1]

        ticks = [
            Tick(
                symbol=row[0],
                price=row[1],
                volume=row[2],
                timestamp=row[3],
                bid_vol=row[4],
                ask_vol=row[5]
            ) for row in rows
        ]
        return ticks

    # Synchronous method for Dashboard (Dash runs in sync context usually, but can use async)
    # Ideally Dash should use its own connection.
