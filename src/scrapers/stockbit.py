import asyncio
import json
import logging
import os
import time
from dataclasses import asdict
from typing import Optional, List

from playwright.async_api import async_playwright, Page, BrowserContext
from fake_useragent import UserAgent

from src.data_ingestion import DataSource, Tick

logger = logging.getLogger("STOCKBIT_SCRAPER")

class StockbitLiveSource(DataSource):
    def __init__(self, symbol="BBRI", headless=True):
        self.symbol = symbol
        self.headless = headless
        self.browser_context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.queue = None  # To be set by main.py
        self.running = False
        self.cookies_path = "stockbit_cookies.json"

    async def connect(self):
        """Launches browser, loads cookies, handles login, starts WSS sniffing."""
        logger.info(f"Connecting to Stockbit for {self.symbol}...")
        self.running = True

        ua = UserAgent()
        user_agent = ua.random

        async with async_playwright() as p:
            # Launch with Stealth Args
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars"
                ]
            )

            self.browser_context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1280, "height": 720}
            )

            # Load Cookies
            if os.path.exists(self.cookies_path):
                try:
                    with open(self.cookies_path, 'r') as f:
                        cookies = json.load(f)
                        await self.browser_context.add_cookies(cookies)
                    logger.info("Loaded session cookies.")
                except Exception as e:
                    logger.warning(f"Failed to load cookies: {e}")

            self.page = await self.browser_context.new_page()

            # WebSocket Interception
            self.page.on("websocket", self.on_websocket)

            try:
                # Go to chart page (trigger WSS connection)
                target_url = f"https://stockbit.com/symbol/{self.symbol}"
                await self.page.goto(target_url, timeout=60000)

                # Check login status
                if await self.page.locator("text=Login").is_visible():
                    logger.warning("Session invalid. Manual Login required!")
                    if self.headless:
                        logger.error("Cannot login in headless mode. Please run with headless=False to authenticate.")
                        return

                    # Wait for user to login manually
                    logger.info("Waiting 60s for manual login...")
                    await self.page.wait_for_timeout(60000)

                    # Save new cookies
                    cookies = await self.browser_context.cookies()
                    with open(self.cookies_path, 'w') as f:
                        json.dump(cookies, f)
                    logger.info("New cookies saved.")

                logger.info("Listening for WSS frames...")

                # Keep alive loop
                while self.running:
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Browser crashed: {e}")
            finally:
                await browser.close()

    def on_websocket(self, ws):
        """Called when a WebSocket is created."""
        # logger.debug(f"WS Created: {ws.url}")
        ws.on("framereceived", self.on_frame)

    def on_frame(self, frame):
        try:
            payload = frame.payload
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')

            # --- HANDLE SOCKET.IO PREFIX (The Fix) ---
            # Stockbit sends '42["trade",...]' which isn't valid JSON until stripped
            if not (payload.startswith('{') or payload.startswith('[')):
                import re
                # Look for the first JSON bracket
                match = re.search(r'[\\[\\{]', payload)
                if match:
                    payload = payload[match.start():]
                else:
                    return

            data = json.loads(payload)

            # Handle list format: ["event_name", {data}]
            if isinstance(data, list) and len(data) > 1:
                real_data = data[1]
                self.parse_and_enqueue(real_data)
            elif isinstance(data, dict):
                self.parse_and_enqueue(data)

        except Exception as e:
            pass # Keep streaming

    def parse_and_enqueue(self, data: dict):
        """Extracts fields and pushes Tick to Queue."""
        try:
            # MOCK PARSING LOGIC (Replace with real JSON paths)
            # Assuming data = {'symbol': 'BBRI', 'price': 4500, 'vol': 100, ...}

            # For demonstration, let's pretend we extracted these:
            price = float(data.get('price', 0))
            volume = int(data.get('volume', 0))
            bid_vol = int(data.get('bid_vol', 0))
            ask_vol = int(data.get('ask_vol', 0))

            if price > 0:
                tick = Tick(
                    symbol=self.symbol,
                    price=price,
                    volume=volume,
                    timestamp=time.time(),
                    bid_vol=bid_vol,
                    ask_vol=ask_vol
                )

                if self.queue:
                    self.queue.put(tick)
                    # logger.info(f"Tick enqueued: {price}")

        except Exception as e:
            logger.error(f"Tick conversion failed: {e}")

    async def get_tick(self) -> Tick:
        """Deprecated in favor of Queue push, but kept for interface compliance."""
        return None
