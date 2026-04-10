"""
AAVE Backtesting Engine — FINAL v4
====================================
Key findings from 3 iterations:
- AAVE ATR ~5.5% daily -> SL must be >= 5%, TP 10-12% (2:1+ reward:risk)
- Fixed SL/TP outperforms trailing stops on AAVE (sharp moves + retracements)
- Selective signals > high frequency (quality over quantity)
- Ensembles of indicators increase frequency while maintaining quality

Walk-forward: train 70% / test 30%, NO optimization on test data.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Callable
import json


@dataclass
class Trade:
    entry_date: str
    exit_date: str
    direction: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_usd: float
    equity_after: float


@dataclass
class BacktestResult:
    strategy_name: str
    period: str
    initial_capital: float
    final_equity: float
    total_return_pct: float
    num_trades: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    avg_trade_duration: float
    trades_per_month: float
    trades: List[Trade] = field(default_factory=list)


class BacktestEngine:
    def __init__(self, df, initial_capital=200.0, commission_pct=0.1):
        self.df = df.copy()
        self.initial_capital = initial_capital
        self.comm = commission_pct / 100.0

    def run(self, func, name, sl=0.05, tp=0.12,
            train_end="2023-12-02", test_start="2023-12-03"):
        df = self.df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df['signal'] = func(df)

        train = df[df['date'] <= pd.Timestamp(train_end)].copy()
        test = df[df['date'] >= pd.Timestamp(test_start)].copy()
        return (self._sim(train, name, "train", sl, tp),
                self._sim(test, name, "test", sl, tp))

    def _sim(self, df, name, period, sl, tp):
        eq = self.initial_capital
        pos = 0  # 0=flat, 1=long, -1=short
        ep = 0.0  # entry price
        ed = ""   # entry date
        trades = []
        eq_curve = [eq]

        def close(date, exit_p, d):
            nonlocal eq, pos
            pnl = ((exit_p-ep)/ep if d=="long" else (ep-exit_p)/ep) - self.comm
            usd = eq * pnl
            eq = max(eq + usd, 1.0)
            trades.append(Trade(ed, date, d, round(ep,2), round(exit_p,2),
                                round(pnl*100,2), round(usd,2), round(eq,2)))
            pos = 0

        for i in range(len(df)):
            r = df.iloc[i]
            sig, c, h, l = r['signal'], r['close'], r['high'], r['low']
            date = str(r['date'].date())

            # Check SL/TP using intrabar high/low
            if pos == 1:
                if (l-ep)/ep <= -sl:
                    close(date, ep*(1-sl), "long")
                elif (h-ep)/ep >= tp:
                    close(date, ep*(1+tp), "long")
            elif pos == -1:
                if (ep-h)/ep <= -sl:
                    close(date, ep*(1+sl), "short")
                elif (ep-l)/ep >= tp:
                    close(date, ep*(1-tp), "short")

            # New signals
            if sig == 1 and pos != 1:
                if pos == -1: close(date, c, "short")
                pos, ep, ed = 1, c*(1+self.comm), date
            elif sig == -1 and pos != -1:
                if pos == 1: close(date, c, "long")
                pos, ep, ed = -1, c*(1-self.comm), date

            eq_curve.append(eq)

        if pos != 0:
            close(str(df.iloc[-1]['date'].date()), df.iloc[-1]['close'],
                  "long" if pos==1 else "short")

        return self._metrics(trades, eq_curve, name, period, df)

    def _metrics(self, trades, eq_curve, name, period, df):
        n = len(trades)
        eq = eq_curve[-1]
        if n == 0:
            return BacktestResult(name, period, self.initial_capital, round(eq,2),
                                  0,0,0,0,0,0,0,0,0,0,[])
        wins = [t for t in trades if t.pnl_pct > 0]
        losses = [t for t in trades if t.pnl_pct <= 0]
        wr = len(wins)/n*100
        aw = np.mean([t.pnl_pct for t in wins]) if wins else 0
        al = np.mean([t.pnl_pct for t in losses]) if losses else 0
        ec = np.array(eq_curve)
        pk = np.maximum.accumulate(ec)
        mdd = ((ec-pk)/pk*100).min()
        dr = np.diff(ec)/ec[:-1]
        sh = np.mean(dr)/np.std(dr)*np.sqrt(365) if len(dr)>1 and np.std(dr)>0 else 0
        gp = sum(t.pnl_usd for t in wins) if wins else 0
        gl = abs(sum(t.pnl_usd for t in losses)) if losses else 1
        pf = gp/gl if gl>0 else gp
        durs = [max((pd.Timestamp(t.exit_date)-pd.Timestamp(t.entry_date)).days,1) for t in trades]
        ad = np.mean(durs)
        td = (df['date'].iloc[-1]-df['date'].iloc[0]).days
        tpm = n/max(td/30,1)
        ret = (eq-self.initial_capital)/self.initial_capital*100
        return BacktestResult(name, period, self.initial_capital, round(eq,2),
                              round(ret,2), n, round(wr,2), round(aw,2), round(al,2),
                              round(mdd,2), round(sh,3), round(pf,2),
                              round(ad,1), round(tpm,1), trades)


# =====================================================================
# HELPERS
# =====================================================================
def _ema(s, p): return s.ewm(span=p, adjust=False).mean()
def _sma(s, p): return s.rolling(p, min_periods=p).mean()
def _rsi(s, p):
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1/p, min_periods=p, adjust=False).mean()
    return 100 - 100/(1+g/l.replace(0, np.nan))
def _atr(df, p):
    tr = np.maximum(df['high']-df['low'],
                    np.maximum(abs(df['high']-df['close'].shift(1)),
                               abs(df['low']-df['close'].shift(1))))
    return tr.rolling(p, min_periods=p).mean()
def _stoch(s, p):
    lo, hi = s.rolling(p).min(), s.rolling(p).max()
    return ((s-lo)/(hi-lo).replace(0, np.nan))*100
def _xo(a, b):  # crossover
    return (a > b) & (a.shift(1) <= b.shift(1))
def _xu(a, b):  # crossunder
    return (a < b) & (a.shift(1) >= b.shift(1))


# =====================================================================
# 10 STRATEGIES
# Mix of proven singles + ensembles for more frequency
# =====================================================================

# --- 1. StochRSI Classic (v1 winner, unchanged) ---
def s01_stochrsi(df):
    r = _rsi(df['close'], 14)
    sk = _sma(_stoch(r, 14), 3)
    sd = _sma(sk, 3)
    e50 = _ema(df['close'], 50)
    sig = pd.Series(0, index=df.index)
    sig[_xo(sk, sd) & (sk < 25) & (df['close'] > e50)] = 1
    sig[_xu(sk, sd) & (sk > 75) & (df['close'] < e50)] = -1
    return sig

# --- 2. StochRSI Widened — wider zones for more signals ---
def s02_stochrsi_wide(df):
    r = _rsi(df['close'], 14)
    sk = _sma(_stoch(r, 14), 3)
    sd = _sma(sk, 3)
    e30 = _ema(df['close'], 30)
    sig = pd.Series(0, index=df.index)
    sig[_xo(sk, sd) & (sk < 35) & (df['close'] > e30)] = 1
    sig[_xu(sk, sd) & (sk > 65) & (df['close'] < e30)] = -1
    return sig

# --- 3. Triple EMA (v1 #3, proven consistent) ---
def s03_triple_ema(df):
    e8, e21, e55 = _ema(df['close'],8), _ema(df['close'],21), _ema(df['close'],55)
    sig = pd.Series(0, index=df.index)
    sig[_xo(e8,e21) & (e21>e55)] = 1
    sig[_xu(e8,e21) & (e21<e55)] = -1
    return sig

# --- 4. MACD Histogram Cross Zero ---
def s04_macd(df):
    macd = _ema(df['close'],12) - _ema(df['close'],26)
    sl = _ema(macd, 9)
    hist = macd - sl
    z = pd.Series(0.0, index=df.index)
    sig = pd.Series(0, index=df.index)
    sig[_xo(hist, z)] = 1
    sig[_xu(hist, z)] = -1
    return sig

# --- 5. RSI + EMA20 Crossover ---
def s05_rsi_ema(df):
    r = _rsi(df['close'], 14)
    e = _ema(df['close'], 20)
    r50 = pd.Series(50.0, index=df.index)
    sig = pd.Series(0, index=df.index)
    sig[_xo(r, r50) & (df['close'] > e)] = 1
    sig[_xu(r, r50) & (df['close'] < e)] = -1
    return sig

# --- 6. Supertrend (classic, factor=3, ATR=10) ---
def s06_supertrend(df):
    a = _atr(df, 10)
    hl2 = (df['high']+df['low'])/2
    f = 3.0
    ub, lb = (hl2+f*a).copy(), (hl2-f*a).copy()
    d = pd.Series(1, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(a.iloc[i]): continue
        if not pd.isna(lb.iloc[i-1]) and df['close'].iloc[i-1]>lb.iloc[i-1]:
            lb.iloc[i] = max(lb.iloc[i], lb.iloc[i-1])
        if not pd.isna(ub.iloc[i-1]) and df['close'].iloc[i-1]<ub.iloc[i-1]:
            ub.iloc[i] = min(ub.iloc[i], ub.iloc[i-1])
        if d.iloc[i-1]==-1:
            d.iloc[i] = 1 if df['close'].iloc[i]<lb.iloc[i] else -1
        else:
            d.iloc[i] = -1 if df['close'].iloc[i]>ub.iloc[i] else 1
    sig = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if d.iloc[i]==-1 and d.iloc[i-1]==1: sig.iloc[i] = 1
        elif d.iloc[i]==1 and d.iloc[i-1]==-1: sig.iloc[i] = -1
    return sig

# --- 7. ADX + DI Crossover ---
def s07_adx_di(df):
    p = 14
    hi, lo, cl = df['high'], df['low'], df['close']
    tr = np.maximum(hi-lo, np.maximum(abs(hi-cl.shift(1)), abs(lo-cl.shift(1))))
    um, dm = hi-hi.shift(1), lo.shift(1)-lo
    pdm = pd.Series(np.where((um>dm)&(um>0), um, 0), index=df.index)
    mdm = pd.Series(np.where((dm>um)&(dm>0), dm, 0), index=df.index)
    at = tr.rolling(p).mean()
    pdi = 100*pdm.rolling(p).mean()/at.replace(0, np.nan)
    mdi = 100*mdm.rolling(p).mean()/at.replace(0, np.nan)
    dx = 100*abs(pdi-mdi)/(pdi+mdi).replace(0, np.nan)
    adx = dx.rolling(p).mean()
    sig = pd.Series(0, index=df.index)
    sig[_xo(pdi, mdi) & (adx > 25)] = 1
    sig[_xo(mdi, pdi) & (adx > 25)] = -1
    return sig

# --- 8. ENSEMBLE: StochRSI OR Triple EMA (union of best 2) ---
def s08_ensemble_top2(df):
    sig1 = s01_stochrsi(df)
    sig2 = s03_triple_ema(df)
    sig = pd.Series(0, index=df.index)
    # Take any signal from either strategy
    for i in range(len(df)):
        if sig1.iloc[i] != 0:
            sig.iloc[i] = sig1.iloc[i]
        elif sig2.iloc[i] != 0:
            sig.iloc[i] = sig2.iloc[i]
    return sig

# --- 9. ENSEMBLE: StochRSI OR MACD OR EMA (union of 3) ---
def s09_ensemble_3way(df):
    sig1 = s01_stochrsi(df)
    sig2 = s04_macd(df)
    sig3 = s03_triple_ema(df)
    sig = pd.Series(0, index=df.index)
    for i in range(len(df)):
        # Priority: StochRSI > Triple EMA > MACD
        if sig1.iloc[i] != 0:
            sig.iloc[i] = sig1.iloc[i]
        elif sig3.iloc[i] != 0:
            sig.iloc[i] = sig3.iloc[i]
        elif sig2.iloc[i] != 0:
            sig.iloc[i] = sig2.iloc[i]
    return sig

# --- 10. ENSEMBLE: All 5 base strategies — majority vote ---
def s10_ensemble_vote(df):
    sigs = [s01_stochrsi(df), s02_stochrsi_wide(df), s03_triple_ema(df),
            s05_rsi_ema(df), s04_macd(df)]
    sig = pd.Series(0, index=df.index)
    # Track last known signal from each strategy
    states = [0] * 5
    for i in range(len(df)):
        for j, s in enumerate(sigs):
            if s.iloc[i] != 0:
                states[j] = s.iloc[i]
        # Count current bullish/bearish states
        bulls = sum(1 for s in states if s == 1)
        bears = sum(1 for s in states if s == -1)
        # Majority (>= 3 of 5) triggers signal change
        if bulls >= 3:
            if i == 0 or sig.iloc[i-1] != 1:  # state change
                # Only fire if at least one NEW signal this bar
                if any(s.iloc[i] == 1 for s in sigs):
                    sig.iloc[i] = 1
        elif bears >= 3:
            if i == 0 or sig.iloc[i-1] != -1:
                if any(s.iloc[i] == -1 for s in sigs):
                    sig.iloc[i] = -1
    return sig


# =====================================================================
# REGISTRY: (func, sl_pct, tp_pct)
# =====================================================================
STRATEGIES = {
    "01_StochRSI":          (s01_stochrsi,        0.05, 0.12),
    "02_StochRSI_Wide":     (s02_stochrsi_wide,   0.05, 0.12),
    "03_Triple_EMA":        (s03_triple_ema,       0.05, 0.12),
    "04_MACD":              (s04_macd,             0.05, 0.12),
    "05_RSI_EMA":           (s05_rsi_ema,          0.05, 0.12),
    "06_Supertrend":        (s06_supertrend,       0.05, 0.12),
    "07_ADX_DI":            (s07_adx_di,           0.05, 0.12),
    "08_Ensemble_Top2":     (s08_ensemble_top2,    0.05, 0.12),
    "09_Ensemble_3way":     (s09_ensemble_3way,    0.05, 0.12),
    "10_Ensemble_Vote":     (s10_ensemble_vote,    0.05, 0.12),
}
