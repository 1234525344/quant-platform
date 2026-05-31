# Quant Platform

Python 量化交易平台 — 多因子评分 · 组合优化 · 策略回测 · 自动日报

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Platform](https://img.shields.io/badge/platform-Win%20%7C%20Linux-lightgrey)

![banner](https://raw.githubusercontent.com/yourname/quant-platform/main/badge.png)

## 功能

- **多因子评分引擎** — 9 维度评分模型，覆盖 77+ 品类自动排序
- **实时数据看板** — 浏览器打开即用，行情自动刷新
- **组合优化器** — Max Sharpe / Risk Parity / Min Variance / Equal Weight
- **策略回测引擎** — 月度/周度调仓，净值曲线可视化
- **三层风控系统** — 止损/止盈/仓位限制/VaR/Beta
- **自动日报生成** — 每日 JSON + 文本双格式报告

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py

# 浏览器打开
# http://localhost:3000
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python / Flask |
| 计算 | Pandas / NumPy / SciPy |
| 前端 | HTML5 / ECharts / 响应式布局 |
| 数据 | akshare (东方财富) / 本地缓存降级 |

## 项目结构

```
quant_python/
├── app.py              # Flask 服务 (13 API + 5 页面)
├── data_engine.py      # 数据引擎 (akshare + 缓存 + 降级)
├── factor_engine.py    # 9因子评分模型
├── screener.py         # 全品类筛选排序
├── portfolio.py        # 组合优化器
├── risk.py             # 风控模块
├── backtest.py         # 回测引擎
├── report.py           # 报告生成器
├── templates/          # 前端页面
└── requirements.txt    # 依赖列表
```

## 免责声明

本平台仅供学习研究使用，不构成任何投资建议。所有数据和算法输出仅供参考，使用者自行承担风险。

## License

MIT License — 详见 [LICENSE](LICENSE) 文件
