import asyncio
import random
import time
from dataclasses import dataclass
import numpy as np

@dataclass
class Tick:
    __slots__ = ['symbol', 'price', 'volume', 'timestamp', 'bid_vol', 'ask_vol']
    symbol: str
    price: float
    volume: int
    timestamp: float
    bid_vol: int
    ask_vol: int

class DataSource:
    async def connect(self):
        raise NotImplementedError

    async def get_tick(self) -> Tick:
        raise NotImplementedError

class MockIDXSource(DataSource):
    def __init__(self, symbol="BBRI.JK", start_price=4800, mu=0.0001, sigma=0.02):
        self.symbol = symbol
        self.price = start_price
        self.mu = mu
        self.sigma = sigma
        self.running = False

    async def connect(self):
        self.running = True
        print(f"Connected to Mock IDX Source for {self.symbol}")

    async def get_tick(self) -> Tick:
        if not self.running:
            await asyncio.sleep(0.1)
            return None

        # Simulate GBM step (using small time steps for HFT-like simulation)
        dt = 1.0 / (252 * 390 * 60) # Approx 1 second
        drift = (self.mu - 0.5 * self.sigma**2) * dt
        diffusion = self.sigma * np.sqrt(dt) * np.random.normal()

        # Jump diffusion (occasional shock to test TDA)
        jump = 0
        rand_val = random.random()
        if rand_val < 0.0005: # Flash crash
            jump = -0.05
        elif rand_val > 0.9995: # Pump
            jump = 0.05

        ret = drift + diffusion + jump
        self.price *= np.exp(ret)

        # Quantize to tick size (IDX rules)
        if self.price > 5000:
            tick_size = 25
        elif self.price > 2000:
            tick_size = 10
        elif self.price > 500:
            tick_size = 5
        elif self.price > 200:
            tick_size = 2
        else:
            tick_size = 1

        self.price = max(50, round(self.price / tick_size) * tick_size)

        # Simulate Order Book volumes
        bid_vol = random.randint(100, 5000)
        ask_vol = random.randint(100, 5000)

        # Simulate trade volume
        volume = random.randint(1, 100) if random.random() > 0.7 else 0

        # Simulate slight latency
        await asyncio.sleep(0.001)

        return Tick(
            symbol=self.symbol,
            price=self.price,
            volume=volume,
            timestamp=time.time(),
            bid_vol=bid_vol,
            ask_vol=ask_vol
        )
