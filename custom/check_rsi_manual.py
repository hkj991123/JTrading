#!/usr/bin/env python3
"""
自定义 RSI 检查脚本 - 独立于上游代码，便于 sync
"""
import sys, json, os
from datetime import datetime
# 复用上游工具函数（通过导入，不复制代码）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from github_action_runner import fetch_etf_data, calculate_rsi_ema

def generate_custom_result(etf_code: str, output_dir: str = "docs"):
    """执行检查并生成独立的结果页面"""
    # 1. 获取数据并计算
    df = fetch_etf_data(etf_code, days=60)
    if df is None:
        return False
    
    df['rsi'] = calculate_rsi_ema(df['close'], period=15)
    latest = df.iloc[-1]
    
    # 2. 生成 JSON 数据（独立文件名，避免冲突）
    result = {
        "etf_code": etf_code,
        "rsi": round(latest['rsi'], 2),
        "price": round(latest['close'], 4),
        "signal": "买入" if latest['rsi'] < 32 else "卖出" if latest['rsi'] > 77 else "持有",
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open(f"{output_dir}/custom_rsi_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 3. 生成独立 HTML 页面（模板化，可复用）
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>RSI 手动检查结果</title></head>
<body>
<h1>📊 {etf_code} RSI 检查结果</h1>
<p>RSI(15): <strong>{result['rsi']}</strong></p>
<p>价格: ¥{result['price']}</p>
<p>信号: <span style="color:{'#22c55e' if result['signal']=='买入' else '#ef4444' if result['signal']=='卖出' else '#3b82f6'}">
{result['signal']}</span></p>
<p><small>检查时间: {result['checked_at']}</small></p>
<a href="index.html">← 返回主页</a>
</body></html>"""
    
    with open(f"{output_dir}/custom_rsi.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    return True

if __name__ == "__main__":
    etf = sys.argv[1] if len(sys.argv) > 1 else "512890"
    success = generate_custom_result(etf)
    sys.exit(0 if success else 1)
