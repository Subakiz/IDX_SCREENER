import numpy as np
import scipy.stats as stats
from dataclasses import dataclass

@dataclass
class SimulationResult:
    median_path: np.ndarray
    lower_bound: np.ndarray # 5th percentile
    upper_bound: np.ndarray # 95th percentile
    ruin_probability: float

class MonteCarloEngine:
    def __init__(self, simulations=1000, horizon=5, dt=1/252):
        self.simulations = simulations
        self.horizon = horizon
        self.dt = dt

    def simulate_paths(self, start_price: float, mu: float, sigma: float) -> SimulationResult:
        """
        Simulates future price paths using Geometric Brownian Motion with Jump Diffusion.
        Vectorized using cumprod.
        """
        steps = self.horizon

        # 1. Generate Returns Components
        # Random normal shocks for GBM
        # shape: (simulations, steps)
        Z = np.random.normal(0, 1, (self.simulations, steps))

        # Drift component (constant per step)
        drift = (mu - 0.5 * sigma**2) * self.dt

        # Diffusion component
        diffusion = sigma * np.sqrt(self.dt) * Z

        # Jump Diffusion
        # Lambda = 0.01 (1% chance of jump per step)
        jump_prob = 0.01
        # Random choice for jumps: 1 if jump, 0 if not
        jumps = np.random.choice([0, 1], size=(self.simulations, steps), p=[1-jump_prob, jump_prob])
        # Jump magnitude
        jump_magnitude = np.random.normal(-0.1, 0.05, (self.simulations, steps)) # Bearish skew

        jump_impact = jumps * jump_magnitude

        # Total Log Returns
        log_returns = drift + diffusion + jump_impact

        # 2. Convert to Price Paths
        # Cumulative sum of log returns -> Cumulative product of exponential returns
        cum_log_returns = np.cumsum(log_returns, axis=1)
        price_paths = start_price * np.exp(cum_log_returns)

        # Prepend start_price to each path for t=0
        # shape becomes (simulations, steps + 1)
        price_paths = np.hstack([np.full((self.simulations, 1), start_price), price_paths])

        # 3. Apply Constraints (ARB)
        # Vectorized ARB check is tricky because it's path dependent (if t hits ARB, does it stick?)
        # For simplicity in vectorized form, we just cap the price at the limit.
        # Ideally, ARB lock means liquidity dries up, but for price simulation:
        arb_limit = start_price * 0.65
        price_paths = np.maximum(price_paths, arb_limit)

        # 4. Calculate Statistics
        median_path = np.median(price_paths, axis=0)
        lower_bound = np.percentile(price_paths, 5, axis=0)
        upper_bound = np.percentile(price_paths, 95, axis=0)

        # Ruin: hitting ARB or Stop Loss (say 5% down)
        stop_loss = start_price * 0.95
        # Check if any point in the path dropped below stop loss
        # axis=1 checks across time steps for each simulation
        ruin_counts = np.sum(np.any(price_paths < stop_loss, axis=1))
        ruin_prob = ruin_counts / self.simulations

        return SimulationResult(median_path, lower_bound, upper_bound, ruin_prob)

    def calculate_kelly_fraction(self, win_prob: float, win_loss_ratio: float, regime_modifier: float) -> float:
        """
        Calculates Optimal Kelly Fraction adjusted by regime.
        f* = (p*b - q) / b
        """
        if win_loss_ratio <= 0:
            return 0.0

        p = win_prob
        q = 1 - p
        b = win_loss_ratio

        kelly = (p * b - q) / b

        # Half-Kelly for safety
        kelly = max(0, kelly * 0.5)

        # Regime Adjustment (0.0 to 1.0)
        return kelly * regime_modifier
