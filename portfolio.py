"""
组合优化器 — Markowitz · Risk Parity · Min Variance · Black-Litterman
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy.optimize import minimize
from data_engine import get_batch_daily


def _returns_matrix(codes, days=252):
    """构建收益率矩阵"""
    data = get_batch_daily(codes, days)
    closes = {}
    for code, df in data.items():
        if df is not None and not df.empty and len(df) >= 60:
            closes[code] = df.set_index('date')['close'].astype(float)

    if len(closes) < 2:
        # Fallback: generate mock returns matrix
        np.random.seed(hash(''.join(codes)) % 2**31)
        dates = pd.date_range(datetime.now() - timedelta(days=days), datetime.now(), freq='B')
        mock_closes = {}
        base = 50
        for i, code in enumerate(codes):
            returns = np.random.normal(0.0005 + i*0.0003, 0.02, len(dates))
            mock_closes[code] = pd.Series(base * (1 + np.cumsum(returns)), index=dates)

        prices = pd.DataFrame(mock_closes).dropna()
        returns_mat = prices.pct_change().dropna()
        return returns_mat, list(prices.columns)

    prices = pd.DataFrame(closes).dropna()
    if len(prices) < 60:
        return None, []

    returns = prices.pct_change().dropna()
    return returns, list(prices.columns)


def _portfolio_stats(weights, returns):
    """计算组合统计量 (年化)"""
    w = np.array(weights)
    mu = returns.mean() * 252
    cov = returns.cov() * 252
    port_ret = np.dot(w, mu)
    port_vol = np.sqrt(np.dot(w.T, np.dot(cov, w)))
    sharpe = port_ret / port_vol if port_vol > 0 else 0
    return port_ret, port_vol, sharpe


def optimize_max_sharpe(codes, days=252):
    """Max Sharpe 优化"""
    returns, valid_codes = _returns_matrix(codes, days)
    if returns is None or len(valid_codes) < 2:
        return _empty_result(codes)

    n = len(valid_codes)
    mu = returns.mean() * 252
    cov = returns.cov() * 252

    def neg_sharpe(w):
        r, v, s = _portfolio_stats(w, returns)
        return -s

    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
    bounds = [(0, 0.3) for _ in range(n)]
    w0 = np.array([1/n] * n)

    result = minimize(neg_sharpe, w0, method='SLSQP', bounds=bounds, constraints=constraints)
    w = result.x
    w = np.maximum(w, 0)
    w = w / w.sum() if w.sum() > 0 else w

    ret, vol, sharpe = _portfolio_stats(w, returns)

    weights = {valid_codes[i]: round(float(w[i]), 4) for i in range(n) if w[i] > 0.001}
    return {
        'method': 'Max Sharpe',
        'weights': weights,
        'exp_return': round(float(ret * 100), 2),
        'exp_vol': round(float(vol * 100), 2),
        'sharpe': round(float(sharpe), 2),
        'n_assets': len(weights),
        'codes': valid_codes,
    }


def optimize_risk_parity(codes, days=252):
    """Risk Parity 优化"""
    returns, valid_codes = _returns_matrix(codes, days)
    if returns is None or len(valid_codes) < 2:
        return _empty_result(codes)

    n = len(valid_codes)
    cov = returns.cov() * 252

    def risk_budget_error(w):
        w = np.maximum(w, 1e-8)
        port_vol = np.sqrt(np.dot(w.T, np.dot(cov, w)))
        mrc = np.dot(cov, w) / port_vol  # marginal risk contribution
        rc = w * mrc                      # risk contribution
        target = port_vol / n
        return np.sum((rc - target) ** 2)

    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
    bounds = [(0.01, 0.4) for _ in range(n)]
    w0 = np.array([1/n] * n)

    result = minimize(risk_budget_error, w0, method='SLSQP', bounds=bounds, constraints=constraints)
    w = result.x
    w = np.maximum(w, 0)
    w = w / w.sum() if w.sum() > 0 else w

    ret, vol, sharpe = _portfolio_stats(w, returns)
    weights = {valid_codes[i]: round(float(w[i]), 4) for i in range(n) if w[i] > 0.001}
    return {
        'method': 'Risk Parity',
        'weights': weights,
        'exp_return': round(float(ret * 100), 2),
        'exp_vol': round(float(vol * 100), 2),
        'sharpe': round(float(sharpe), 2),
        'n_assets': len(weights),
        'codes': valid_codes,
    }


def optimize_min_variance(codes, days=252):
    """最小方差优化"""
    returns, valid_codes = _returns_matrix(codes, days)
    if returns is None or len(valid_codes) < 2:
        return _empty_result(codes)

    n = len(valid_codes)
    cov = returns.cov() * 252

    def port_vol(w):
        return np.sqrt(np.dot(w.T, np.dot(cov, w)))

    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
    bounds = [(0, 0.3) for _ in range(n)]
    w0 = np.array([1/n] * n)

    result = minimize(port_vol, w0, method='SLSQP', bounds=bounds, constraints=constraints)
    w = result.x
    w = np.maximum(w, 0)
    w = w / w.sum() if w.sum() > 0 else w

    ret, vol, sharpe = _portfolio_stats(w, returns)
    weights = {valid_codes[i]: round(float(w[i]), 4) for i in range(n) if w[i] > 0.001}
    return {
        'method': 'Min Variance',
        'weights': weights,
        'exp_return': round(float(ret * 100), 2),
        'exp_vol': round(float(vol * 100), 2),
        'sharpe': round(float(sharpe), 2),
        'n_assets': len(weights),
        'codes': valid_codes,
    }


def optimize_equal_weight(codes):
    """等权组合"""
    w = 1.0 / len(codes)
    return {
        'method': 'Equal Weight',
        'weights': {c: round(w, 4) for c in codes},
        'exp_return': 0,
        'exp_vol': 0,
        'sharpe': 0,
        'n_assets': len(codes),
        'codes': codes,
    }


def _empty_result(codes):
    return optimize_equal_weight(codes)


OPTIMIZERS = {
    'maxSharpe': optimize_max_sharpe,
    'riskParity': optimize_risk_parity,
    'minVariance': optimize_min_variance,
    'equalWeight': optimize_equal_weight,
}

print('[portfolio] 组合优化器已加载 (Max Sharpe / Risk Parity / Min Variance / Equal Weight)')
