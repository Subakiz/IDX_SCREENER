import asyncio
import uvloop
import logging
from src.data_ingestion import MockIDXSource
from src.database import MockDatabase
from src.tda_engine import TDAEngine
from src.mc_engine import MonteCarloEngine
from src.strategy import HybridStrategy
from src.discord_bot import DiscordNotifier

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("IDX_ALGO_CORE")

async def main():
    # Set high-performance event loop policy
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    logger.info("Initializing Hybrid TDA-Probabilistic Trading System...")

    # 1. Initialize Components
    db = MockDatabase()
    data_source = MockIDXSource(symbol="BBRI.JK")

    tda = TDAEngine(window_size=50)
    mc = MonteCarloEngine(simulations=500, horizon=5) # Lower sims for sandbox speed

    notifier = DiscordNotifier(token=None) # Mock mode

    strategy = HybridStrategy(tda_engine=tda, mc_engine=mc)

    # 2. Start Services
    await db.connect()
    await data_source.connect()
    await notifier.start()

    logger.info("System Live. Listening for ticks...")

    # 3. Event Loop
    try:
        while True:
            tick = await data_source.get_tick()
            if tick:
                # Log occasional tick to show life
                if int(tick.timestamp * 100) % 50 == 0:
                    logger.debug(f"Tick: {tick.symbol} @ {tick.price}")

                # Persist
                await db.write_tick(tick)

                # Analyze
                signal = await strategy.on_tick(tick)

                # Execute
                if signal:
                    logger.info(f"SIGNAL GENERATED: {signal}")
                    await notifier.send_signal(signal)

            # Yield control
            await asyncio.sleep(0)

    except KeyboardInterrupt:
        logger.info("Shutting down...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
