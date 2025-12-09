import aiosqlite
import logging
from src.data_ingestion import Tick
from src.database import DatabaseAdapter

logger = logging.getLogger("DB_SQLITE")

class SQLiteAdapter(DatabaseAdapter):
    def __init__(self, db_path="market_data.db"):
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        """Initialize the DB schema"""
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS ticks (
                symbol TEXT,
                price REAL,
                volume INTEGER,
                bid_vol INTEGER,
                ask_vol INTEGER,
                timestamp REAL
            )
        ''')
        await self.conn.commit()
        logger.info(f"Connected to SQLite: {self.db_path}")

    async def write_tick(self, tick: Tick):
        """Writes a single tick to the DB"""
        try:
            if not self.conn:
                await self.connect()

            await self.conn.execute(
                "INSERT INTO ticks (symbol, price, volume, bid_vol, ask_vol, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (tick.symbol, tick.price, tick.volume, tick.bid_vol, tick.ask_vol, tick.timestamp)
            )
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Write Error: {e}")

    async def query_history(self, symbol: str, limit: int) -> list[Tick]:
        if not self.conn:
            await self.connect()

        cursor = await self.conn.execute(
            'SELECT symbol, price, volume, bid_vol, ask_vol, timestamp FROM ticks WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?',
            (symbol, limit)
        )
        rows = await cursor.fetchall()
        # Sort back to ascending time for strategy processing
        rows = rows[::-1]

        ticks = [
            Tick(
                symbol=row[0],
                price=row[1],
                volume=row[2],
                bid_vol=row[3],
                ask_vol=row[4],
                timestamp=row[5]
            ) for row in rows
        ]
        return ticks
