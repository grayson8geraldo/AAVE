# AAVE Trading Indicator Tournament — Final Report

## Methodology

| Parameter | Value |
|---|---|
| Asset | AAVE/USD |
| Data period | 2020-10-03 — 2025-04-09 (1650 days) |
| Training period | 2020-10-03 — 2023-12-02 (70%) |
| **Test period (OOS)** | **2023-12-03 — 2025-04-09 (30%)** |
| Starting capital | $200 |
| Commission | 0.1% per trade |
| Position sizing | 100% of equity |
| Directions | Long + Short |

### Anti-Overfitting Measures
1. **Walk-forward split** — parameters fixed BEFORE test period
2. **No optimization** — all indicator parameters are standard/classic values
3. **Ranking by OOS only** — training results used only for consistency check
4. **Composite score** — weighted metric (return, Sharpe, profit factor, win rate, drawdown)
5. **Consistency audit** — strategies with large train/test divergence flagged

---

## Tournament Results (Out-of-Sample)

| Rank | Strategy | $200 → | Return | Trades | Win Rate | Sharpe | PF | Max DD | Score |
|------|----------|--------|--------|--------|----------|--------|----|--------|-------|
| 🥇 1 | **Stochastic RSI** | **$311.96** | **+56.0%** | 12 | 50.0% | 1.19 | 2.61 | -16.6% | 0.4224 |
| 🥈 2 | Bollinger Breakout | $276.38 | +38.2% | 4 | 75.0% | 1.27 | 6.02 | -5.2% | 0.4222 |
| 🥉 3 | Triple EMA | $232.91 | +16.5% | 4 | 50.0% | 0.70 | 2.55 | -10.6% | 0.2540 |
| 4 | Williams Alligator | $217.97 | +9.0% | 7 | 42.9% | 0.37 | 1.33 | -27.0% | 0.1269 |
| 5 | RSI Momentum | $200.20 | +0.1% | 6 | 33.3% | 0.10 | 1.00 | -21.9% | 0.0588 |
| 6 | Ichimoku Cloud | $170.58 | -14.7% | 5 | 20.0% | -0.47 | 0.49 | -19.0% | -0.0677 |
| 7 | ADX Trend | $150.16 | -24.9% | 10 | 20.0% | -0.79 | 0.48 | -35.8% | -0.1507 |
| 8 | Supertrend | $141.89 | -29.1% | 7 | 14.3% | -1.12 | 0.24 | -38.1% | -0.2114 |
| 9 | MACD Histogram | $114.44 | -42.8% | 38 | 26.3% | -0.77 | 0.66 | -52.9% | -0.2126 |
| 10 | VWAP Mean Reversion | $121.64 | -39.2% | 11 | 18.2% | -1.25 | 0.29 | -41.6% | -0.2512 |

---

## Winner: Stochastic RSI

### Why It Won
- **Best absolute return**: $200 → $312 (+56%) on unseen data
- **Most consistent**: Train +58.5% vs Test +56.0% (only 2.5% degradation!)
- **Balanced metrics**: 50% win rate, 2.61 profit factor, 1.19 Sharpe
- **Controlled risk**: max drawdown only -16.6%
- **Good trade frequency**: 12 trades in 16 months (~1 trade every 5 weeks)

### How It Works
1. Calculates RSI(14), then applies Stochastic oscillator (14,3,3) to the RSI
2. Uses 50-period EMA as trend filter
3. **BUY**: StochRSI K crosses above D in oversold zone (<20) + price above EMA50
4. **SELL**: StochRSI K crosses below D in overbought zone (>80) + price below EMA50
5. Stop-loss: 5% | Take-profit: 10%

### Winner's Trade Log (Last 5 Trades)
| Entry | Exit | Direction | Entry$ | Exit$ | PnL |
|-------|------|-----------|--------|-------|-----|
| 2024-08-31 | 2024-09-11 | Long | $133.71 | $149.80 | +11.9% |
| 2024-10-09 | 2024-11-06 | Long | $153.57 | $176.84 | +15.1% |
| 2024-11-26 | 2024-12-01 | Long | $218.88 | $255.70 | +16.7% |
| 2024-12-19 | 2024-12-21 | Long | $288.72 | $270.94 | -6.3% |
| 2025-02-26 | 2025-03-23 | Short | $207.71 | $178.85 | +13.8% |

---

## Honourable Mentions

### 🥈 Bollinger Breakout (Score: 0.4222)
- Nearly tied with the winner (0.0002 difference!)
- **Lowest drawdown** of all profitable strategies (-5.2%)
- **Highest win rate**: 75%
- **Highest profit factor**: 6.02
- Weakness: only 4 trades — needs more market time to validate

### 🥉 Triple EMA (Score: 0.2540)
- **Most consistent strategy overall**: train +13.1% vs test +16.5% (test BEAT train!)
- Ultra-conservative, low drawdown (-10.6%)
- Best for risk-averse traders

---

## Overfitting Analysis

| Strategy | Train | Test | Gap | Verdict |
|----------|-------|------|-----|---------|
| **Stochastic RSI** | +58.5% | +56.0% | 2.5% | **Robust** |
| **Triple EMA** | +13.1% | +16.5% | -3.4% | **Robust** |
| **Bollinger Breakout** | +88.5% | +38.2% | 50.3% | OK |
| Supertrend | +355.4% | -29.1% | 384.4% | **Overfit** |
| ADX Trend | +397.7% | -24.9% | 422.7% | **Overfit** |

Key insight: Strategies that looked spectacular on training data (Supertrend +355%, ADX +398%) 
completely failed on unseen data. This proves the importance of out-of-sample testing.

---

## Recommendations for $200 Deposit

1. **Primary strategy**: Use **Stochastic RSI** on AAVE/USD daily chart
2. **Confirmation**: Cross-reference with **Bollinger Breakout** signals for high-confidence entries
3. **Risk management**: Never risk more than 5% per trade with stop-loss
4. **Compounding**: Reinvest profits to leverage the compound effect
5. **Timeframe**: Daily chart, expect ~1 trade every 5 weeks

### TradingView Setup
1. Open AAVE/USD on TradingView (daily timeframe)
2. Add indicator: `05_stochastic_rsi.pine` from the `/indicators` folder
3. Set alerts for buy/sell signals
4. Follow the signals with proper stop-loss/take-profit levels

---

## File Structure

```
AAVE/
├── aave_daily_ohlcv.csv          # Historical OHLCV data
├── generate_data.py               # Data generation script
├── backtest_engine.py             # Backtesting engine + 10 strategies
├── run_tournament.py              # Tournament runner + ranking
├── tournament_results.json        # Machine-readable results
├── REPORT.md                      # This report
└── indicators/                    # TradingView PineScript indicators
    ├── 01_rsi_momentum.pine
    ├── 02_macd_histogram.pine
    ├── 03_bollinger_breakout.pine
    ├── 04_triple_ema.pine
    ├── 05_stochastic_rsi.pine     ← WINNER
    ├── 06_supertrend.pine
    ├── 07_ichimoku_cloud.pine
    ├── 08_adx_trend.pine
    ├── 09_vwap_mean_reversion.pine
    └── 10_williams_alligator.pine
```

---

*Disclaimer: Past performance does not guarantee future results. Cryptocurrency trading involves substantial risk. This analysis is for educational purposes.*
