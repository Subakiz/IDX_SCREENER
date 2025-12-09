# Architectural Constraints & Directives

## 1. Core Architecture
- **Language**: Python 3.10+
- **Concurrency**: Must use `asyncio` with `uvloop` for the main event loop.
- **Design Pattern**: Producer-Consumer (Data Ingestion -> Strategy -> Execution).

## 2. Market Specifics (IDX)
- **Auto-Rejection (ARA/ARB)**:
  - Symmetric limits (approx 20-35% depending on price).
  - Risk Model must treat ARB Lock as a "Ruin State" (Zero Liquidity).
- **Lot Size**: 1 Lot = 100 Shares.
- **Tick Size**: Variable based on price fraction.
- **Execution**:
  - No official retail API.
  - Use "Option A": Semi-Automated via Discord Bot signals.
  - "Option B" (Grey-hat scraping) is reserved for experimental use only.

## 3. Technology Stack
- **Database**: QuestDB (InfluxDB Line Protocol) for high-speed time-series.
- **Math**:
  - **TDA**: `giotto-tda` for Persistent Homology ($L^1$ norms) to detect regimes.
  - **Risk**: Monte Carlo (GBM with Jump Diffusion) + Dynamic Kelly Criterion.
- **Visualization**: Plotly Dash for "Visual Alpha".

## 4. Strategy Logic
- **Macro**: TDA measures "Crash Topology". If $L^1$ norm > Threshold -> Crash Regime (Exit/Hedge).
- **Micro**: Monte Carlo predicts price cone. Buy if Price in Value Zone AND Order Book Imbalance > 0.3.

## 5. Development Guidelines
- Prioritize memory optimization (VPS constraint).
- Use `__slots__` for high-frequency objects.
- Mock external services (Brokers, GoAPI) if credentials are unavailable, but keep interfaces compatible.
