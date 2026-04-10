#!/usr/bin/env python3
"""
AAVE Indicator Tournament — FINAL v4
Single indicators + Ensembles for more frequency.
5% SL / 12% TP (proven optimal for AAVE daily volatility).
"""

import pandas as pd
import numpy as np
import json
from backtest_engine import BacktestEngine, STRATEGIES


def score(r):
    ret = r.total_return_pct / 100
    sh = min(max(r.sharpe_ratio, -1) / 3.0, 1.0)
    pf = min(r.profit_factor / 3.0, 1.0)
    wr = r.win_rate / 100
    dd = max(r.max_drawdown_pct / 100, -1.0)
    freq = min(r.trades_per_month / 4.0, 1.0)
    return round(0.25*ret + 0.20*sh + 0.15*pf + 0.10*wr + 0.15*dd + 0.15*freq, 4)


def main():
    print("=" * 100)
    print("   AAVE INDICATOR TOURNAMENT — FINAL")
    print("   Singles + Ensembles | $200 | SL=5% TP=12% | Walk-Forward")
    print("=" * 100)

    df = pd.read_csv("/home/user/AAVE/aave_daily_ohlcv.csv")
    eng = BacktestEngine(df, initial_capital=200.0, commission_pct=0.1)
    train_res, test_res = [], []

    for name, (func, sl, tp) in STRATEGIES.items():
        print(f"\n{'─'*80}")
        print(f"  {name}  (SL={sl*100:.0f}% / TP={tp*100:.0f}%)")
        print(f"{'─'*80}")
        try:
            tr, te = eng.run(func, name, sl=sl, tp=tp)
            train_res.append(tr)
            test_res.append(te)
            for lb, r in [("TRAIN", tr), ("TEST", te)]:
                print(f"  {lb}: ${r.initial_capital} -> ${r.final_equity:.2f} "
                      f"({r.total_return_pct:+.1f}%) | "
                      f"{r.num_trades} trades ({r.trades_per_month:.1f}/mo) | "
                      f"WR: {r.win_rate:.1f}% | PF: {r.profit_factor:.2f} | "
                      f"Sharpe: {r.sharpe_ratio:.2f} | DD: {r.max_drawdown_pct:.1f}%")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    # Ranking
    print("\n\n" + "=" * 100)
    print("   FINAL RANKING — OUT-OF-SAMPLE (Dec 2023 – Apr 2025) — $200 start")
    print("=" * 100)

    scored = [(r, score(r)) for r in test_res]
    scored.sort(key=lambda x: x[1], reverse=True)

    print(f"\n{'#':<3} {'Strategy':<22} {'$Final':<9} {'Return':<9} "
          f"{'Trades':<7} {'T/Mo':<6} {'WR%':<6} {'AvgW%':<8} {'AvgL%':<8} "
          f"{'Sharpe':<8} {'PF':<6} {'MaxDD':<8} {'Score':<7}")
    print("─" * 112)

    rankings = []
    for i, (r, sc) in enumerate(scored, 1):
        tag = {1:" <<< BEST", 2:" << 2nd", 3:" < 3rd"}.get(i, "")
        print(f"{i:<3} {r.strategy_name:<22} ${r.final_equity:<8.2f} "
              f"{r.total_return_pct:>+7.1f}%  {r.num_trades:<7} "
              f"{r.trades_per_month:<5.1f}  {r.win_rate:<5.1f}  "
              f"{r.avg_win_pct:>+6.2f}%  {r.avg_loss_pct:>+6.2f}%  "
              f"{r.sharpe_ratio:>7.3f}  {r.profit_factor:<5.2f}  "
              f"{r.max_drawdown_pct:>6.1f}%  {sc:>6.4f}{tag}")
        rankings.append({
            "rank": i, "strategy": r.strategy_name,
            "final_equity": r.final_equity, "return_pct": r.total_return_pct,
            "num_trades": r.num_trades, "trades_per_month": r.trades_per_month,
            "win_rate": r.win_rate, "avg_win_pct": r.avg_win_pct,
            "avg_loss_pct": r.avg_loss_pct, "sharpe_ratio": r.sharpe_ratio,
            "profit_factor": r.profit_factor, "max_drawdown_pct": r.max_drawdown_pct,
            "avg_trade_duration": r.avg_trade_duration, "score": sc,
        })

    # Winner
    w = scored[0][0]
    print(f"\n\n{'='*100}")
    print(f"   WINNER: {w.strategy_name}")
    print(f"{'='*100}")
    print(f"  Capital:      $200 -> ${w.final_equity:.2f} ({w.total_return_pct:+.1f}%)")
    print(f"  Trades:       {w.num_trades} ({w.trades_per_month:.1f}/month = "
          f"~{w.trades_per_month/4.3:.1f}/week)")
    print(f"  Win Rate:     {w.win_rate:.1f}%")
    print(f"  Avg Win:      {w.avg_win_pct:+.2f}%  |  Avg Loss: {w.avg_loss_pct:+.2f}%")
    if w.avg_loss_pct != 0:
        print(f"  Reward/Risk:  {abs(w.avg_win_pct/w.avg_loss_pct):.2f}x")
    print(f"  Sharpe:       {w.sharpe_ratio:.3f}  |  Profit Factor: {w.profit_factor:.2f}")
    print(f"  Max Drawdown: {w.max_drawdown_pct:.1f}%  |  Avg Duration: {w.avg_trade_duration:.1f} days")

    if w.trades:
        print(f"\n  All trades ({len(w.trades)}):")
        for t in w.trades:
            print(f"    {t.entry_date} -> {t.exit_date} | {t.direction:5s} | "
                  f"${t.entry_price:.2f} -> ${t.exit_price:.2f} | "
                  f"{t.pnl_pct:+.2f}% (${t.pnl_usd:+.2f}) | Eq: ${t.equity_after:.2f}")

    # Consistency
    print(f"\n\n{'='*100}")
    print(f"   OVERFITTING CHECK")
    print(f"{'='*100}")
    print(f"{'Strategy':<22} {'Train $':<10} {'Train Ret':<10} {'Test $':<10} {'Test Ret':<10} "
          f"{'Train T/Mo':<11} {'Test T/Mo':<11} {'Status'}")
    print("─" * 95)
    for tr, te in zip(train_res, test_res):
        if tr.total_return_pct > 0 and te.total_return_pct > 0: st = "ROBUST"
        elif te.total_return_pct > 0: st = "OK"
        elif tr.total_return_pct > 0 and te.total_return_pct < 0: st = "OVERFIT"
        else: st = "WEAK"
        print(f"{tr.strategy_name:<22} ${tr.final_equity:<9.2f} {tr.total_return_pct:>+8.1f}%  "
              f"${te.final_equity:<9.2f} {te.total_return_pct:>+8.1f}%  "
              f"{tr.trades_per_month:<10.1f}  {te.trades_per_month:<10.1f}  {st}")

    with open("/home/user/AAVE/tournament_results.json", "w") as f:
        json.dump({"version": "v4_final", "rankings": rankings,
                   "winner": rankings[0] if rankings else None}, f, indent=2)
    print(f"\nSaved to tournament_results.json")


if __name__ == "__main__":
    main()
