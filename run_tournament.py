#!/usr/bin/env python3
"""
AAVE Indicator Tournament
==========================
Runs all 10 strategies through walk-forward backtesting
and produces a final ranking based on OUT-OF-SAMPLE (test) performance.

Anti-overfitting measures:
1. Parameters are FIXED before test period
2. No parameter optimization on any data
3. Train/test split: 70%/30%
4. Ranking uses ONLY test period results
5. Multiple metrics used to avoid gaming a single metric
"""

import pandas as pd
import numpy as np
import json
from backtest_engine import BacktestEngine, STRATEGIES


def composite_score(result):
    """
    Weighted composite score for ranking.
    Rewards: return, Sharpe, profit factor, win rate
    Penalizes: drawdown, few trades
    """
    # Normalize components
    ret_score = result.total_return_pct / 100  # % return as decimal
    sharpe_score = min(result.sharpe_ratio / 3.0, 1.0)  # Cap at 3.0
    pf_score = min(result.profit_factor / 3.0, 1.0)  # Cap at 3.0
    wr_score = result.win_rate / 100  # Win rate as decimal
    dd_penalty = max(result.max_drawdown_pct / 100, -1.0)  # Drawdown penalty (negative)
    trade_penalty = 0 if result.num_trades >= 5 else -0.3  # Need at least 5 trades

    score = (
        0.30 * ret_score +          # 30% weight on return
        0.25 * sharpe_score +        # 25% weight on risk-adjusted return
        0.15 * pf_score +            # 15% weight on profit factor
        0.10 * wr_score +            # 10% weight on win rate
        0.15 * dd_penalty +          # 15% penalty for drawdown
        0.05 * trade_penalty         # 5% penalty for too few trades
    )
    return round(score, 4)


def run_tournament():
    print("=" * 80)
    print("   AAVE TRADING INDICATOR TOURNAMENT")
    print("   Walk-Forward Backtest | $200 Initial Capital | 0.1% Commission")
    print("=" * 80)

    # Load data
    df = pd.read_csv("/home/user/AAVE/aave_daily_ohlcv.csv")
    engine = BacktestEngine(df, initial_capital=200.0, commission_pct=0.1)

    train_results = []
    test_results = []

    # Run all strategies
    for name, func in STRATEGIES.items():
        print(f"\n{'─' * 60}")
        print(f"Running: {name}")
        print(f"{'─' * 60}")

        try:
            train_res, test_res = engine.run(func, name)
            train_results.append(train_res)
            test_results.append(test_res)

            print(f"  TRAIN: ${train_res.initial_capital} → ${train_res.final_equity:.2f} "
                  f"({train_res.total_return_pct:+.1f}%) | "
                  f"{train_res.num_trades} trades | WR: {train_res.win_rate:.1f}% | "
                  f"MaxDD: {train_res.max_drawdown_pct:.1f}%")
            print(f"  TEST:  ${test_res.initial_capital} → ${test_res.final_equity:.2f} "
                  f"({test_res.total_return_pct:+.1f}%) | "
                  f"{test_res.num_trades} trades | WR: {test_res.win_rate:.1f}% | "
                  f"MaxDD: {test_res.max_drawdown_pct:.1f}%")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    # =====================================================================
    # TOURNAMENT RANKING (based on TEST results only)
    # =====================================================================
    print("\n\n" + "=" * 80)
    print("   TOURNAMENT RESULTS — OUT-OF-SAMPLE (TEST PERIOD)")
    print("   Period: 2023-12-03 to 2025-04-09 | Starting Capital: $200")
    print("=" * 80)

    # Calculate composite scores
    scored = []
    for r in test_results:
        score = composite_score(r)
        scored.append((r, score))

    # Sort by composite score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    print(f"\n{'Rank':<5} {'Strategy':<25} {'Final $':<10} {'Return%':<10} "
          f"{'Trades':<8} {'WinRate%':<10} {'Sharpe':<8} {'PF':<8} "
          f"{'MaxDD%':<10} {'Score':<8}")
    print("─" * 110)

    rankings = []
    for rank, (r, score) in enumerate(scored, 1):
        medal = ""
        if rank == 1: medal = " 🥇"
        elif rank == 2: medal = " 🥈"
        elif rank == 3: medal = " 🥉"

        print(f"{rank:<5} {r.strategy_name:<25} ${r.final_equity:<9.2f} "
              f"{r.total_return_pct:<+9.1f}  {r.num_trades:<8} "
              f"{r.win_rate:<9.1f}  {r.sharpe_ratio:<7.3f}  "
              f"{r.profit_factor:<7.2f}  {r.max_drawdown_pct:<9.1f}  "
              f"{score:<7.4f}{medal}")

        rankings.append({
            "rank": rank,
            "strategy": r.strategy_name,
            "final_equity": r.final_equity,
            "return_pct": r.total_return_pct,
            "num_trades": r.num_trades,
            "win_rate": r.win_rate,
            "sharpe_ratio": r.sharpe_ratio,
            "profit_factor": r.profit_factor,
            "max_drawdown_pct": r.max_drawdown_pct,
            "avg_trade_duration_days": r.avg_trade_duration,
            "composite_score": score,
            "avg_win_pct": r.avg_win_pct,
            "avg_loss_pct": r.avg_loss_pct,
        })

    # =====================================================================
    # DETAILED WINNER ANALYSIS
    # =====================================================================
    winner = scored[0][0]
    print(f"\n\n{'=' * 80}")
    print(f"   WINNER: {winner.strategy_name}")
    print(f"{'=' * 80}")
    print(f"\n  Starting Capital:    ${winner.initial_capital}")
    print(f"  Final Equity:        ${winner.final_equity:.2f}")
    print(f"  Total Return:        {winner.total_return_pct:+.2f}%")
    print(f"  Number of Trades:    {winner.num_trades}")
    print(f"  Win Rate:            {winner.win_rate:.1f}%")
    print(f"  Avg Win:             {winner.avg_win_pct:+.2f}%")
    print(f"  Avg Loss:            {winner.avg_loss_pct:.2f}%")
    print(f"  Profit Factor:       {winner.profit_factor:.2f}")
    print(f"  Sharpe Ratio:        {winner.sharpe_ratio:.3f}")
    print(f"  Max Drawdown:        {winner.max_drawdown_pct:.2f}%")
    print(f"  Avg Trade Duration:  {winner.avg_trade_duration:.1f} days")

    if winner.trades:
        print(f"\n  Last 5 trades:")
        for t in winner.trades[-5:]:
            print(f"    {t.entry_date} → {t.exit_date} | {t.direction:5s} | "
                  f"${t.entry_price:.2f} → ${t.exit_price:.2f} | "
                  f"PnL: {t.pnl_pct:+.2f}% (${t.pnl_usd:+.2f})")

    # =====================================================================
    # TRAIN vs TEST CONSISTENCY CHECK
    # =====================================================================
    print(f"\n\n{'=' * 80}")
    print(f"   OVERFITTING CHECK: TRAIN vs TEST CONSISTENCY")
    print(f"{'=' * 80}")
    print(f"\n{'Strategy':<25} {'Train Return%':<15} {'Test Return%':<15} "
          f"{'Degradation':<15} {'Consistent?':<12}")
    print("─" * 80)

    for tr, te in zip(train_results, test_results):
        degradation = tr.total_return_pct - te.total_return_pct
        # A strategy is "consistent" if test performance is within reasonable range
        consistent = "YES" if (te.total_return_pct > 0 or
                               abs(degradation) < abs(tr.total_return_pct) * 0.7) else "NO"
        print(f"{tr.strategy_name:<25} {tr.total_return_pct:<+14.1f}  "
              f"{te.total_return_pct:<+14.1f}  {degradation:<+14.1f}  {consistent:<12}")

    # Save results to JSON
    output = {
        "methodology": {
            "train_period": "2020-10-03 to 2023-12-02",
            "test_period": "2023-12-03 to 2025-04-09",
            "initial_capital": 200,
            "commission_pct": 0.1,
            "position_sizing": "100% of equity",
            "anti_overfitting": [
                "Walk-forward split (70/30)",
                "Fixed parameters (no optimization)",
                "Ranking based on OUT-OF-SAMPLE only",
                "Multiple metrics in composite score",
                "Consistency check (train vs test)"
            ]
        },
        "rankings": rankings,
        "winner": rankings[0] if rankings else None
    }

    with open("/home/user/AAVE/tournament_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n\nResults saved to tournament_results.json")

    return output


if __name__ == "__main__":
    run_tournament()
