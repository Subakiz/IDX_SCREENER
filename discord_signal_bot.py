import argparse
import os
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

import discord
from discord.ext import commands

CURRENCY_PREFIX = os.environ.get("CURRENCY_PREFIX", "Rp")
T = TypeVar("T", int, float)


@dataclass(slots=True)
class TradeSignal:
    symbol: str
    action: str
    entry: float
    stop_loss: float
    size_lots: int
    note: Optional[str] = None
    broker_url: Optional[str] = None


def _format_price(value: float) -> str:
    return f"{CURRENCY_PREFIX} {value:,.2f}"


def _coerce_env_number(raw: Optional[str], cast: Callable[[str], T], env_name: str) -> Optional[T]:
    if raw is None:
        return None
    try:
        return cast(raw)
    except Exception as exc:
        raise SystemExit(f"{env_name} must be numeric; received {raw!r}") from exc


def _positive_float(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{raw!r} is not a valid number.") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero.")
    return value


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{raw!r} is not a valid integer.") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero.")
    return value


def _read_timeout_seconds() -> int:
    timeout = _coerce_env_number(os.environ.get("VIEW_TIMEOUT_SECONDS"), _positive_int, "VIEW_TIMEOUT_SECONDS")
    return timeout or 3600


VIEW_TIMEOUT_SECONDS = _read_timeout_seconds()


def build_signal_embed(signal: TradeSignal) -> discord.Embed:
    action = signal.action.upper()
    if action == "BUY":
        color = discord.Color.green()
    elif action == "SELL":
        color = discord.Color.red()
    else:
        color = discord.Color.blurple()
    embed = discord.Embed(
        title=f"{action} {signal.symbol}",
        description="Semi-automated trade signal",
        color=color,
    )
    embed.add_field(name="Entry", value=_format_price(signal.entry))
    embed.add_field(name="Stop Loss", value=_format_price(signal.stop_loss))
    embed.add_field(name="Size", value=f"{signal.size_lots} lots")
    if signal.note:
        embed.add_field(name="Note", value=signal.note, inline=False)
    return embed


class AckButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(style=discord.ButtonStyle.primary, label="Mark Executed", custom_id="signal_ack")

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "Execution acknowledged. Please finalize the order in your broker app.",
            ephemeral=True,
        )


class AckView(discord.ui.View):
    def __init__(self, broker_url: Optional[str] = None) -> None:
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        if broker_url:
            self.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label="Open Broker",
                    url=broker_url,
                )
            )
        self.add_item(AckButton())


class SignalBot(commands.Bot):
    def __init__(self, channel_id: int, initial_signal: Optional[TradeSignal] = None) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.channel_id = channel_id
        self.initial_signal = initial_signal
        self._channel: Optional[discord.abc.Messageable] = None

    async def on_ready(self) -> None:
        await self._ensure_channel()
        if self.initial_signal:
            try:
                await self.publish_signal(self.initial_signal)
            except discord.HTTPException as exc:
                raise SystemExit(f"Failed to send initial signal: {exc}") from exc

    async def _ensure_channel(self) -> discord.abc.Messageable:
        if self._channel:
            return self._channel
        try:
            channel = self.get_channel(self.channel_id)
            if channel is None:
                channel = await self.fetch_channel(self.channel_id)
        except discord.NotFound as exc:
            raise SystemExit(f"Channel {self.channel_id} was not found or the bot cannot access it.") from exc
        except discord.Forbidden as exc:
            raise SystemExit(f"Bot lacks permission to access channel {self.channel_id}.") from exc
        except discord.HTTPException as exc:
            raise SystemExit(f"Failed to fetch channel {self.channel_id}: {exc}") from exc
        if not isinstance(channel, discord.abc.Messageable):
            raise SystemExit(f"Channel {self.channel_id} cannot receive messages.")
        self._channel = channel
        return channel

    async def publish_signal(self, signal: TradeSignal) -> None:
        channel = await self._ensure_channel()
        embed = build_signal_embed(signal)
        view = AckView(signal.broker_url)
        await channel.send(embed=embed, view=view)


def _parse_args() -> TradeSignal:
    env_entry = _coerce_env_number(os.environ.get("TRADE_ENTRY"), _positive_float, "TRADE_ENTRY")
    env_stop = _coerce_env_number(os.environ.get("TRADE_STOP"), _positive_float, "TRADE_STOP")
    env_size = _coerce_env_number(os.environ.get("TRADE_SIZE_LOTS"), _positive_int, "TRADE_SIZE_LOTS")

    parser = argparse.ArgumentParser(description="Dispatch a trade signal to Discord.")
    parser.add_argument("--symbol", default=os.environ.get("TRADE_SYMBOL", "BBRI"), help="Ticker symbol, e.g. BBRI.JK")
    parser.add_argument("--action", default=os.environ.get("TRADE_ACTION", "BUY"), help="BUY or SELL")
    parser.add_argument(
        "--entry",
        type=_positive_float,
        default=env_entry,
        required=env_entry is None,
        help="Entry price (required unless TRADE_ENTRY is set)",
    )
    parser.add_argument(
        "--stop",
        type=_positive_float,
        default=env_stop,
        required=env_stop is None,
        help="Stop loss price (required unless TRADE_STOP is set)",
    )
    parser.add_argument(
        "--size",
        type=_positive_int,
        default=env_size,
        required=env_size is None,
        help="Order size in lots (required unless TRADE_SIZE_LOTS is set)",
    )
    parser.add_argument("--note", default=os.environ.get("TRADE_NOTE"), help="Optional free-form note")
    parser.add_argument(
        "--broker-url",
        default=os.environ.get("BROKER_URL"),
        help="Optional link button destination (e.g., broker trade ticket).",
    )
    args = parser.parse_args()
    return TradeSignal(
        symbol=args.symbol,
        action=args.action,
        entry=args.entry,
        stop_loss=args.stop,
        size_lots=args.size,
        note=args.note,
        broker_url=args.broker_url,
    )


def main() -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")
    if not token or not channel_id:
        raise SystemExit("DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID environment variables are required.")

    try:
        channel_id_int = int(channel_id)
    except ValueError as exc:
        raise SystemExit("DISCORD_CHANNEL_ID must be numeric.") from exc

    signal = _parse_args()
    bot = SignalBot(channel_id_int, initial_signal=signal)
    bot.run(token)

if __name__ == "__main__":
    main()
