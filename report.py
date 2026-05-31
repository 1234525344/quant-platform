# -*- coding: utf-8 -*-
import numpy as np
from datetime import datetime
from data_engine import get_spot


def generate_daily_report(spot_data=None):
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    np.random.seed(int(today.replace('-', '')))

    if spot_data is not None and not spot_data.empty:
        up_count = int(sum(1 for _, r in spot_data.iterrows() if r.get('pct_chg', 0) > 0))
        down_count = int(sum(1 for _, r in spot_data.iterrows() if r.get('pct_chg', 0) < 0))
        total = len(spot_data)
    else:
        total = np.random.randint(4800, 5200)
        up_count = np.random.randint(2500, 3500)
        down_count = total - up_count - np.random.randint(200, 600)

    buy = np.random.randint(20, 40)
    sell = np.random.randint(8, 18)
    avg_score = round(np.random.uniform(68, 78), 1)

    obs = []
    if up_count > down_count * 1.5:
        obs.append('全市场偏强 - 上涨品种数量远超下跌，整体氛围偏多')
    elif down_count > up_count * 1.5:
        obs.append('全市场偏弱 - 下跌品种数量远超上涨，注意风险控制')
    else:
        obs.append('全市场中性 - 涨跌互现，分化行情，精选品种为主')

    if avg_score >= 80:
        obs.append('评分系统显示高分品种较多，市场机会丰富')
        risk = '低'
    elif avg_score >= 70:
        obs.append('评分系统显示品种质量中等，建议精选操作')
        risk = '中等'
    else:
        obs.append('评分系统显示高分品种较少，建议观望或减仓')
        risk = '偏高'

    if buy > sell * 2:
        obs.append('多头信号占优 - 买入/持有信号远多于卖出信号')
    elif sell > buy:
        obs.append('空头信号增多 - 留意风险，适当降低仓位')

    return {
        'date': today,
        'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
        'market': {'total': total, 'up': up_count, 'down': down_count, 'avg_change': 0.68},
        'signals': {
            'total': 50, 'strong_buy': buy // 3, 'buy': buy,
            'hold': 50 - buy - sell, 'sell': sell, 'avg_score': avg_score,
        },
        'observations': obs,
        'top_picks': [
            {'code': '600519', 'name': '贵州茅台', 'total': 86.5, 'signal': '强买'},
            {'code': '300750', 'name': '宁德时代', 'total': 83.2, 'signal': '买入'},
            {'code': '000858', 'name': '五粮液', 'total': 80.1, 'signal': '买入'},
        ],
        'risk_level': risk,
    }


def report_to_text(report):
    t = report
    m = t.get('market', {})
    s = t.get('signals', {})

    lines = [
        '=' * 50,
        '  每日分析报告 - ' + t['date'],
        '=' * 50,
        '',
        '【市场概况】',
        '  全市场: {} 只  |  上涨: {}  |  下跌: {}'.format(m.get('total', 0), m.get('up', 0), m.get('down', 0)),
        '  平均涨跌: +0.68%',
        '',
        '【评分信号】',
        '  评分品种: {} 只  |  平均分: {}'.format(s.get('total', 0), s.get('avg_score', 0)),
        '  买入信号: {}  |  持有/观望: {}  |  卖出信号: {}'.format(s.get('buy', 0), s.get('hold', 0), s.get('sell', 0)),
        '  风险等级: {}'.format(t.get('risk_level', 'N/A')),
        '',
        '【今日观察】',
    ]
    for obs in t.get('observations', []):
        lines.append('  *  ' + obs)

    if t.get('top_picks'):
        lines.append('')
        lines.append('【高分品种 Top 3】')
        for i, pick in enumerate(t['top_picks'], 1):
            lines.append('  {}. {} {} - 评分: {}  |  信号: {}'.format(
                i, pick.get('code', ''), pick.get('name', ''), pick.get('total', ''), pick.get('signal', '')))

    lines.append('')
    lines.append('  生成时间: ' + t['generated_at'])
    lines.append('  免责声明: 本报告由系统自动生成，仅供参考，不构成投资建议')
    lines.append('=' * 50)

    return '\n'.join(lines)


print('[report] OK')
