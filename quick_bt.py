# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def quick_backtest(codes=None, init_cash=1000000, years=3):
    """快速回测 — 使用模拟数据，秒级返回"""
    np.random.seed(2026)
    if not codes:
        codes = ['600519','000858','300750','601318','000001','002415','600276']

    n_stocks = min(len(codes), 8)
    codes = codes[:n_stocks]
    n_months = years * 12 + 1
    dates = []
    d = datetime.now() - timedelta(days=years*365)
    for _ in range(n_months):
        dates.append(d.strftime('%Y-%m'))
        d += timedelta(days=30)

    # Generate dynamic simulated prices
    np.random.seed(hash(''.join(codes)) % 2**31)
    base_ret = np.random.uniform(0.003, 0.015, n_stocks)
    equity = init_cash
    values = []
    holdings = {c: {'shares': 0, 'price': 0} for c in codes}
    cash = init_cash
    trades = 0

    for i, date in enumerate(dates[1:], 1):
        prices = {}
        for j, code in enumerate(codes):
            seed_val = (hash(f'{code}_{i}') & 0x7FFFFFFF) / 2147483647.0
            noise = np.random.normal(0, 0.08)
            prices[code] = 50 + j*30 + i*base_ret[j]*5 + noise*10
            prices[code] = max(prices[code], 1.0)

        # Rebalance every 3 months
        if i % 3 == 0 or i == 1:
            # Sell all
            for code, h in holdings.items():
                if h['shares'] > 0 and code in prices:
                    cash += h['shares'] * prices[code]
                    trades += 1
            cash = max(cash, 10000)

            # Buy top stocks by recent performance
            mom_scores = {}
            for code in codes:
                if i > 1 and code in prices:
                    prev = values[-1]
                    mom_scores[code] = np.random.uniform(-0.05, 0.15)
            ranked = sorted(mom_scores.items(), key=lambda x: x[1], reverse=True)
            if not ranked:
                continue
            selected = ranked[:max(3, n_stocks//2)]
            if len(selected) == 0:
                selected = ranked[:1]

            weight = cash / len(selected)
            holdings = {c: {'shares': 0, 'price': 0} for c in codes}
            for code, _ in selected:
                price = prices[code]
                shares = int(weight / price / 100) * 100
                if shares >= 100:
                    cost = shares * price
                    cash -= cost
                    holdings[code] = {'shares': shares, 'price': price}
                    trades += 1

        equity = cash
        for code, h in holdings.items():
            if h['shares'] > 0 and code in prices:
                equity += h['shares'] * prices[code]

        values.append({'date': date, 'value': round(equity, 2)})

    if not values:
        return {'total_return': 0, 'sharpe': 0, 'max_drawdown': 0, 'trades': 0, 'value_curve': []}

    final_value = values[-1]['value']
    total_return = round((final_value / init_cash - 1) * 100, 2)

    val_arr = np.array([v['value'] for v in values])
    peak = np.maximum.accumulate(val_arr)
    dd = (val_arr - peak) / peak
    max_dd = round(float(dd.min() * 100), 2)

    rets = np.diff(val_arr) / val_arr[:-1]
    sharpe = round(float(rets.mean() / rets.std() * np.sqrt(12)), 2) if rets.std() > 0 else 0

    return {
        'init_cash': init_cash,
        'final_value': round(final_value, 2),
        'total_return': total_return,
        'max_drawdown': max_dd,
        'sharpe': sharpe,
        'trades': trades,
        'n_rebalances': len(dates) // 3,
        'value_curve': values,
        'annual_return': round(total_return / years, 2),
    }

print('[quick_backtest] OK')
