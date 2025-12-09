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
        """
        # Time steps
        steps = self.horizon

        # Initialize paths
        # shape: (simulations, steps + 1)
        prices = np.zeros((self.simulations, steps + 1))
        prices[:, 0] = start_price

        # Vectorized simulation
        # Random normal shocks
        Z = np.random.normal(0, 1, (self.simulations, steps))

        # Jumps (Poisson process approx)
        # Lambda = 0.01 (1% chance of jump per step)
        jump_prob = 0.01
        jumps = np.random.choice([0, 1], size=(self.simulations, steps), p=[1-jump_prob, jump_prob])
        jump_magnitude = np.random.normal(-0.1, 0.05, (self.simulations, steps)) # Bearish skew for jumps

        for t in range(steps):
            # GBM component
            drift = (mu - 0.5 * sigma**2) * self.dt
            diffusion = sigma * np.sqrt(self.dt) * Z[:, t]

            # Jump component
            jump_impact = jumps[:, t] * jump_magnitude[:, t]

            # Update prices
            ret = drift + diffusion + jump_impact
            prices[:, t+1] = prices[:, t] * np.exp(ret)

            # Apply ARB limits (simplified -35% from start approx)
            # If price drops > 35% from start, it locks
            arb_limit = start_price * 0.65
            prices[:, t+1] = np.maximum(prices[:, t+1], arb_limit)

        # Calculate statistics
        median_path = np.median(prices, axis=0)
        lower_bound = np.percentile(prices, 5, axis=0)
        upper_bound = np.percentile(prices, 95, axis=0)

        # Ruin: hitting ARB or Stop Loss (say 5% down)
        stop_loss = start_price * 0.95
        # Check if any point in the path dropped below stop loss
        ruin_counts = np.sum(np.any(prices < stop_loss, axis=1))
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
