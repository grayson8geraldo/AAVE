"""
AAVE Trading Indicator Backtesting Engine
==========================================
Fair walk-forward backtesting with NO parameter optimization on test data.

Methodology:
- Training period: 2020-10-03 to 2023-12-02 (used ONLY to verify indicator logic works)
- Test period: 2023-12-03 to 2025-04-09 (untouched, used for final ranking)
- All indicator parameters are FIXED before test period begins
- Commission: 0.1% per trade (realistic crypto exchange fee)
- Starting capital: $200
- Position sizing: 100% of equity per trade (aggressive, for small account growth)
- Both long and short trades allowed
- No look-ahead bias
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import json


@dataclass
class Trade:
    entry_date: str
    exit_date: str
    direction: str  # "long" or "short"
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_usd: float
    equity_after: float


@dataclass
class BacktestResult:
    strategy_name: str
    period: str  # "train" or "test"
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
    trades: List[Trade] = field(default_factory=list)


class BacktestEngine:
    def __init__(self, df: pd.DataFrame, initial_capital: float = 200.0,
                 commission_pct: float = 0.1):
        self.df = df.copy()
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct / 100.0

    def run(self, strategy_func, strategy_name: str,
            train_end_date: str = "2023-12-02",
            test_start_date: str = "2023-12-03") -> Tuple[BacktestResult, BacktestResult]:
        """Run backtest on both train and test periods."""
        df = self.df.copy()
        df['date'] = pd.to_datetime(df['date'])

        # Generate signals on FULL dataset (indicators need history)
        signals = strategy_func(df)
        df['signal'] = signals  # 1 = buy, -1 = sell, 0 = hold

        # Split AFTER signal generation (signals use only past data by construction)
        train_mask = df['date'] <= pd.Timestamp(train_end_date)
        test_mask = df['date'] >= pd.Timestamp(test_start_date)

        train_result = self._simulate(df[train_mask].copy(), strategy_name, "train")
        test_result = self._simulate(df[test_mask].copy(), strategy_name, "test")

        return train_result, test_result

    def _simulate(self, df: pd.DataFrame, name: str, period: str) -> BacktestResult:
        """Simulate trading on a given period."""
        equity = self.initial_capital
        position = 0  # 0 = flat, 1 = long, -1 = short
        entry_price = 0.0
        entry_date = ""
        entry_idx = 0
        trades = []
        equity_curve = [equity]
        peak_equity = equity

        for i in range(len(df)):
            row = df.iloc[i]
            signal = row['signal']
            price = row['close']
            date = str(row['date'].date())

            # Check stop-loss / take-profit first
            if position != 0:
                if position == 1:  # Long
                    pnl_pct = (price - entry_price) / entry_price
                    # Stop loss at -5% or take profit at varying levels
                    if pnl_pct <= -0.05 or pnl_pct >= 0.12:
                        exit_pnl = pnl_pct - self.commission_pct
                        pnl_usd = equity * exit_pnl
                        equity += pnl_usd
                        equity = max(equity, 1.0)  # Can't go below $1
                        trades.append(Trade(entry_date, date, "long",
                                            entry_price, price, exit_pnl * 100,
                                            pnl_usd, equity))
                        position = 0
                elif position == -1:  # Short
                    pnl_pct = (entry_price - price) / entry_price
                    if pnl_pct <= -0.05 or pnl_pct >= 0.12:
                        exit_pnl = pnl_pct - self.commission_pct
                        pnl_usd = equity * exit_pnl
                        equity += pnl_usd
                        equity = max(equity, 1.0)
                        trades.append(Trade(entry_date, date, "short",
                                            entry_price, price, exit_pnl * 100,
                                            pnl_usd, equity))
                        position = 0

            # Process new signals
            if signal == 1 and position <= 0:
                # Close short if open
                if position == -1:
                    pnl_pct = (entry_price - price) / entry_price - self.commission_pct
                    pnl_usd = equity * pnl_pct
                    equity += pnl_usd
                    equity = max(equity, 1.0)
                    trades.append(Trade(entry_date, date, "short",
                                        entry_price, price, pnl_pct * 100,
                                        pnl_usd, equity))
                # Enter long
                position = 1
                entry_price = price * (1 + self.commission_pct)
                entry_date = date
                entry_idx = i

            elif signal == -1 and position >= 0:
                # Close long if open
                if position == 1:
                    pnl_pct = (price - entry_price) / entry_price - self.commission_pct
                    pnl_usd = equity * pnl_pct
                    equity += pnl_usd
                    equity = max(equity, 1.0)
                    trades.append(Trade(entry_date, date, "long",
                                        entry_price, price, pnl_pct * 100,
                                        pnl_usd, equity))
                # Enter short
                position = -1
                entry_price = price * (1 - self.commission_pct)
                entry_date = date
                entry_idx = i

            equity_curve.append(equity)
            peak_equity = max(peak_equity, equity)

        # Close any remaining position
        if position != 0:
            price = df.iloc[-1]['close']
            date = str(df.iloc[-1]['date'].date())
            if position == 1:
                pnl_pct = (price - entry_price) / entry_price - self.commission_pct
                direction = "long"
            else:
                pnl_pct = (entry_price - price) / entry_price - self.commission_pct
                direction = "short"
            pnl_usd = equity * pnl_pct
            equity += pnl_usd
            equity = max(equity, 1.0)
            trades.append(Trade(entry_date, date, direction,
                                entry_price, price, pnl_pct * 100,
                                pnl_usd, equity))

        # Calculate metrics
        num_trades = len(trades)
        if num_trades == 0:
            return BacktestResult(name, period, self.initial_capital, equity,
                                  0, 0, 0, 0, 0, 0, 0, 0, 0, [])

        wins = [t for t in trades if t.pnl_pct > 0]
        losses = [t for t in trades if t.pnl_pct <= 0]
        win_rate = len(wins) / num_trades * 100

        avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
        avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0

        # Max drawdown from equity curve
        ec = np.array(equity_curve)
        peak = np.maximum.accumulate(ec)
        drawdown = (ec - peak) / peak * 100
        max_dd = drawdown.min()

        # Sharpe ratio (daily returns from equity curve)
        daily_returns = np.diff(ec) / ec[:-1]
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            sharpe = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(365)
        else:
            sharpe = 0

        # Profit factor
        gross_profit = sum(t.pnl_usd for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl_usd for t in losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit

        # Average trade duration (in bars/days)
        durations = []
        for t in trades:
            d1 = pd.Timestamp(t.entry_date)
            d2 = pd.Timestamp(t.exit_date)
            durations.append((d2 - d1).days)
        avg_duration = np.mean(durations) if durations else 0

        total_return = (equity - self.initial_capital) / self.initial_capital * 100

        return BacktestResult(
            strategy_name=name,
            period=period,
            initial_capital=self.initial_capital,
            final_equity=round(equity, 2),
            total_return_pct=round(total_return, 2),
            num_trades=num_trades,
            win_rate=round(win_rate, 2),
            avg_win_pct=round(avg_win, 2),
            avg_loss_pct=round(avg_loss, 2),
            max_drawdown_pct=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 3),
            profit_factor=round(profit_factor, 2),
            avg_trade_duration=round(avg_duration, 1),
            trades=trades
        )


# =====================================================================
# 10 STRATEGY SIGNAL GENERATORS
# Each function takes a DataFrame and returns a signal series
# 1 = buy, -1 = sell, 0 = hold
# ALL parameters are HARDCODED (no optimization on test data)
# =====================================================================

def compute_rsi(series, period):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def compute_sma(series, period):
    return series.rolling(window=period, min_periods=period).mean()


def compute_atr(df, period):
    high, low, close = df['high'], df['low'], df['close']
    tr = np.maximum(high - low,
                    np.maximum(abs(high - close.shift(1)),
                               abs(low - close.shift(1))))
    return tr.rolling(window=period, min_periods=period).mean()


def compute_stoch(series, period):
    lowest = series.rolling(window=period).min()
    highest = series.rolling(window=period).max()
    denom = highest - lowest
    return ((series - lowest) / denom.replace(0, np.nan)) * 100


# --- Strategy 1: RSI Momentum ---
def strategy_rsi_momentum(df):
    rsi = compute_rsi(df['close'], 14)
    ema50 = compute_ema(df['close'], 50)
    signals = pd.Series(0, index=df.index)

    for i in range(1, len(df)):
        if pd.isna(rsi.iloc[i]) or pd.isna(ema50.iloc[i]):
            continue
        # Long: RSI crosses above 35 and price above EMA50
        if rsi.iloc[i] > 35 and rsi.iloc[i-1] <= 35 and df['close'].iloc[i] > ema50.iloc[i]:
            signals.iloc[i] = 1
        # Short: RSI crosses below 65 and price below EMA50
        elif rsi.iloc[i] < 65 and rsi.iloc[i-1] >= 65 and df['close'].iloc[i] < ema50.iloc[i]:
            signals.iloc[i] = -1
    return signals


# --- Strategy 2: MACD Histogram Reversal ---
def strategy_macd_histogram(df):
    ema12 = compute_ema(df['close'], 12)
    ema26 = compute_ema(df['close'], 26)
    macd_line = ema12 - ema26
    signal_line = compute_ema(macd_line, 9)
    histogram = macd_line - signal_line

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(histogram.iloc[i]):
            continue
        # Long: histogram crosses above zero
        if histogram.iloc[i] > 0 and histogram.iloc[i-1] <= 0:
            signals.iloc[i] = 1
        # Short: histogram crosses below zero
        elif histogram.iloc[i] < 0 and histogram.iloc[i-1] >= 0:
            signals.iloc[i] = -1
    return signals


# --- Strategy 3: Bollinger Band Breakout ---
def strategy_bollinger_breakout(df):
    sma20 = compute_sma(df['close'], 20)
    std20 = df['close'].rolling(window=20).std()
    upper = sma20 + 2.0 * std20
    lower = sma20 - 2.0 * std20
    bandwidth = (upper - lower) / sma20
    bw_sma = compute_sma(bandwidth, 20)
    vol_ma = compute_sma(df['volume'], 20)

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(upper.iloc[i]) or pd.isna(bw_sma.iloc[i]):
            continue
        is_squeeze = bandwidth.iloc[i-1] < bw_sma.iloc[i-1] * 0.75 if not pd.isna(bw_sma.iloc[i-1]) else False
        high_vol = df['volume'].iloc[i] > vol_ma.iloc[i] * 1.5 if not pd.isna(vol_ma.iloc[i]) else False

        if df['close'].iloc[i] > upper.iloc[i] and is_squeeze and high_vol:
            signals.iloc[i] = 1
        elif df['close'].iloc[i] < lower.iloc[i] and is_squeeze and high_vol:
            signals.iloc[i] = -1
    return signals


# --- Strategy 4: Triple EMA Crossover ---
def strategy_triple_ema(df):
    ema8 = compute_ema(df['close'], 8)
    ema21 = compute_ema(df['close'], 21)
    ema55 = compute_ema(df['close'], 55)

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(ema55.iloc[i]):
            continue
        # Long: fast crosses above mid, mid above slow
        if (ema8.iloc[i] > ema21.iloc[i] and ema8.iloc[i-1] <= ema21.iloc[i-1]
                and ema21.iloc[i] > ema55.iloc[i]):
            signals.iloc[i] = 1
        # Short: fast crosses below mid, mid below slow
        elif (ema8.iloc[i] < ema21.iloc[i] and ema8.iloc[i-1] >= ema21.iloc[i-1]
              and ema21.iloc[i] < ema55.iloc[i]):
            signals.iloc[i] = -1
    return signals


# --- Strategy 5: Stochastic RSI ---
def strategy_stochastic_rsi(df):
    rsi = compute_rsi(df['close'], 14)
    stoch_k_raw = compute_stoch(rsi, 14)
    stoch_k = compute_sma(stoch_k_raw, 3)
    stoch_d = compute_sma(stoch_k, 3)
    ema50 = compute_ema(df['close'], 50)

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(stoch_k.iloc[i]) or pd.isna(stoch_d.iloc[i]) or pd.isna(ema50.iloc[i]):
            continue
        # Long: K crosses above D in oversold, price above EMA
        if (stoch_k.iloc[i] > stoch_d.iloc[i] and stoch_k.iloc[i-1] <= stoch_d.iloc[i-1]
                and stoch_k.iloc[i] < 20 and df['close'].iloc[i] > ema50.iloc[i]):
            signals.iloc[i] = 1
        # Short: K crosses below D in overbought, price below EMA
        elif (stoch_k.iloc[i] < stoch_d.iloc[i] and stoch_k.iloc[i-1] >= stoch_d.iloc[i-1]
              and stoch_k.iloc[i] > 80 and df['close'].iloc[i] < ema50.iloc[i]):
            signals.iloc[i] = -1
    return signals


# --- Strategy 6: Supertrend ---
def strategy_supertrend(df):
    atr = compute_atr(df, 10)
    hl2 = (df['high'] + df['low']) / 2
    factor = 3.0

    upper_band = hl2 + factor * atr
    lower_band = hl2 - factor * atr

    supertrend = pd.Series(0.0, index=df.index)
    direction = pd.Series(1, index=df.index)  # 1=down, -1=up

    for i in range(1, len(df)):
        if pd.isna(atr.iloc[i]):
            supertrend.iloc[i] = 0
            continue

        # Adjust bands
        if lower_band.iloc[i] < lower_band.iloc[i-1] and df['close'].iloc[i-1] > lower_band.iloc[i-1]:
            lower_band.iloc[i] = lower_band.iloc[i-1]
        if upper_band.iloc[i] > upper_band.iloc[i-1] and df['close'].iloc[i-1] < upper_band.iloc[i-1]:
            upper_band.iloc[i] = upper_band.iloc[i-1]

        if direction.iloc[i-1] == -1:  # Was uptrend
            if df['close'].iloc[i] < lower_band.iloc[i]:
                direction.iloc[i] = 1  # Switch to downtrend
                supertrend.iloc[i] = upper_band.iloc[i]
            else:
                direction.iloc[i] = -1
                supertrend.iloc[i] = lower_band.iloc[i]
        else:  # Was downtrend
            if df['close'].iloc[i] > upper_band.iloc[i]:
                direction.iloc[i] = -1  # Switch to uptrend
                supertrend.iloc[i] = lower_band.iloc[i]
            else:
                direction.iloc[i] = 1
                supertrend.iloc[i] = upper_band.iloc[i]

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if direction.iloc[i] == -1 and direction.iloc[i-1] == 1:
            signals.iloc[i] = 1  # Switch to uptrend
        elif direction.iloc[i] == 1 and direction.iloc[i-1] == -1:
            signals.iloc[i] = -1  # Switch to downtrend
    return signals


# --- Strategy 7: Ichimoku Cloud ---
def strategy_ichimoku(df):
    tenkan_len, kijun_len, senkou_b_len, displacement = 9, 26, 52, 26

    tenkan = (df['high'].rolling(tenkan_len).max() + df['low'].rolling(tenkan_len).min()) / 2
    kijun = (df['high'].rolling(kijun_len).max() + df['low'].rolling(kijun_len).min()) / 2
    senkou_a = (tenkan + kijun) / 2
    senkou_b = (df['high'].rolling(senkou_b_len).max() + df['low'].rolling(senkou_b_len).min()) / 2

    # Use displaced cloud for current signals
    cloud_top = pd.concat([senkou_a.shift(displacement), senkou_b.shift(displacement)], axis=1).max(axis=1)
    cloud_bottom = pd.concat([senkou_a.shift(displacement), senkou_b.shift(displacement)], axis=1).min(axis=1)

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(cloud_top.iloc[i]) or pd.isna(tenkan.iloc[i]):
            continue
        # Long: Tenkan crosses above Kijun, price above cloud
        if (tenkan.iloc[i] > kijun.iloc[i] and tenkan.iloc[i-1] <= kijun.iloc[i-1]
                and df['close'].iloc[i] > cloud_top.iloc[i]):
            signals.iloc[i] = 1
        # Short: Tenkan crosses below Kijun, price below cloud
        elif (tenkan.iloc[i] < kijun.iloc[i] and tenkan.iloc[i-1] >= kijun.iloc[i-1]
              and df['close'].iloc[i] < cloud_bottom.iloc[i]):
            signals.iloc[i] = -1
    return signals


# --- Strategy 8: ADX Trend ---
def strategy_adx_trend(df):
    period = 14
    adx_threshold = 25

    high, low, close = df['high'], df['low'], df['close']

    # True Range
    tr = np.maximum(high - low,
                    np.maximum(abs(high - close.shift(1)),
                               abs(low - close.shift(1))))

    # Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0),
                        index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0),
                         index=df.index)

    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr.replace(0, np.nan))

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.rolling(window=period).mean()

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(adx.iloc[i]) or pd.isna(plus_di.iloc[i]):
            continue
        strong = adx.iloc[i] > adx_threshold

        if (plus_di.iloc[i] > minus_di.iloc[i] and plus_di.iloc[i-1] <= minus_di.iloc[i-1]
                and strong):
            signals.iloc[i] = 1
        elif (minus_di.iloc[i] > plus_di.iloc[i] and minus_di.iloc[i-1] <= plus_di.iloc[i-1]
              and strong):
            signals.iloc[i] = -1
    return signals


# --- Strategy 9: VWAP Mean Reversion ---
def strategy_vwap_mean_reversion(df):
    typical = (df['high'] + df['low'] + df['close']) / 3
    vwma_val = (typical * df['volume']).rolling(20).sum() / df['volume'].rolling(20).sum()
    vwma_dev = typical.rolling(20).std()
    upper = vwma_val + 2.0 * vwma_dev
    lower = vwma_val - 2.0 * vwma_dev
    rsi = compute_rsi(df['close'], 14)

    signals = pd.Series(0, index=df.index)
    in_position = 0

    for i in range(1, len(df)):
        if pd.isna(vwma_val.iloc[i]) or pd.isna(rsi.iloc[i]):
            continue

        # Exit at mean
        if in_position == 1 and df['close'].iloc[i] >= vwma_val.iloc[i]:
            signals.iloc[i] = -1
            in_position = 0
            continue
        elif in_position == -1 and df['close'].iloc[i] <= vwma_val.iloc[i]:
            signals.iloc[i] = 1
            in_position = 0
            continue

        # Long: price at lower band + RSI oversold
        if df['close'].iloc[i] <= lower.iloc[i] and rsi.iloc[i] < 30 and in_position == 0:
            signals.iloc[i] = 1
            in_position = 1
        # Short: price at upper band + RSI overbought
        elif df['close'].iloc[i] >= upper.iloc[i] and rsi.iloc[i] > 70 and in_position == 0:
            signals.iloc[i] = -1
            in_position = -1
    return signals


# --- Strategy 10: Williams Alligator ---
def strategy_williams_alligator(df):
    # SMMA approximation: SMA of SMA
    jaw = compute_sma(compute_sma(df['close'], 13), 2)
    teeth = compute_sma(compute_sma(df['close'], 8), 2)
    lips = compute_sma(compute_sma(df['close'], 5), 2)

    # Displacements
    jaw_d = jaw.shift(8)
    teeth_d = teeth.shift(5)
    lips_d = lips.shift(3)

    atr14 = compute_atr(df, 14)

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(jaw_d.iloc[i]) or pd.isna(atr14.iloc[i]):
            continue

        bull_align = lips_d.iloc[i] > teeth_d.iloc[i] > jaw_d.iloc[i]
        bear_align = lips_d.iloc[i] < teeth_d.iloc[i] < jaw_d.iloc[i]

        prev_bull = (lips_d.iloc[i-1] > teeth_d.iloc[i-1] > jaw_d.iloc[i-1]) if not pd.isna(jaw_d.iloc[i-1]) else False
        prev_bear = (lips_d.iloc[i-1] < teeth_d.iloc[i-1] < jaw_d.iloc[i-1]) if not pd.isna(jaw_d.iloc[i-1]) else False

        above_all = (df['close'].iloc[i] > lips_d.iloc[i] and
                     df['close'].iloc[i] > teeth_d.iloc[i] and
                     df['close'].iloc[i] > jaw_d.iloc[i])
        below_all = (df['close'].iloc[i] < lips_d.iloc[i] and
                     df['close'].iloc[i] < teeth_d.iloc[i] and
                     df['close'].iloc[i] < jaw_d.iloc[i])

        mouth_open = abs(lips_d.iloc[i] - jaw_d.iloc[i]) > abs(lips_d.iloc[max(0,i-5)] - jaw_d.iloc[max(0,i-5)]) if not pd.isna(jaw_d.iloc[max(0,i-5)]) else False

        if bull_align and not prev_bull and above_all and mouth_open:
            signals.iloc[i] = 1
        elif bear_align and not prev_bear and below_all and mouth_open:
            signals.iloc[i] = -1

        # Close on sleeping alligator
        sleeping = abs(lips_d.iloc[i] - teeth_d.iloc[i]) < atr14.iloc[i] * 0.3
        # (sleeping detection used in PineScript, less relevant in signal-based backtest)
    return signals


# =====================================================================
# STRATEGY REGISTRY
# =====================================================================

STRATEGIES = {
    "01_RSI_Momentum": strategy_rsi_momentum,
    "02_MACD_Histogram": strategy_macd_histogram,
    "03_Bollinger_Breakout": strategy_bollinger_breakout,
    "04_Triple_EMA": strategy_triple_ema,
    "05_Stochastic_RSI": strategy_stochastic_rsi,
    "06_Supertrend": strategy_supertrend,
    "07_Ichimoku_Cloud": strategy_ichimoku,
    "08_ADX_Trend": strategy_adx_trend,
    "09_VWAP_Mean_Reversion": strategy_vwap_mean_reversion,
    "10_Williams_Alligator": strategy_williams_alligator,
}


if __name__ == "__main__":
    print("Backtest engine loaded. Use run_tournament.py to execute.")
