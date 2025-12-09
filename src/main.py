import asyncio
import uvloop
import logging
import multiprocessing
import time
from multiprocessing import Queue

from src.scrapers.stockbit import StockbitLiveSource
from src.database_sqlite import SQLiteAdapter
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

async def trading_core(tick_queue: Queue):
    """The HFT Logic Loop (Runs on CPU Core 1)"""
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.info("Initializing HFT Engine...")

    # 1. Initialize Components
    db = SQLiteAdapter()
    await db.connect()

    # Switch to StockbitLiveSource
    # Note: Headless=True by default. Set False for debugging/login.
    data_source = StockbitLiveSource(symbol="BBRI", headless=True)
    data_source.queue = tick_queue # Inject Queue for real-time passing

    tda = TDAEngine(window_size=50)
    mc = MonteCarloEngine(simulations=500, horizon=5)
    notifier = DiscordNotifier(token=None)
    strategy = HybridStrategy(tda_engine=tda, mc_engine=mc)

    # Pre-fill Strategy with DB history
    await db.connect()
    history = await db.query_history("BBRI", 50)
    if history:
        strategy.load_initial_data([t.price for t in history])

    # 2. Start Services
    # Connect DataSource (This launches Playwright)
    # Ideally, we run data_source.connect() as a task because it blocks on while loop

    await notifier.start()

    logger.info("HFT Engine Live. Launching Scraper...")

    # Create background task for scraper
    scraper_task = asyncio.create_task(data_source.connect())

    try:
        while True:
            # We consume from the Queue populated by the Scraper
            # Check queue non-blocking
            while not tick_queue.empty():
                tick = tick_queue.get()

                if tick:
                    # 1. Persist (IO Bound)
                    await db.write_tick(tick)

                    # 2. Analyze & Execute (CPU Bound)
                    signal = await strategy.on_tick(tick)

                    if signal:
                        logger.info(f"⚡ ACTION: {signal['action']} | {signal['reason']}")
                        await notifier.send_signal(signal)

            # Zero-sleep yield
            await asyncio.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("HFT Engine Stopping...")
        scraper_task.cancel()
    except Exception as e:
        logger.error(f"Core Error: {e}")

def start_dashboard():
    """The Visual Server (Runs on CPU Core 2)"""
    # Dash reads from SQLite directly, so we don't need to pass the queue here
    # unless we wanted to implement a live update via websocket/server-sent-events
    # For now, polling DB is robust.
    run_dashboard_server()

if __name__ == "__main__":
    # IPC Queue
    tick_queue = multiprocessing.Queue()

    p1 = multiprocessing.Process(target=start_dashboard, name="Dashboard_Proc")
    p1.start()

    try:
        # Run the Async Trading Bot in the Main Process
        asyncio.run(trading_core(tick_queue))
    except KeyboardInterrupt:
        logger.info("Main Process Shutdown.")
        p1.terminate()
        p1.join()
