import discord
import asyncio
import logging

logger = logging.getLogger(__name__)

class DiscordNotifier:
    def __init__(self, token=None, channel_id=None):
        self.token = token
        self.channel_id = channel_id
        # We mock the client if no token provided
        self.client = discord.Client(intents=discord.Intents.default()) if token else None

    async def start(self):
        if self.token:
            asyncio.create_task(self.client.start(self.token))
            logger.info("Discord Bot Starting...")
        else:
            logger.info("Discord Bot running in MOCK mode (No Token)")

    async def send_signal(self, signal: dict):
        message = f"🚨 **SIGNAL ALERT** 🚨\n" \
                  f"**Action**: {signal['action']}\n" \
                  f"**Symbol**: {signal['symbol']}\n" \
                  f"**Price**: {signal['price']}\n" \
                  f"**Reason**: {signal['reason']}"

        logger.info(f"Sending Notification: {message}")

        if self.client and self.client.is_ready():
            channel = self.client.get_channel(self.channel_id)
            if channel:
                await channel.send(message)
        elif not self.token:
             # Mock send
             print(f"[DISCORD MOCK] Sent: {message}")
