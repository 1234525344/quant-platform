"""
回测引擎 — 多因子Alpha策略回测
"""
import numpy as np
import pandas as pd
from data_engine import get_batch_daily, get_daily
from factor_engine import score_batch
from risk import calc_max_drawdown


def backtest(codes, start_date='2023-01-01', end_date='2025-12-31',
             rebalance_freq='monthly', top_n=20, init_cash=1000000):
    """
    多因子Alpha选股回测
    - codes: 标的池
    - rebalance_freq: 调仓频率 ('monthly' / 'weekly')
    - top_n: 每次调仓持有评分最高的N只
    """
    # 获取所有K线数据
    print(f'[backtest] 获取 {len(codes)} 只品种数据...')
    data = get_batch_daily(codes, days=1500)
    if not data:
        return _empty_bt_result()

    # 构建价格矩阵
    closes = {}
    for code, df in data.items():
        if df is not None and not df.empty:
            df = df.set_index('date')
            closes[code] = df['close'].astype(float)

    prices = pd.DataFrame(closes).sort_index()
    prices = prices.loc[start_date:end_date]
    if prices.empty or len(prices.columns) < 5:
        return _empty_bt_result()

    # 确定调仓日期
    if rebalance_freq == 'monthly':
        rebal_dates = prices.resample('M').last().index
    else:
        rebal_dates = prices.resample('W').last().index

    # 回测主循环
    holdings = []  # 当前持仓
    cash = init_cash
    portfolio_value = init_cash
    values = []
    trades = 0

    for i, date in enumerate(rebal_dates):
        if date not in prices.index:
            continue

        current_prices = prices.loc[date]

        # 卖出不在新名单中的持仓
        for h in holdings:
            code = h['code']
            if code in current_prices.index and not pd.isna(current_prices[code]):
                cash += h['shares'] * float(current_prices[code])
        trades += len(holdings)

        # 重新评分选股（简化：用动量 + 趋势信号模拟，避免每次调仓重新从API获取数据）
        # 实际回测用当日已知数据
        lookback = prices.loc[:date].iloc[-120:]
        if len(lookback) < 40:
            continue

        returns = lookback.pct_change().dropna()
        scores = {}
        for col in prices.columns:
            if col in returns.columns:
                ret_series = returns[col].dropna()
                if len(ret_series) < 20:
                    continue
                mom = ret_series.iloc[-20:].mean() * 252
                vol = ret_series.iloc[-20:].std() * np.sqrt(252)
                sharpe = mom / vol if vol > 0 else 0
                scores[col] = mom * 0.4 + sharpe * 100 * 0.3 + (1 - vol) * 0.3

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected = ranked[:top_n]
        n = len(selected)
        if n == 0:
            continue

        # 等权买入
        weight_per = cash / n
        holdings = []
        for code, score in selected:
            if code in current_prices.index and not pd.isna(current_prices[code]):
                price = float(current_prices[code])
                shares = int(weight_per / price / 100) * 100  # 整手
                if shares >= 100:
                    cost = shares * price
                    cash -= cost
                    holdings.append({'code': code, 'shares': shares, 'price': price})
                    trades += 1

        # 记录组合价值
        equity = cash
        for h in holdings:
            code = h['code']
            if code in current_prices.index and not pd.isna(current_prices[code]):
                equity += h['shares'] * float(current_prices[code])

        values.append({'date': str(date), 'value': round(equity, 2)})

    if not values:
        return _empty_bt_result()

    df_vals = pd.DataFrame(values)
    df_vals['value'] = df_vals['value'].astype(float)
    final_value = df_vals['value'].iloc[-1]
    total_return = (final_value / init_cash - 1) * 100
    max_dd = calc_max_drawdown(df_vals['value'])

    # 计算每日收益率
    df_vals['daily_ret'] = df_vals['value'].pct_change()
    sharpe = (df_vals['daily_ret'].mean() / df_vals['daily_ret'].std() * np.sqrt(252)
              if df_vals['daily_ret'].std() > 0 else 0)

    return {
        'init_cash': init_cash,
        'final_value': round(final_value, 2),
        'total_return': round(total_return, 2),
        'max_drawdown': round(float(max_dd * 100), 2),
        'sharpe': round(float(sharpe), 2),
        'trades': trades,
        'n_rebalances': len(rebal_dates),
        'value_curve': values,
        'annual_return': round(total_return / max((len(rebal_dates) / 12), 1), 2),
    }


def _empty_bt_result():
    return {
        'init_cash': 1000000,
        'final_value': 1000000,
        'total_return': 0,
        'max_drawdown': 0,
        'sharpe': 0,
        'trades': 0,
        'n_rebalances': 0,
        'value_curve': [],
        'annual_return': 0,
    }


print('[backtest] 回测引擎已加载')
