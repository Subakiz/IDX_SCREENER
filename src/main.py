import asyncio
import uvloop
import logging
import multiprocessing
import time
from src.data_ingestion import MockIDXSource
from src.database import MockDatabase
from src.tda_engine import TDAEngine
from src.mc_engine import MonteCarloEngine
from src.strategy import HybridStrategy
from src.discord_bot import DiscordNotifier
from src.dashboard import run_dashboard_server

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - [PROCESS %(processName)s] - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("IDX_ALGO")

async def trading_core():
    """The HFT Logic Loop (Runs on CPU Core 1)"""
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.info("Initializing HFT Engine...")

    # 1. Initialize Components
    db = MockDatabase()
    data_source = MockIDXSource(symbol="BBRI.JK")
    tda = TDAEngine(window_size=50)
    mc = MonteCarloEngine(simulations=500, horizon=5)
    notifier = DiscordNotifier(token=None)
    strategy = HybridStrategy(tda_engine=tda, mc_engine=mc)

    # Pre-fill Strategy with DB history (The Fix for Risk B)
    await db.connect() # Ensure DB connection for query
    history = await db.query_history("BBRI.JK", 50)
    if history:
        # Note: query_history returns ascending order (oldest first)
        strategy.load_initial_data([t.price for t in history])

    # 2. Start Services
    # db.connect() called above
    await data_source.connect()
    await notifier.start()

    logger.info("HFT Engine Live. Waiting for ticks...")

    try:
        while True:
            tick = await data_source.get_tick()
            if tick:
                # 1. Persist (IO Bound)
                await db.write_tick(tick)

                # 2. Analyze & Execute (CPU Bound)
                signal = await strategy.on_tick(tick)

                if signal:
                    logger.info(f"⚡ ACTION: {signal['action']} | {signal['reason']}")
                    await notifier.send_signal(signal)

            # Zero-sleep allows other async tasks (like heartbeats) to run
            await asyncio.sleep(0)

    except KeyboardInterrupt:
        logger.info("HFT Engine Stopping...")

def start_dashboard():
    """The Visual Server (Runs on CPU Core 2)"""
    run_dashboard_server()

if __name__ == "__main__":
    # Use Multiprocessing to separate Trading Logic from Visual Rendering
    # This ensures your GUI never lags your Order Execution

    p1 = multiprocessing.Process(target=start_dashboard, name="Dashboard_Proc")
    p1.start()

    try:
        # Run the Async Trading Bot in the Main Process
        asyncio.run(trading_core())
    except KeyboardInterrupt:
        logger.info("Main Process Shutdown.")
        p1.terminate()
        p1.join()
