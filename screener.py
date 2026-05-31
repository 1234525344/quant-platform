"""
筛选器 — 全品类多因子筛选排序
"""
import pandas as pd
import numpy as np
from data_engine import get_stock_list, get_spot
from factor_engine import score_batch


def screen_top_n(n=50, codes=None):
    """筛选评分最高的 N 只品种"""
    if codes is None:
        stocks = get_stock_list()
        codes = [s['code'] for s in stocks[:200]]  # 默认取前200只

    print(f'[screener] 开始评分 {len(codes)} 只品种...')
    df = score_batch(codes)
    if df is None or df.empty:
        return None

    # 合并名称
    spot = get_spot()
    if spot is not None and not spot.empty:
        name_map = dict(zip(spot['code'], spot.get('name', spot['code'])))
        df['name'] = df['code'].map(name_map).fillna('')
    else:
        stocks = get_stock_list()
        name_map = {s['code']: s['name'] for s in stocks}
        df['name'] = df['code'].map(name_map).fillna('')

    result = df.head(n)
    print(f'[screener] 完成, Top {n} 平均分: {result["total"].mean():.1f}')
    return result


def screen_by_sector(sector_codes, n=20):
    """对指定板块进行评分排名"""
    return screen_top_n(n, sector_codes)


def screen_by_market_cap(min_cap=50e8, max_cap=5000e8, n=50):
    """按市值范围筛选后评分"""
    spot = get_spot()
    if spot is None or spot.empty:
        return screen_top_n(n)

    if 'total_mv' not in spot.columns:
        return screen_top_n(n)

    spot = spot[(spot['total_mv'] >= min_cap) & (spot['total_mv'] <= max_cap)]
    codes = spot['code'].tolist()
    return screen_top_n(n, codes)


def get_signal_summary(df):
    """从评分结果生成信号摘要"""
    if df is None or df.empty:
        return {'total': 0, 'buy': 0, 'hold': 0, 'sell': 0}

    signals = df['signal'].value_counts().to_dict()
    return {
        'total': len(df),
        'strong_buy': signals.get('强买', 0),
        'buy': signals.get('买入', 0) + signals.get('强买', 0),
        'hold': signals.get('持有', 0) + signals.get('观望', 0),
        'sell': signals.get('减仓', 0) + signals.get('回避', 0),
        'avg_score': round(df['total'].mean(), 1),
        'top_3': df.head(3)[['code', 'name', 'total', 'signal']].to_dict('records') if len(df) >= 3 else [],
    }


print('[screener] 筛选器已加载')
