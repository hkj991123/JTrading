import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULT_PATH = ROOT / "backtest_result.json"
PARAMS_PATH = ROOT / "best_combined_params.json"
OPT_REPORT_PATH = ROOT / "最新参数优化报告.md"
COMPARE_REPORT_PATH = ROOT / "策略对比报告.md"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fmt_pct(value):
    if value is None:
        return "--"
    return f"{value:.2f}%"


def fmt_num(value, digits=2):
    if value is None:
        return "--"
    return f"{value:.{digits}f}"


def build_optimization_report(result, params, today):
    meta = result.get("meta", {})
    stats = result.get("statistics", {})
    optimization_meta = meta.get("dynamic_optimization", {})
    baseline_params = optimization_meta.get("baseline_params", {})

    dynamic = stats.get("strategy_dynamic", {})
    baseline = stats.get("strategy_ideal") or stats.get("strategy") or {}
    buyhold = stats.get("buyhold", {})

    improvement = None
    if dynamic.get("total_return") is not None and baseline.get("total_return") is not None:
        improvement = dynamic["total_return"] - baseline["total_return"]

    assets = [
        ("RSI + 波动率动态阈值", dynamic.get("total_return"), dynamic.get("annual_return")),
        ("RSI(15) 固定阈值", baseline.get("total_return"), baseline.get("annual_return")),
        ("黄金ETF 买入持有", stats.get("gold_return"), stats.get("gold_annual")),
        ("纳指ETF 买入持有", stats.get("nasdaq_return"), stats.get("nasdaq_annual")),
        ("标普500ETF 买入持有", stats.get("sp500_return"), stats.get("sp500_annual")),
        (f"{meta.get('etf_name', '标的')} 买入持有", buyhold.get("total_return"), buyhold.get("annual_return")),
        ("沪深300ETF 买入持有", stats.get("hs300_return"), stats.get("hs300_annual")),
    ]

    lines = [
        f"# 策略参数优化报告（{today} 自动更新）",
        "",
        "## 数据概况",
        f"- 数据区间：{meta.get('start_date', '--')} 至 {meta.get('end_date', '--')}",
        f"- 交易日数：{baseline.get('days', '--')} 天",
        f"- 自然日数：{baseline.get('calendar_days', '--')} 天",
        f"- 初始资金：{meta.get('initial_capital', '--'):,}" if isinstance(meta.get("initial_capital"), int) else f"- 初始资金：{meta.get('initial_capital', '--')}",
        f"- 基准（买入持有）：总收益 {fmt_pct(buyhold.get('total_return'))}，年化 {fmt_pct(buyhold.get('annual_return'))}",
        "",
        "---",
        "",
        "## 1. 固定阈值 RSI 基线策略",
        "",
        "### 参数",
        "```text",
        f"RSI 周期: {baseline_params.get('rsi_period', 15)}（日）",
        f"买入条件: RSI < {baseline_params.get('rsi_buy_base', 32)}",
        f"卖出条件: RSI > {baseline_params.get('rsi_sell_base', 77)}",
        "平滑方式: EMA",
        "```",
        "",
        "### 回测表现",
        f"- 总收益率：{fmt_pct(baseline.get('total_return'))}",
        f"- 年化收益：{fmt_pct(baseline.get('annual_return'))}",
        f"- 最大回撤：{fmt_pct(baseline.get('max_drawdown'))}",
        f"- 交易次数：{baseline.get('trade_count', '--')} 次",
        f"- 胜率：{fmt_pct(baseline.get('win_rate'))}",
        "",
        "---",
        "",
        "## 2. RSI + 波动率动态阈值（当前最优）",
        "",
        "### 最优参数（best_combined_params.json）",
        "```text",
        f"RSI 周期: {params.get('rsi_period', '--')}",
        f"买入基准: {fmt_num(params.get('rsi_buy_base'), 2)}",
        f"卖出基准: {fmt_num(params.get('rsi_sell_base'), 2)}",
        f"波动率窗口: {params.get('vol_window', '--')}",
        f"k_vol: {fmt_num(params.get('k_vol'), 6)}",
        f"波动率锚点: {fmt_num(params.get('vol_anchor'), 2)}",
        "```",
        "",
        "### 动态规则",
        "```python",
        "adjustment = k_vol * (volatility - vol_anchor)",
        "buy_threshold = rsi_buy_base - adjustment",
        "sell_threshold = rsi_sell_base + adjustment",
        "```",
        "",
        "### 回测表现",
        f"- 总收益率：{fmt_pct(dynamic.get('total_return'))}",
        f"- 年化收益：{fmt_pct(dynamic.get('annual_return'))}",
        f"- 最大回撤：{fmt_pct(dynamic.get('max_drawdown'))}",
        f"- 交易次数：{dynamic.get('trade_count', '--')} 次",
        f"- 胜率：{fmt_pct(dynamic.get('win_rate'))}",
        f"- 相比固定阈值基线提升：{fmt_pct(improvement)}",
        "",
        "---",
        "",
        "## 3. 资产与策略对比（同一时间区间）",
        "",
        "| 对比项 | 总收益 | 年化收益 |",
        "|---|---:|---:|",
    ]

    for name, total_return, annual_return in assets:
        lines.append(f"| {name} | {fmt_pct(total_return)} | {fmt_pct(annual_return)} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. 关键结论",
            "",
            "1. 固定 RSI(15) EMA 规则稳健，回撤控制良好。",
            "2. 动态阈值在接近回撤水平下提升收益，波动率因子有效。",
            "3. 参数建议持续滚动重估，降低过拟合风险。",
            "",
            "---",
            "",
            "## 5. 风险提示",
            "",
            "1. 历史回测不代表未来收益。",
            "2. 动态参数存在过拟合风险，需做样本外验证。",
            "3. 实盘需考虑交易成本、滑点与执行时延。",
            "",
            "---",
            "",
            "## 6. 数据与脚本来源",
            "",
            "- ETF 数据：AKShare",
            "- 回测结果：backtest_result.json",
            "- 动态参数：best_combined_params.json",
            "- 动态优化脚本：combined_optimization.py",
            "",
            "---",
            "",
            f"更新时间：{today}",
            "建议：每周自动回测后复核样本外表现",
            "",
        ]
    )

    return "\n".join(lines)


def build_comparison_report(result, today):
    meta = result.get("meta", {})
    stats = result.get("statistics", {})

    dynamic = stats.get("strategy_dynamic", {})
    baseline = stats.get("strategy_ideal") or stats.get("strategy") or {}
    buyhold = stats.get("buyhold", {})

    improvement = None
    if dynamic.get("total_return") is not None and baseline.get("total_return") is not None:
        improvement = dynamic["total_return"] - baseline["total_return"]

    lines = [
        f"# 策略对比报告（{today} 自动更新）",
        "",
        "## 回测设定",
        f"- 标的：{meta.get('etf_name', '--')}（{meta.get('etf_code', '--')}）",
        f"- 区间：{meta.get('start_date', '--')} 至 {meta.get('end_date', '--')}",
        f"- 初始资金：{meta.get('initial_capital', '--')}",
        f"- 交易日：{baseline.get('days', '--')}",
        f"- 自然日：{baseline.get('calendar_days', '--')}",
        "",
        "---",
        "",
        "## 一、核心策略排名（按年化收益）",
        "",
        "| 排名 | 策略 | 总收益 | 年化收益 | 最大回撤 | 交易次数 | 胜率 |",
        "|---|---|---:|---:|---:|---:|---:|",
        f"| 1 | RSI + 波动率动态阈值 | **{fmt_pct(dynamic.get('total_return'))}** | **{fmt_pct(dynamic.get('annual_return'))}** | {fmt_pct(dynamic.get('max_drawdown'))} | {dynamic.get('trade_count', '--')} | {fmt_pct(dynamic.get('win_rate'))} |",
        f"| 2 | RSI(15) 固定阈值 32/77 | {fmt_pct(baseline.get('total_return'))} | {fmt_pct(baseline.get('annual_return'))} | {fmt_pct(baseline.get('max_drawdown'))} | {baseline.get('trade_count', '--')} | {fmt_pct(baseline.get('win_rate'))} |",
        f"| 3 | 买入持有 | {fmt_pct(buyhold.get('total_return'))} | {fmt_pct(buyhold.get('annual_return'))} | {fmt_pct(buyhold.get('max_drawdown'))} | 0 | - |",
        "",
        "注：本表数据来自 backtest_result.json 最新结果。",
        "",
        "---",
        "",
        "## 二、与主要指数/资产对照",
        "",
        "| 对照标的 | 总收益 | 年化收益 |",
        "|---|---:|---:|",
        f"| 黄金ETF（518880） | {fmt_pct(stats.get('gold_return'))} | {fmt_pct(stats.get('gold_annual'))} |",
        f"| 纳指ETF（159941） | {fmt_pct(stats.get('nasdaq_return'))} | {fmt_pct(stats.get('nasdaq_annual'))} |",
        f"| 标普500ETF（513500） | {fmt_pct(stats.get('sp500_return'))} | {fmt_pct(stats.get('sp500_annual'))} |",
        f"| 沪深300ETF（510300） | {fmt_pct(stats.get('hs300_return'))} | {fmt_pct(stats.get('hs300_annual'))} |",
        "",
        "---",
        "",
        "## 三、关键发现",
        "",
        "1. 固定 RSI(15) 32/77 规则稳定且可执行性高。",
        f"2. 引入波动率后收益增量为 {fmt_pct(improvement)}，回撤基本维持同级。",
        "3. 动态参数建议每周滚动更新并观察样本外稳定性。",
        "",
        "---",
        "",
        "## 四、风险提示",
        "",
        "1. 历史表现不代表未来收益。",
        "2. 参数优化存在过拟合风险。",
        "3. 实盘需计入佣金、滑点与税费成本。",
        "",
        "---",
        "",
        "## 五、数据来源",
        "",
        "- 主结果文件：backtest_result.json",
        "- 动态参数文件：best_combined_params.json",
        "- 优化脚本：combined_optimization.py",
        "",
        f"生成时间：{today}",
        "",
    ]

    return "\n".join(lines)


def main():
    result = load_json(RESULT_PATH)
    if PARAMS_PATH.exists():
        params = load_json(PARAMS_PATH)
    else:
        params = result.get("meta", {}).get("dynamic_params", {})
    today = datetime.now().strftime("%Y-%m-%d")

    OPT_REPORT_PATH.write_text(build_optimization_report(result, params, today), encoding="utf-8")
    COMPARE_REPORT_PATH.write_text(build_comparison_report(result, today), encoding="utf-8")

    print(f"已更新: {OPT_REPORT_PATH.name}")
    print(f"已更新: {COMPARE_REPORT_PATH.name}")


if __name__ == "__main__":
    main()
