"""
风控模块 — 三层风控：止损 · 止盈 · 仓位限制 · VaR · Beta
"""
import numpy as np
import pandas as pd
from data_engine import get_daily


def calc_var(returns, confidence=0.95):
    """历史模拟法 VaR"""
    if returns is None or len(returns) < 30:
        return 0
    return float(np.percentile(returns, (1 - confidence) * 100))


def calc_cvar(returns, confidence=0.95):
    """CVaR (Expected Shortfall)"""
    var = calc_var(returns, confidence)
    if var == 0:
        return 0
    return float(returns[returns <= var].mean())


def calc_beta(stock_returns, benchmark_returns):
    """计算 Beta"""
    common = pd.concat([stock_returns, benchmark_returns], axis=1).dropna()
    if len(common) < 30:
        return 0
    cov = common.cov().iloc[0, 1]
    var = benchmark_returns.var()
    return float(cov / var) if var > 0 else 0


def calc_max_drawdown(close):
    """最大回撤"""
    peak = close.expanding().max()
    dd = (close - peak) / peak
    return float(dd.min())


def risk_check(code, position_pct, stop_loss_pct=-0.08, take_profit_pct=0.20):
    """
    单品种风控检查
    position_pct: 当前仓位占比 (0-1)
    stop_loss_pct: 止损线 (负值)
    take_profit_pct: 止盈线 (正值)
    """
    df = get_daily(code, 252)
    if df is None or df.empty:
        return {'pass': False, 'reason': '无数据'}

    close = df['close'].astype(float)
    returns = close.pct_change().dropna()

    max_dd = calc_max_drawdown(close)
    vol_20d = returns.iloc[-20:].std() * np.sqrt(252) if len(returns) >= 20 else 0

    checks = []

    # 1. 仓位检查
    if position_pct > 0.3:
        checks.append({'check': '仓位超限', 'pass': False,
                        'detail': f'单品种仓位 {position_pct*100:.0f}% > 30%上限'})
    else:
        checks.append({'check': '仓位正常', 'pass': True,
                        'detail': f'仓位 {position_pct*100:.0f}% ≤ 30%'})

    # 2. 回撤检查
    if abs(max_dd) > 0.5:
        checks.append({'check': '回撤过高', 'pass': False,
                        'detail': f'最大回撤 {max_dd*100:.1f}% > 50%'})
    else:
        checks.append({'check': '回撤正常', 'pass': True,
                        'detail': f'最大回撤 {max_dd*100:.1f}% ≤ 50%'})

    # 3. 波动率检查
    if vol_20d > 0.5:
        checks.append({'check': '波动过高', 'pass': False,
                        'detail': f'年化波动 {vol_20d*100:.1f}% > 50%'})
    else:
        checks.append({'check': '波动正常', 'pass': True,
                        'detail': f'年化波动 {vol_20d*100:.1f}% ≤ 50%'})

    all_pass = all(c['pass'] for c in checks)
    return {
        'code': code,
        'all_pass': all_pass,
        'checks': checks,
        'max_dd': round(float(max_dd * 100), 1),
        'vol_annual': round(float(vol_20d * 100), 1),
        'stop_loss': f'{stop_loss_pct*100:.0f}%',
        'take_profit': f'{take_profit_pct*100:.0f}%',
    }


def portfolio_risk(positions):
    """
    组合层面风控
    positions: [{'code': str, 'weight': float, 'cost': float}, ...]
    """
    total_weight = sum(p['weight'] for p in positions)
    max_single = max(p['weight'] for p in positions) if positions else 0

    warnings = []
    if total_weight > 1.0:
        warnings.append(f'总仓位 {total_weight*100:.0f}% 超100%')
    if max_single > 0.3:
        warnings.append(f'最大单品种仓位 {max_single*100:.0f}% 超30%')

    return {
        'total_weight': round(total_weight, 3),
        'max_single': round(max_single, 3),
        'n_positions': len(positions),
        'warnings': warnings,
    }


print('[risk] 风控模块已加载 (止损/止盈/仓位/VaR/Beta)')
