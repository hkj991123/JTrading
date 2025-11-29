"""
周K线 RSI(14) 策略回测测试
对比日K线和周K线的RSI策略效果
"""

import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime

# ============ 配置参数 ============
ETF_CODE = "512890"
ETF_NAME = "红利低波ETF"
RSI_PERIOD = 14
RSI_BUY_THRESHOLD = 40
RSI_SELL_THRESHOLD = 70
INITIAL_CAPITAL = 100000


def calculate_rsi(prices, period=14):
    """计算RSI指标（Wilder's Smoothing Method）"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    # 使用EMA方式计算后续值
    for i in range(period, len(prices)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def get_etf_data(code, period="daily"):
    """获取ETF数据
    
    Args:
        code: ETF代码
        period: 周期，"daily" 或 "weekly"
    """
    print(f"正在获取 {code} {period} 数据...")
    try:
        df = ak.fund_etf_hist_em(symbol=code, period=period, adjust="qfq")
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        })
        df = df.sort_values('date').reset_index(drop=True)
        print(f"获取到 {len(df)} 条 {period} 数据")
        return df
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None


def get_etf_dividend():
    """获取ETF分红数据"""
    dividend_data = [
        {'date': '2017-01-06', 'dividend': 0.028},
        {'date': '2018-01-05', 'dividend': 0.041},
        {'date': '2019-01-04', 'dividend': 0.058},
        {'date': '2020-01-09', 'dividend': 0.074},
        {'date': '2021-01-07', 'dividend': 0.048},
        {'date': '2022-01-06', 'dividend': 0.042},
        {'date': '2023-01-05', 'dividend': 0.072},
        {'date': '2024-01-04', 'dividend': 0.064},
        {'date': '2024-07-11', 'dividend': 0.030},
        {'date': '2025-01-06', 'dividend': 0.058},
    ]
    df = pd.DataFrame(dividend_data)
    df['date'] = pd.to_datetime(df['date'])
    return df


def run_backtest_daily(df, dividend_df, initial_capital=INITIAL_CAPITAL):
    """日线RSI策略回测"""
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
    
    cash = initial_capital
    shares = 0
    position = 0
    trades = []
    
    dividend_dict = {}
    if dividend_df is not None:
        for _, row in dividend_df.iterrows():
            dividend_dict[row['date'].strftime('%Y-%m-%d')] = row['dividend']
    
    for i, row in df.iterrows():
        date = row['date']
        price = row['close']
        rsi = row['rsi']
        date_str = date.strftime('%Y-%m-%d')
        
        # 处理分红
        if date_str in dividend_dict and shares > 0:
            dividend_amount = shares * dividend_dict[date_str]
            new_shares = dividend_amount / price
            shares += new_shares
        
        if pd.notna(rsi):
            if rsi < RSI_BUY_THRESHOLD and position == 0:
                shares_to_buy = int(cash / price / 100) * 100
                if shares_to_buy > 0:
                    cost = shares_to_buy * price
                    cash -= cost
                    shares += shares_to_buy
                    position = 1
                    trades.append({
                        'date': date_str,
                        'action': '买入',
                        'price': price,
                        'rsi': round(rsi, 2)
                    })
                    
            elif rsi > RSI_SELL_THRESHOLD and position == 1:
                if shares > 0:
                    sell_shares = int(shares / 100) * 100
                    if sell_shares > 0:
                        revenue = sell_shares * price
                        cash += revenue
                        shares -= sell_shares
                        if shares < 100:
                            cash += shares * price
                            shares = 0
                        position = 0
                        trades.append({
                            'date': date_str,
                            'action': '卖出',
                            'price': price,
                            'rsi': round(rsi, 2)
                        })
    
    final_value = cash + shares * df.iloc[-1]['close']
    total_return = (final_value / initial_capital - 1) * 100
    
    return {
        'final_value': final_value,
        'total_return': round(total_return, 2),
        'trades': trades,
        'trade_count': len([t for t in trades if t['action'] == '买入']),
        'final_position': '持仓' if position == 1 else '空仓'
    }


def run_backtest_weekly(daily_df, weekly_df, dividend_df, initial_capital=INITIAL_CAPITAL):
    """
    周线RSI策略回测
    - 使用周K线计算RSI信号
    - 在日线上执行交易（周一开盘或信号当天收盘）
    """
    weekly_df = weekly_df.copy()
    daily_df = daily_df.copy()
    
    # 计算周线RSI
    weekly_df['rsi'] = calculate_rsi(weekly_df['close'], RSI_PERIOD)
    
    cash = initial_capital
    shares = 0
    position = 0
    trades = []
    
    # 创建周线RSI信号映射 (周五日期 -> RSI值)
    weekly_signals = {}
    for _, row in weekly_df.iterrows():
        if pd.notna(row['rsi']):
            weekly_signals[row['date'].strftime('%Y-%m-%d')] = row['rsi']
    
    # 分红字典
    dividend_dict = {}
    if dividend_df is not None:
        for _, row in dividend_df.iterrows():
            dividend_dict[row['date'].strftime('%Y-%m-%d')] = row['dividend']
    
    # 找到每个日期属于哪一周
    daily_df['week_end'] = daily_df['date'].dt.to_period('W').dt.end_time.dt.date
    
    current_week_rsi = None
    
    for i, row in daily_df.iterrows():
        date = row['date']
        price = row['close']
        date_str = date.strftime('%Y-%m-%d')
        
        # 处理分红
        if date_str in dividend_dict and shares > 0:
            dividend_amount = shares * dividend_dict[date_str]
            new_shares = dividend_amount / price
            shares += new_shares
        
        # 更新当周RSI（如果是周末收盘日）
        if date_str in weekly_signals:
            current_week_rsi = weekly_signals[date_str]
        
        # 使用周线RSI信号交易
        if current_week_rsi is not None:
            if current_week_rsi < RSI_BUY_THRESHOLD and position == 0:
                shares_to_buy = int(cash / price / 100) * 100
                if shares_to_buy > 0:
                    cost = shares_to_buy * price
                    cash -= cost
                    shares += shares_to_buy
                    position = 1
                    trades.append({
                        'date': date_str,
                        'action': '买入',
                        'price': price,
                        'rsi': round(current_week_rsi, 2),
                        'type': '周线信号'
                    })
                    current_week_rsi = None  # 信号已使用
                    
            elif current_week_rsi > RSI_SELL_THRESHOLD and position == 1:
                if shares > 0:
                    sell_shares = int(shares / 100) * 100
                    if sell_shares > 0:
                        revenue = sell_shares * price
                        cash += revenue
                        shares -= sell_shares
                        if shares < 100:
                            cash += shares * price
                            shares = 0
                        position = 0
                        trades.append({
                            'date': date_str,
                            'action': '卖出',
                            'price': price,
                            'rsi': round(current_week_rsi, 2),
                            'type': '周线信号'
                        })
                        current_week_rsi = None  # 信号已使用
    
    final_value = cash + shares * daily_df.iloc[-1]['close']
    total_return = (final_value / initial_capital - 1) * 100
    
    return {
        'final_value': final_value,
        'total_return': round(total_return, 2),
        'trades': trades,
        'trade_count': len([t for t in trades if t['action'] == '买入']),
        'final_position': '持仓' if position == 1 else '空仓'
    }


def calculate_buy_hold(df, dividend_df, initial_capital=INITIAL_CAPITAL):
    """计算买入持有收益"""
    start_price = df.iloc[0]['close']
    shares = int(initial_capital / start_price / 100) * 100
    remaining_cash = initial_capital - shares * start_price
    
    dividend_dict = {}
    if dividend_df is not None:
        for _, row in dividend_df.iterrows():
            dividend_dict[row['date'].strftime('%Y-%m-%d')] = row['dividend']
    
    for _, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        if date_str in dividend_dict and shares > 0:
            dividend_amount = shares * dividend_dict[date_str]
            new_shares = dividend_amount / price
            shares += new_shares
    
    final_value = remaining_cash + shares * df.iloc[-1]['close']
    total_return = (final_value / initial_capital - 1) * 100
    
    return round(total_return, 2)


def main():
    print("=" * 70)
    print("红利低波ETF (512890) RSI策略对比测试")
    print("日K线 RSI(14) vs 周K线 RSI(14)")
    print("=" * 70)
    
    # 获取数据
    daily_df = get_etf_data(ETF_CODE, "daily")
    weekly_df = get_etf_data(ETF_CODE, "weekly")
    dividend_df = get_etf_dividend()
    
    if daily_df is None or weekly_df is None:
        print("获取数据失败")
        return
    
    print(f"\n回测区间: {daily_df['date'].min().strftime('%Y-%m-%d')} 至 {daily_df['date'].max().strftime('%Y-%m-%d')}")
    print(f"日K线数据: {len(daily_df)} 条")
    print(f"周K线数据: {len(weekly_df)} 条")
    
    # 计算买入持有收益
    buyhold_return = calculate_buy_hold(daily_df, dividend_df)
    
    # 日线RSI回测
    print("\n" + "-" * 50)
    print("执行日K线 RSI(14) 回测...")
    daily_result = run_backtest_daily(daily_df, dividend_df)
    
    # 周线RSI回测
    print("\n执行周K线 RSI(14) 回测...")
    weekly_result = run_backtest_weekly(daily_df, weekly_df, dividend_df)
    
    # 输出结果
    print("\n" + "=" * 70)
    print("回测结果对比")
    print("=" * 70)
    
    days = len(daily_df)
    
    def calc_annual(total_ret):
        return round(((1 + total_ret / 100) ** (365 / days) - 1) * 100, 2)
    
    print(f"\n{'策略':<20} {'总收益率':<15} {'年化收益':<15} {'交易次数':<10} {'最终状态':<10}")
    print("-" * 70)
    
    # 买入持有
    buyhold_annual = calc_annual(buyhold_return)
    print(f"{'买入持有(全收益)':<18} {buyhold_return:>10.2f}% {buyhold_annual:>12.2f}% {'-':>10} {'持仓':>10}")
    
    # 日线RSI
    daily_annual = calc_annual(daily_result['total_return'])
    print(f"{'日K线 RSI(14)':<18} {daily_result['total_return']:>10.2f}% {daily_annual:>12.2f}% {daily_result['trade_count']:>10} {daily_result['final_position']:>10}")
    
    # 周线RSI
    weekly_annual = calc_annual(weekly_result['total_return'])
    print(f"{'周K线 RSI(14)':<18} {weekly_result['total_return']:>10.2f}% {weekly_annual:>12.2f}% {weekly_result['trade_count']:>10} {weekly_result['final_position']:>10}")
    
    # 详细交易记录
    print("\n" + "=" * 70)
    print("日K线 RSI 交易记录 (最近10笔)")
    print("-" * 70)
    for trade in daily_result['trades'][-10:]:
        print(f"  {trade['date']} {trade['action']} @ {trade['price']:.3f} (RSI={trade['rsi']})")
    
    print("\n" + "=" * 70)
    print("周K线 RSI 交易记录 (全部)")
    print("-" * 70)
    for trade in weekly_result['trades']:
        print(f"  {trade['date']} {trade['action']} @ {trade['price']:.3f} (周RSI={trade['rsi']})")
    
    # 分析对比
    print("\n" + "=" * 70)
    print("分析总结")
    print("=" * 70)
    
    print(f"""
【日K线 RSI(14)】
  - 基于日线收盘价计算RSI，信号更频繁
  - 交易次数: {daily_result['trade_count']} 次
  - 能捕捉短期波动，但可能产生更多噪音信号
  
【周K线 RSI(14)】  
  - 基于周线收盘价计算RSI，信号更稳定
  - 交易次数: {weekly_result['trade_count']} 次
  - 过滤短期噪音，但可能错过一些交易机会

【收益对比】
  - 日线RSI策略: {daily_result['total_return']:.2f}% (年化 {daily_annual:.2f}%)
  - 周线RSI策略: {weekly_result['total_return']:.2f}% (年化 {weekly_annual:.2f}%)
  - 差异: {daily_result['total_return'] - weekly_result['total_return']:.2f}%
  
【结论】
  - {'日线RSI效果更好' if daily_result['total_return'] > weekly_result['total_return'] else '周线RSI效果更好'}
  - 周线RSI交易频率更低，适合不想频繁操作的投资者
""")


if __name__ == "__main__":
    main()
