"""
因子引擎 — 9维度多因子评分模型
位置因子(25%) · 动能因子(20%) · 趋势因子(20%) · 质量因子(15%)
成长因子(10%) · 流动性(5%) · 波动率(5%) · 动量(额外) · 反转(额外)
"""
import pandas as pd
import numpy as np
from data_engine import get_daily, get_batch_daily


# ===================== 因子计算函数 =====================

def calc_rsi(close, n=14):
    """RSI 相对强弱指标"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(n).mean()
    avg_loss = loss.rolling(n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(close):
    """MACD: DIF, DEA, MACD柱"""
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9).mean()
    macd = (dif - dea) * 2
    return dif, dea, macd


def calc_boll(close, n=20):
    """布林带"""
    ma = close.rolling(n).mean()
    std = close.rolling(n).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    return upper, ma, lower


def calc_atr(high, low, close, n=14):
    """ATR 平均真实波幅"""
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def calc_kdj(high, low, close, n=9):
    """KDJ 随机指标"""
    lowest = low.rolling(n).min()
    highest = high.rolling(n).max()
    rsv = (close - lowest) / (highest - lowest).replace(0, np.nan) * 100
    k = rsv.ewm(com=2).mean()
    d = k.ewm(com=2).mean()
    j = 3 * k - 2 * d
    return k, d, j


# ===================== 单只股票因子评分 =====================

def score_single(code, days=252):
    """
    对单只股票计算9因子评分，返回 dict
    每项因子 0-100 分，加权得出综合分
    """
    df = get_daily(code, max(days+60, 300))
    if df is None or df.empty or len(df) < 60:
        return None

    close = df['close'].astype(float)
    high  = df['high'].astype(float)
    low   = df['low'].astype(float)
    volume = df['volume'].astype(float)
    turnover = df.get('turnover', pd.Series([np.nan]*len(df))).astype(float)
    amount = df.get('amount', pd.Series([np.nan]*len(df))).astype(float)
    latest_close = close.iloc[-1]

    scores = {}

    # ---- 1. 位置因子 (25%)：估值水位 ----
    ma60 = close.rolling(60).mean().iloc[-1]
    ma120 = close.rolling(120).mean().iloc[-1] if len(close) >= 120 else ma60
    pct_60d = (latest_close / close.iloc[-60] - 1) * 100 if len(close) >= 60 else 0
    pct_20d = (latest_close / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
    dist_ma60 = (latest_close - ma60) / ma60 * 100

    position_score = 50
    if dist_ma60 < -20: position_score += 25
    elif dist_ma60 < -10: position_score += 15
    elif dist_ma60 < 0: position_score += 5
    elif dist_ma60 > 30: position_score -= 20
    elif dist_ma60 > 15: position_score -= 10
    if pct_60d < -30 and pct_20d > 0: position_score += 10
    scores['position'] = max(0, min(100, position_score))

    # ---- 2. 动能因子 (20%)：量与价的动量 ----
    vol_ratio = volume.iloc[-5:].mean() / volume.iloc[-20:].mean() if volume.iloc[-20:].mean() > 0 else 1
    rsi14 = calc_rsi(close, 14).iloc[-1]
    dif, dea, macd = calc_macd(close)

    momentum_score = 50
    if vol_ratio > 1.5: momentum_score += 15
    elif vol_ratio > 1.2: momentum_score += 10
    elif vol_ratio < 0.6: momentum_score -= 15
    if not np.isnan(rsi14):
        if 40 < rsi14 < 70: momentum_score += 15
        elif rsi14 >= 80: momentum_score -= 10
        elif rsi14 < 30: momentum_score += 10
    if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
        momentum_score += 10  # 金叉
    scores['momentum'] = max(0, min(100, momentum_score))

    # ---- 3. 趋势因子 (20%)：方向与强度 ----
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60_2 = close.rolling(60).mean().iloc[-1]

    trend_score = 50
    if latest_close > ma20 > ma60_2: trend_score += 20
    elif latest_close > ma20: trend_score += 10
    elif latest_close < ma20 < ma60_2: trend_score -= 20
    elif latest_close < ma20: trend_score -= 10
    slope_20 = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] if len(close) >= 20 else 0
    if slope_20 > 0.1: trend_score += 15
    elif slope_20 > 0.03: trend_score += 5
    elif slope_20 < -0.1: trend_score -= 15
    scores['trend'] = max(0, min(100, trend_score))

    # ---- 4. 质量因子 (15%) ----
    quality_score = 50
    if turnover.iloc[-1] > 0:
        if turnover.iloc[-1] < 3: quality_score += 10
        elif turnover.iloc[-1] > 15: quality_score -= 10
    recent_volatility = close.pct_change().iloc[-20:].std() * 100
    if recent_volatility < 2: quality_score += 15
    elif recent_volatility > 5: quality_score -= 10
    scores['quality'] = max(0, min(100, quality_score))

    # ---- 5. 成长因子 (10%) ----
    growth_score = 50
    if amount.iloc[-1] > 0:
        amt_ratio = amount.iloc[-5:].mean() / amount.iloc[-20:].mean() if amount.iloc[-20:].mean() > 0 else 1
        if amt_ratio > 1.3: growth_score += 15
        elif amt_ratio > 1.1: growth_score += 8
    if pct_60d > 0: growth_score += min(pct_60d * 0.3, 15)
    scores['growth'] = max(0, min(100, growth_score))

    # ---- 6. 流动性因子 (5%) ----
    liq_score = 50
    if turnover.iloc[-1] > 0:
        if 2 < turnover.iloc[-1] < 10: liq_score += 15
        elif turnover.iloc[-1] < 1: liq_score -= 15
    scores['liquidity'] = max(0, min(100, liq_score))

    # ---- 7. 波动率因子 (5%) ----
    vol_score = 50
    if recent_volatility < 1.5: vol_score += 15
    elif recent_volatility > 4: vol_score -= 10
    scores['volatility'] = max(0, min(100, vol_score))

    # ---- 8. 反转因子 (额外) ----
    rev_score = 50
    pct_5d = (latest_close / close.iloc[-5] - 1) * 100 if len(close) >= 5 else 0
    if pct_5d < -8: rev_score += 20
    elif pct_5d > 15: rev_score -= 15
    scores['reversal'] = max(0, min(100, rev_score))

    # ---- 综合评分 ----
    weights = {
        'position': 0.25, 'momentum': 0.20, 'trend': 0.20,
        'quality': 0.15, 'growth': 0.10, 'liquidity': 0.05,
        'volatility': 0.05,
    }
    total = sum(scores.get(k, 50) * w for k, w in weights.items())
    scores['total'] = round(total, 1)
    scores['close'] = float(latest_close)
    scores['pct_20d'] = round(float(pct_20d), 2) if pct_20d else 0
    scores['vol_ratio'] = round(float(vol_ratio), 2) if not np.isnan(vol_ratio) else 1.0
    scores['rsi'] = round(float(rsi14), 1) if not np.isnan(rsi14) else 50
    scores['code'] = code

    return scores


# ===================== 批量评分 =====================

def score_batch(codes):
    """批量评分，返回 DataFrame，按总分降序排列"""
    results = []
    for i, code in enumerate(codes):
        s = score_single(code)
        if s:
            results.append(s)
        if (i + 1) % 20 == 0:
            print(f'  [评分进度] {i+1}/{len(codes)}')
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values('total', ascending=False).reset_index(drop=True)
        df['rank'] = range(1, len(df) + 1)
        df['grade'] = df['total'].apply(_grade)
        df['signal'] = df['total'].apply(_signal)
    return df


def _grade(total):
    if total >= 85: return 'A+'
    if total >= 80: return 'A'
    if total >= 75: return 'B+'
    if total >= 70: return 'B'
    if total >= 60: return 'C'
    return 'D'


def _signal(total):
    if total >= 85: return '强买'
    if total >= 75: return '买入'
    if total >= 70: return '持有'
    if total >= 60: return '观望'
    if total >= 50: return '减仓'
    return '回避'


# ===================== 风格因子暴露 =====================

def factor_exposure(code):
    """计算单只股票的风格因子暴露"""
    s = score_single(code, 252)
    if s is None: return None
    return {
        'code': code,
        'momentum_exp': round((s.get('momentum', 50) - 50) / 50, 2),
        'value_exp': round((s.get('position', 50) - 50) / 50, 2),
        'quality_exp': round((s.get('quality', 50) - 50) / 50, 2),
        'lowvol_exp': round((50 - s.get('volatility', 50)) / 50, 2),
        'size_exp': 0.0,
        'growth_exp': round((s.get('growth', 50) - 50) / 50, 2),
        'liquidity_exp': round((s.get('liquidity', 50) - 50) / 50, 2),
        'reversal_exp': round((s.get('reversal', 50) - 50) / 50, 2),
    }


print('[factor_engine] 9因子评分模型已加载')
print('  权重: 位置25% 动能20% 趋势20% 质量15% 成长10% 流动5% 波动5%')
