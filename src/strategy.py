import asyncio
import logging
import numpy as np
from src.data_ingestion import Tick
from src.tda_engine import TDAEngine
from src.mc_engine import MonteCarloEngine

logger = logging.getLogger(__name__)

class HybridStrategy:
    def __init__(self, tda_engine: TDAEngine, mc_engine: MonteCarloEngine):
        self.tda_engine = tda_engine
        self.mc_engine = mc_engine

        self.prices = []
        self.regime = "NEUTRAL"
        self.current_position = 0

        # TDA Thresholds (Calibrated via backtest in theory)
        self.THRESHOLD_CRASH = 100.0 # Arbitrary for simulation
        self.THRESHOLD_STABLE = 50.0

    def load_initial_data(self, prices: list[float]):
        """
        Pre-fill the price history to avoid warm-up delay.
        """
        self.prices = prices
        logger.info(f"Strategy initialized with {len(prices)} historical data points.")

    async def on_tick(self, tick: Tick) -> dict:
        """
        Process a new tick. Returns a Signal dict if action required, else None.
        """
        self.prices.append(tick.price)
        if len(self.prices) > 200:
            self.prices.pop(0)

        signal = None

        # 1. Macro: Regime Detection (TDA)
        # We don't run TDA on every tick, maybe every 50 ticks
        if len(self.prices) >= self.tda_engine.window_size and len(self.prices) % 10 == 0:
            l1_norm = await self.tda_engine.compute_landscape_norm(self.prices)
            logger.info(f"TDA L1 Norm: {l1_norm:.2f}")

            prev_regime = self.regime
            if l1_norm > self.THRESHOLD_CRASH:
                self.regime = "CRASH_RISK"
            elif l1_norm < self.THRESHOLD_STABLE:
                self.regime = "STABLE_TREND"
            else:
                self.regime = "NEUTRAL"

            if prev_regime != self.regime:
                logger.info(f"Regime Change: {prev_regime} -> {self.regime}")

        # 2. Micro: HFT Execution
        if self.regime == "STABLE_TREND" and len(self.prices) > 22:
            # Check Monte Carlo levels
            # Estimate short term vol
            price_window = np.array(self.prices[-21:]) # Take last 21 prices
            returns = np.diff(price_window) / price_window[:-1] # Returns length 20

            sigma = np.std(returns) * np.sqrt(252*390*60) # Annualized
            mu = np.mean(returns) * 252*390*60

            mc_res = self.mc_engine.simulate_paths(tick.price, mu, sigma)

            # Buy Zone: Below lower bound (Mean Reversion)
            buy_zone = mc_res.lower_bound[1] # Next step lower bound

            # Order Book Imbalance
            total_vol = tick.bid_vol + tick.ask_vol
            if total_vol > 0:
                obi = (tick.bid_vol - tick.ask_vol) / total_vol
            else:
                obi = 0.0 # Neutral if no data

            if tick.price <= buy_zone and obi > 0.3:
                # Calculate Size
                win_prob = 1.0 - mc_res.ruin_probability
                kelly = self.mc_engine.calculate_kelly_fraction(win_prob, 2.0, 1.0) # 2:1 Reward/Risk assumed

                if kelly > 0:
                    signal = {
                        "action": "BUY",
                        "symbol": tick.symbol,
                        "price": tick.price,
                        "size_fraction": kelly,
                        "reason": f"Regime: {self.regime} | Price {tick.price} <= Zone {buy_zone:.2f} | OBI {obi:.2f}"
                    }

        elif self.regime == "CRASH_RISK":
            if self.current_position > 0:
                signal = {
                    "action": "SELL",
                    "symbol": tick.symbol,
                    "price": tick.price,
                    "reason": "CRASH REGIME DETECTED"
                }

        return signal
