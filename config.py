# -*- coding: utf-8 -*-
"""
锐锋 15 分钟自适应趋势策略 天勤版 全局配置
版本: V2.1.3
"""

import os

from dotenv import load_dotenv


load_dotenv()


# =====================
# 天勤账户
# =====================
TQ_USER = os.getenv("TQ_USER", "")
TQ_PASSWORD = os.getenv("TQ_PASSWORD", "")

# ===================== 账户基础 =====================
INITIAL_CAPITAL = 200000  # 初始资金 20 万
SLIPPAGE = 2              # 滑点 2tick
COMMISSION_RATE = "EXCHANGE"  # 手续费按交易所标准
DEBUG_SIGNAL_DIAGNOSTICS = True  # 输出信号、成交与过滤器诊断
FILTER_MODE = os.getenv("FILTER_MODE", "directional")  # dual_hurst / directional

# ===================== 策略核心周期 =====================
MAIN_CYCLE = "15min"      # 主周期
FILTER_CYCLE = "60min"    # 过滤周期

# ===================== 风控参数 =====================
TOTAL_RISK_LIMIT = 0.15   # 总账户风险 15%
DAILY_LOSS_LIMIT = 0.02   # 单日亏损熔断 2%
MIN_STOP_TICKS = 8        # 最小止损间距 8ticks

# ===================== Hurst 参数 =====================
HURST_WINDOW_15 = 60
HURST_WINDOW_1 = 30
HURST_SPAN_15 = 10
HURST_SPAN_1 = 5

TREND_ENABLE_H15 = 0.48
TREND_ENABLE_H1 = 0.43

TREND_DISABLE_H15 = 0.44
TREND_DISABLE_H1 = 0.39

TREND_ENV_ENABLE_H15 = 0.42
TREND_ENV_DISABLE_H15 = 0.36
HTF_KAMA_SLOPE_THRESHOLD = 0.08
MIN_HOLD_BARS = 3


# ===================== KAMA 参数 =====================
KAMA_FAST_PERIOD = 8
KAMA_SLOW_PERIOD = 18
KAMA_FAST = 2
KAMA_SLOW = 20
KAMA_SLOW_FAST = 5
KAMA_SLOW_SLOW = 40

# ===================== MS 参数 =====================
FIXED_TREND_BASE = 0.5
FIXED_EXTREME_BASE = 1.8
MS_WINDOW = 90

# ===================== 分形参数 =====================
FRACTAL_WINDOW = 5       # 5-bar 分形
FRACTAL_CONFIRM_LAG = 2  # 滞后 2 根确认

# ===================== FVG 参数 =====================
FVG_GAP_MIN = 0.2        # 最小缺口 0.2ATR
FVG_ENTITY_MIN = 0.67    # 最小实体占比
FVG_VALID_BARS = 12      # FVG 有效期 12 根 5 分钟 K 线

# ===================== 滚仓参数 =====================
ADD_POS_RISK_LIMIT = 2.5 # 滚仓总风险上限 2.5R
