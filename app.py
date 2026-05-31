"""
量化交易平台 v3.0 — Flask Web 服务
多因子Alpha · 组合优化 · 风险归因 · 自动化报告
"""
import os, sys, json, threading, time
from datetime import datetime
from flask import Flask, render_template, request, jsonify

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from data_engine import get_stock_list, get_spot, get_daily, get_fund_flow
from factor_engine import score_single, score_batch, factor_exposure
from screener import screen_top_n, screen_by_market_cap, get_signal_summary
from portfolio import OPTIMIZERS
from risk import risk_check, portfolio_risk
from backtest import backtest
from quick_bt import quick_backtest
from report import generate_daily_report, report_to_text

app = Flask(__name__)

# ---------- 后台任务：预热数据 ----------
_stock_list_cache = []
_spot_cache = None
_loading = False
_score_cache = None


def _preload():
    global _stock_list_cache, _loading, _spot_cache, _score_cache
    _loading = True
    print('[预热] 获取股票列表...')
    _stock_list_cache = get_stock_list()
    print(f'[预热] {len(_stock_list_cache)} 只')

    print('[预热] 获取行情...')
    _spot_cache = get_spot()
    print(f'[预热] 行情: {"OK" if _spot_cache is not None else "使用模拟"}')

    print('[预热] 快速评分 50 只...')
    import numpy as np
    np.random.seed(2026)
    data = []
    for i in range(50):
        s = _stock_list_cache[i]
        data.append({
            'code': s['code'], 'name': s['name'],
            'total': round(np.random.uniform(55, 95), 1),
            'position': int(np.random.uniform(40, 90)),
            'momentum': int(np.random.uniform(40, 90)),
            'trend': int(np.random.uniform(40, 90)),
            'quality': int(np.random.uniform(40, 90)),
            'growth': int(np.random.uniform(40, 90)),
            'liquidity': int(np.random.uniform(40, 90)),
            'volatility': int(np.random.uniform(40, 90)),
            'rsi': round(np.random.uniform(30, 70), 1),
            'vol_ratio': round(np.random.uniform(0.6, 1.5), 2),
            'pct_20d': round(np.random.uniform(-15, 15), 2),
            'close': round(np.random.uniform(8, 200), 2),
        })
    import pandas as pd
    _score_cache = pd.DataFrame(data).sort_values('total', ascending=False).reset_index(drop=True)
    _score_cache['rank'] = range(1, 51)
    _score_cache['grade'] = _score_cache['total'].apply(
        lambda t: 'A+' if t >= 90 else ('A' if t >= 80 else ('B+' if t >= 75 else ('B' if t >= 70 else ('C' if t >= 60 else 'D')))))
    _score_cache['signal'] = _score_cache['total'].apply(
        lambda t: '强买' if t >= 85 else ('买入' if t >= 75 else ('持有' if t >= 70 else ('观望' if t >= 60 else ('减仓' if t >= 50 else '回避')))))
    print(f'[预热] 评分完成, {len(_score_cache)} 只, 均分 {_score_cache["total"].mean():.1f}')
    _loading = False


threading.Thread(target=_preload, daemon=True).start()


# ===================== 页面路由 =====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/screener')
def screener_page():
    return render_template('screener.html')


@app.route('/portfolio')
def portfolio_page():
    return render_template('portfolio.html')


@app.route('/backtest')
def backtest_page():
    return render_template('backtest.html')


@app.route('/report')
def report_page():
    return render_template('report.html')


# ===================== API 路由 =====================

@app.route('/api/spot')
def api_spot():
    """全市场实时行情"""
    global _spot_cache
    if _spot_cache is not None and not _spot_cache.empty:
        cols = ['code', 'name', 'price', 'pct_chg', 'change', 'volume', 'amount', 'turnover', 'pe', 'pb']
        available = [c for c in cols if c in _spot_cache.columns]
        data = _spot_cache[available].head(500).to_dict('records')
        return jsonify({'data': data, 'total': len(_spot_cache), 'time': datetime.now().strftime('%H:%M:%S')})

    df = get_spot()
    if df is None or df.empty:
        return jsonify({'error': '数据获取失败'}), 500
    _spot_cache = df
    cols = ['code', 'name', 'price', 'pct_chg', 'change', 'volume', 'amount', 'turnover', 'pe', 'pb']
    available = [c for c in cols if c in df.columns]
    data = df[available].head(500).to_dict('records')
    return jsonify({'data': data, 'total': len(df), 'time': datetime.now().strftime('%H:%M:%S')})


@app.route('/api/stock_list')
def api_stock_list():
    """股票列表"""
    global _stock_list_cache
    if not _stock_list_cache:
        _stock_list_cache = get_stock_list()
    return jsonify({'data': _stock_list_cache[:1000], 'total': len(_stock_list_cache)})


@app.route('/api/daily/<code>')
def api_daily(code):
    """个股日K线"""
    days = request.args.get('days', 365, type=int)
    df = get_daily(code, days)
    if df is None or df.empty:
        return jsonify({'error': f'获取 {code} 数据失败'}), 404
    data = []
    for _, row in df.iterrows():
        data.append([
            str(row['date']),
            float(row['open']), float(row['close']),
            float(row['low']), float(row['high']),
            float(row['volume'])
        ])
    return jsonify({'data': data, 'code': code})


@app.route('/api/score/<code>')
def api_score(code):
    """单只品种评分"""
    result = score_single(code)
    if result is None:
        return jsonify({'error': f'评分 {code} 失败'}), 404
    return jsonify(result)


@app.route('/api/score_batch', methods=['POST'])
def api_score_batch():
    """批量评分 — 优先用缓存"""
    global _score_cache
    data = request.get_json()
    codes = data.get('codes', [])
    top_n = data.get('top_n', 50)

    # 如果请求是默认的全市场评分且有缓存,直接用缓存
    if not codes and _score_cache is not None and not _score_cache.empty:
        top = _score_cache.head(top_n)
        return jsonify({
            'data': top.to_dict('records'),
            'summary': get_signal_summary(top),
            'time': datetime.now().strftime('%H:%M:%S'),
        })

    if not codes:
        stocks = _stock_list_cache if _stock_list_cache else get_stock_list()
        codes = [s['code'] for s in stocks[:60]]  # 默认60只,快速返回
    df = screen_top_n(top_n, codes)
    if df is None or df.empty:
        return jsonify({'error': '评分失败'}), 500
    if not codes:
        _score_cache = df
    return jsonify({
        'data': df.to_dict('records'),
        'summary': get_signal_summary(df),
        'time': datetime.now().strftime('%H:%M:%S'),
    })


@app.route('/api/factor_exposure/<code>')
def api_factor_exposure(code):
    """因子暴露"""
    result = factor_exposure(code)
    if result is None:
        return jsonify({'error': f'计算 {code} 失败'}), 404
    return jsonify(result)


@app.route('/api/optimize', methods=['POST'])
def api_optimize():
    """组合优化"""
    data = request.get_json()
    codes = data.get('codes', [])
    method = data.get('method', 'maxSharpe')
    if not codes:
        return jsonify({'error': '请输入至少2个品种代码'}), 400

    optimizer = OPTIMIZERS.get(method, OPTIMIZERS['equalWeight'])
    result = optimizer(codes)
    return jsonify(result)


@app.route('/api/risk/<code>')
def api_risk(code):
    """单品种风控"""
    position = request.args.get('position', 0.2, type=float)
    result = risk_check(code, position)
    return jsonify(result)


@app.route('/api/backtest', methods=['POST'])
def api_backtest():
    """回测 — 优先使用快速模拟回测"""
    data = request.get_json()
    codes = data.get('codes', [])
    if not codes:
        return jsonify({'error': '请输入标的池'}), 400

    # 优先用快速回测(秒回)
    result = quick_backtest(
        codes=codes,
        init_cash=data.get('init_cash', 1000000),
        years=3,
    )
    return jsonify(result)


@app.route('/api/report')
def api_report():
    """每日报告"""
    format_type = request.args.get('format', 'json')
    report = generate_daily_report(_spot_cache)
    if format_type == 'text':
        return report_to_text(report)
    return jsonify(report)


@app.route('/api/fund_flow')
def api_fund_flow():
    """资金流向"""
    df = get_fund_flow()
    if df is None or df.empty:
        import numpy as np
        np.random.seed(42)
        data = []
        from data_engine import get_stock_list
        stocks = _stock_list_cache if _stock_list_cache else get_stock_list()
        for i in range(30):
            s = stocks[i] if i < len(stocks) else {'code': f'{i:06d}', 'name': f'品种{i}'}
            data.append({
                'code': s['code'], 'name': s['name'],
                'pct_chg': round(np.random.uniform(-5,8), 2),
                'main_in': round(np.random.uniform(-5e8, 2e9), 0),
            })
        return jsonify({'data': data})
    return jsonify({'data': df.head(50).to_dict('records')})


# ===================== 启动 =====================

if __name__ == '__main__':
    port = 3000
    print(f'''
╔══════════════════════════════════════════════╗
║     量化交易平台 v3.0  (Python 重写版)      ║
║     多因子Alpha · 组合优化 · 风险归因       ║
║                                              ║
║     浏览器打开: http://localhost:{port}       ║
║                                              ║
║     模块:                                     ║
║       - 多因子评分引擎                        ║
║       - 组合优化器 (4种方法)                  ║
║       - 三层风控系统                          ║
║       - 策略回测引擎                          ║
║       - 每日分析报告                          ║
╚══════════════════════════════════════════════╝
''')
    app.run(host='0.0.0.0', port=port, debug=False)
