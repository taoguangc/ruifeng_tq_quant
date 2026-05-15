# -*- coding: utf-8 -*-
"""
锐锋 15分钟自适应趋势策略 V2.3-A
特点：
- 彻底静默（无 TqSdk INFO）
- Hurst 趋势过滤（修正版）
- KAMA 动量趋势
- 简化但有效的趋势系统
"""

import os
import sys
import numpy as np
import pandas as pd
import logging

from datetime import date
from typing import Any
from tqsdk import TqApi, TqAuth, TqBacktest, TqSim, TargetPosTask
from tqsdk.ta import ATR

import config as cfg


def get_data_field(data: Any, name: str, default: Any = None) -> Any:
    if isinstance(data, dict):
        return data.get(name, default)
    return getattr(data, name, default)


# =========================================================
# 彻底屏蔽 TQSDK 输出（关键）
# =========================================================
os.environ["TQSDK_LOG_LEVEL"] = "ERROR"
logging.disable(logging.CRITICAL)

class HiddenPrints:
    """屏蔽所有底层 stdout 输出（TqSdk INFO 在这里）"""
    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._stdout


# =========================================================
# Strategy
# =========================================================
class RuifengStrategy:
    def __init__(self, api, symbol, target_signals):
        self.api = api
        self.symbol = symbol
        self.target_signals = target_signals

        self.klines = api.get_kline_serial(symbol, 15 * 60, data_length=300)
        self.klines_1h = api.get_kline_serial(symbol, 60 * 60, data_length=150)

        self.target_pos = TargetPosTask(api, symbol)

        self.last_bar_id = None
        self.trend_enabled = False

        self.last_h15 = 0.5
        self.last_h1 = 0.5

        self.debug_bars = 0
        self.debug_trend_bars = 0
        self.debug_kama_bull = 0
        self.debug_kama_bear = 0
        self.debug_h15_min = 999
        self.debug_h15_max = -999
        self.debug_h1_min = 999
        self.debug_h1_max = -999
        self.debug_h15_enable_pass = 0
        self.debug_h1_enable_pass = 0
        self.debug_hurst_enable_pass = 0
        self.debug_hurst_bull = 0
        self.debug_hurst_bear = 0
        self.debug_h15_bull = 0
        self.debug_h15_bear = 0
        self.debug_h1_bull = 0
        self.debug_h1_bear = 0
        self.debug_trend_bull = 0
        self.debug_trend_bear = 0
        self.debug_htf_bull = 0
        self.debug_htf_bear = 0
        self.debug_htf_bull_kama_bull = 0
        self.debug_htf_bear_kama_bear = 0
        self.debug_target_counts = {-1: 0, 0: 0, 1: 0}
        self.debug_target_changes = 0
        self.debug_last_target = None
        self.current_target = 0
        self.target_hold_bars = 0
        self.debug_target_events = []
        self.debug_last_state = {}

    # -------------------------
    # Hurst（稳定版）
    # -------------------------
    def compute_hurst(self, series):
        series = np.asarray(series)
        if len(series) < 20:
            return 0.5

        lags = range(2, min(20, len(series) // 2))
        tau = []
        valid_lags = []

        for lag in lags:
            diff = series[lag:] - series[:-lag]
            std = np.std(diff)
            if std > 0:
                tau.append(std)
                valid_lags.append(lag)

        if len(tau) < 5:
            return 0.5

        try:
            x = np.log(valid_lags)
            y = np.log(tau)
            slope = np.polyfit(x, y, 1)[0]
            if np.isnan(slope):
                return 0.5
            return float(np.clip(slope, 0.0, 1.0))
        except:
            return 0.5

    # -------------------------
    # KAMA（修正版）
    # -------------------------
    def compute_kama(self, close, n, fast, slow):
        close = np.asarray(close)
        kama = np.zeros(len(close))
        kama[0] = close[0]

        fast_sc = 2 / (fast + 1)
        slow_sc = 2 / (slow + 1)

        for i in range(1, len(close)):
            if i < n:
                kama[i] = close[i]
                continue

            change = abs(close[i] - close[i - n])
            volatility = np.sum(np.abs(np.diff(close[i - n:i + 1])))

            er = change / volatility if volatility != 0 else 0
            sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

            kama[i] = kama[i - 1] + sc * (close[i] - kama[i - 1])

        return kama

    # -------------------------
    # 主循环
    # -------------------------
    def run(self):
        while True:
            self.api.wait_update()

            if len(self.klines) < 100 or len(self.klines_1h) < 50:
                continue

            current_id = self.klines.iloc[-1]["id"]
            if current_id != self.last_bar_id:
                self.last_bar_id = current_id
                self.on_bar()

    # -------------------------
    # 每根K线
    # -------------------------
    def on_bar(self):
        close_15 = self.klines["close"].dropna().values
        close_1h = self.klines_1h["close"].dropna().values

        if len(close_15) < 120 or len(close_1h) < 60:
            return

        self.debug_bars += 1

        atr = ATR(self.klines, 20)["atr"].iloc[-1]
        if pd.isna(atr) or atr == 0:
            atr = 1

        # ===== Hurst（平滑）=====
        h15 = self.compute_hurst(close_15[-60:])
        h1 = self.compute_hurst(close_1h[-30:])

        self.last_h15 = self.last_h15 * 0.7 + h15 * 0.3
        self.last_h1 = self.last_h1 * 0.7 + h1 * 0.3
        self.debug_h15_min = min(self.debug_h15_min, self.last_h15)
        self.debug_h15_max = max(self.debug_h15_max, self.last_h15)
        self.debug_h1_min = min(self.debug_h1_min, self.last_h1)
        self.debug_h1_max = max(self.debug_h1_max, self.last_h1)

        h15_enable_pass = self.last_h15 > cfg.TREND_ENABLE_H15
        h15_env_pass = self.last_h15 > cfg.TREND_ENV_ENABLE_H15
        h1_enable_pass = self.last_h1 > cfg.TREND_ENABLE_H1
        if h15_enable_pass:
            self.debug_h15_enable_pass += 1
        if h1_enable_pass:
            self.debug_h1_enable_pass += 1
        if h15_enable_pass and h1_enable_pass:
            self.debug_hurst_enable_pass += 1

        # ===== 趋势开关 =====
        if not self.trend_enabled:
            if cfg.FILTER_MODE == "dual_hurst":
                self.trend_enabled = h15_enable_pass and h1_enable_pass
            else:
                self.trend_enabled = h15_env_pass
        else:
            if cfg.FILTER_MODE == "dual_hurst":
                if (self.last_h15 < cfg.TREND_DISABLE_H15 or
                    self.last_h1 < cfg.TREND_DISABLE_H1):
                    self.trend_enabled = False
            else:
                if self.last_h15 < cfg.TREND_ENV_DISABLE_H15:
                    self.trend_enabled = False

        # ===== KAMA =====
        fk = self.compute_kama(
            close_15,
            cfg.KAMA_FAST_PERIOD,
            cfg.KAMA_FAST,
            cfg.KAMA_SLOW
        )

        sk = self.compute_kama(
            close_15,
            cfg.KAMA_SLOW_PERIOD,
            cfg.KAMA_SLOW_FAST,
            cfg.KAMA_SLOW_SLOW
        )

        fk_1h = self.compute_kama(
            close_1h,
            cfg.KAMA_FAST_PERIOD,
            cfg.KAMA_FAST,
            cfg.KAMA_SLOW
        )

        sk_1h = self.compute_kama(
            close_1h,
            cfg.KAMA_SLOW_PERIOD,
            cfg.KAMA_SLOW_FAST,
            cfg.KAMA_SLOW_SLOW
        )

        # ===== 动量 =====
        slope_f = (fk[-1] - fk[-3]) / atr
        slope_s = (sk[-1] - sk[-3]) / atr
        dist = abs(fk[-1] - sk[-1])

        htf_slope_f = (fk_1h[-1] - fk_1h[-3]) / atr
        htf_slope_s = (sk_1h[-1] - sk_1h[-3]) / atr
        htf_bull = (
            htf_slope_f > cfg.HTF_KAMA_SLOPE_THRESHOLD and
            htf_slope_s > 0 and
            fk_1h[-1] > sk_1h[-1]
        )
        htf_bear = (
            htf_slope_f < -cfg.HTF_KAMA_SLOPE_THRESHOLD and
            htf_slope_s < 0 and
            fk_1h[-1] < sk_1h[-1]
        )

        # ===== 信号（放宽版）=====
        kama_bull = (
            slope_f > 0.12 and
            slope_s > 0.10 and
            fk[-1] > sk[-1]
        )

        kama_bear = (
            slope_f < -0.12 and
            slope_s < -0.10 and
            fk[-1] < sk[-1]
        )

        if self.trend_enabled:
            self.debug_trend_bars += 1
        if kama_bull:
            self.debug_kama_bull += 1
        if kama_bear:
            self.debug_kama_bear += 1
        if h15_enable_pass and h1_enable_pass and kama_bull:
            self.debug_hurst_bull += 1
        if h15_enable_pass and h1_enable_pass and kama_bear:
            self.debug_hurst_bear += 1
        if h15_enable_pass and kama_bull:
            self.debug_h15_bull += 1
        if h15_enable_pass and kama_bear:
            self.debug_h15_bear += 1
        if h1_enable_pass and kama_bull:
            self.debug_h1_bull += 1
        if h1_enable_pass and kama_bear:
            self.debug_h1_bear += 1
        if self.trend_enabled and kama_bull:
            self.debug_trend_bull += 1
        if self.trend_enabled and kama_bear:
            self.debug_trend_bear += 1
        if htf_bull:
            self.debug_htf_bull += 1
        if htf_bear:
            self.debug_htf_bear += 1
        if htf_bull and kama_bull:
            self.debug_htf_bull_kama_bull += 1
        if htf_bear and kama_bear:
            self.debug_htf_bear_kama_bear += 1

        self.debug_last_state = {
            "h15": self.last_h15,
            "h1": self.last_h1,
            "trend_enabled": self.trend_enabled,
            "slope_f": slope_f,
            "slope_s": slope_s,
            "fk_gt_sk": fk[-1] > sk[-1],
            "htf_slope_f": htf_slope_f,
            "htf_slope_s": htf_slope_s,
            "htf_bull": htf_bull,
            "htf_bear": htf_bear,
        }

        target = 0

        if self.trend_enabled:
            if cfg.FILTER_MODE == "dual_hurst":
                if kama_bull:
                    target = 1
                elif kama_bear:
                    target = -1
            else:
                if kama_bull and htf_bull:
                    target = 1
                elif kama_bear and htf_bear:
                    target = -1

        if self.current_target != 0 and target == 0 and self.target_hold_bars < cfg.MIN_HOLD_BARS:
            target = self.current_target

        if target != self.current_target:
            self.current_target = target
            self.target_hold_bars = 0
        elif target != 0:
            self.target_hold_bars += 1

        self.debug_target_counts[target] += 1
        if target != self.debug_last_target:
            self.debug_target_changes += 1
            self.debug_last_target = target
            if len(self.debug_target_events) < 20:
                self.debug_target_events.append({
                    "bar_id": self.last_bar_id,
                    "target": target,
                    "trend_enabled": self.trend_enabled,
                    "kama_bull": kama_bull,
                    "kama_bear": kama_bear,
                    "htf_bull": htf_bull,
                    "htf_bear": htf_bear,
                })

        self.target_pos.set_target_volume(target)

        if target != 0:
            self.target_signals.append(target)


# =========================================================
# main
# =========================================================
if __name__ == "__main__":

    api = None
    target_signals = []
    initial_balance = None

    try:
        api = TqApi(
            TqSim(init_balance=cfg.INITIAL_CAPITAL),
            backtest=TqBacktest(
                start_dt=date(2023, 1, 1),
                end_dt=date(2024, 4, 1)
            ),
            auth=TqAuth(cfg.TQ_USER, cfg.TQ_PASSWORD),
            web_gui=False
        )

        symbol = api.get_quote("KQ.m@SHFE.rb").underlying_symbol

        print(f"开始回测: {symbol}")
        print("回测区间: 2023-01-01 ~ 2024-04-01\n")

        strategy = RuifengStrategy(api, symbol, target_signals)
        initial_balance = api.get_account().balance

        # 🔥 关键：彻底屏蔽 TQSdk 输出
        with HiddenPrints():
            strategy.run()

    except KeyboardInterrupt:
        print("\n手动停止回测")

    except Exception as e:
        if "回测结束" not in str(e):
            print("错误:", e)

    finally:
        print("\n========== 回测结果 ==========")
        print(f"非零目标信号数: {len(target_signals)}")
        print(f"目标信号方向合计: {sum(target_signals)}")

        if cfg.DEBUG_SIGNAL_DIAGNOSTICS and 'strategy' in locals():
            print("\n========== 信号诊断 ==========")
            print(f"过滤模式: {cfg.FILTER_MODE}")
            print(f"有效K线数: {strategy.debug_bars}")
            print(f"趋势开启K线数: {strategy.debug_trend_bars}")
            print(f"H15范围: {strategy.debug_h15_min:.3f} ~ {strategy.debug_h15_max:.3f}")
            print(f"H1范围: {strategy.debug_h1_min:.3f} ~ {strategy.debug_h1_max:.3f}")
            print(f"H15达到开启阈值K线数: {strategy.debug_h15_enable_pass}")
            print(f"H1达到开启阈值K线数: {strategy.debug_h1_enable_pass}")
            print(f"H15/H1同时达到开启阈值K线数: {strategy.debug_hurst_enable_pass}")
            print(f"KAMA多头信号数: {strategy.debug_kama_bull}")
            print(f"KAMA空头信号数: {strategy.debug_kama_bear}")
            print(f"H15通过且KAMA多头数: {strategy.debug_h15_bull}")
            print(f"H15通过且KAMA空头数: {strategy.debug_h15_bear}")
            print(f"H1通过且KAMA多头数: {strategy.debug_h1_bull}")
            print(f"H1通过且KAMA空头数: {strategy.debug_h1_bear}")
            print(f"Hurst同时通过且KAMA多头数: {strategy.debug_hurst_bull}")
            print(f"Hurst同时通过且KAMA空头数: {strategy.debug_hurst_bear}")
            print(f"趋势开启且KAMA多头数: {strategy.debug_trend_bull}")
            print(f"趋势开启且KAMA空头数: {strategy.debug_trend_bear}")
            print(f"1h方向多头K线数: {strategy.debug_htf_bull}")
            print(f"1h方向空头K线数: {strategy.debug_htf_bear}")
            print(f"1h多头且15m KAMA多头数: {strategy.debug_htf_bull_kama_bull}")
            print(f"1h空头且15m KAMA空头数: {strategy.debug_htf_bear_kama_bear}")
            print(f"目标=-1 K线数: {strategy.debug_target_counts[-1]}")
            print(f"目标=0 K线数: {strategy.debug_target_counts[0]}")
            print(f"目标=1 K线数: {strategy.debug_target_counts[1]}")
            print(f"目标仓位变化次数: {strategy.debug_target_changes}")
            if strategy.debug_target_events:
                print("目标仓位变化明细:")
                for event in strategy.debug_target_events:
                    print(
                        f"  bar_id={event['bar_id']}, "
                        f"target={event['target']}, "
                        f"trend={event['trend_enabled']}, "
                        f"bull={event['kama_bull']}, "
                        f"bear={event['kama_bear']}, "
                        f"htf_bull={event['htf_bull']}, "
                        f"htf_bear={event['htf_bear']}"
                    )
            if strategy.debug_last_state:
                print(
                    "最后状态: "
                    f"H15={strategy.debug_last_state['h15']:.3f}, "
                    f"H1={strategy.debug_last_state['h1']:.3f}, "
                    f"trend={strategy.debug_last_state['trend_enabled']}, "
                    f"slope_f={strategy.debug_last_state['slope_f']:.3f}, "
                    f"slope_s={strategy.debug_last_state['slope_s']:.3f}, "
                    f"fk_gt_sk={strategy.debug_last_state['fk_gt_sk']}, "
                    f"htf_slope_f={strategy.debug_last_state['htf_slope_f']:.3f}, "
                    f"htf_slope_s={strategy.debug_last_state['htf_slope_s']:.3f}, "
                    f"htf_bull={strategy.debug_last_state['htf_bull']}, "
                    f"htf_bear={strategy.debug_last_state['htf_bear']}"
                )

        if api:
            try:
                tq_trades = list(api.get_trade().values())
                tq_orders = list(api.get_order().values())
                filled_volume = sum(int(get_data_field(trade, "volume", 0) or 0) for trade in tq_trades)

                print("\n========== 成交诊断 ==========")
                print(f"TQSDK成交笔数: {len(tq_trades)}")
                print(f"TQSDK成交手数: {filled_volume}")
                print(f"TQSDK委托笔数: {len(tq_orders)}")

                account = api.get_account()
                base_balance = initial_balance or account.balance
                pnl = account.balance - base_balance

                quote = api.get_quote(symbol)
                volume_multiple = get_data_field(quote, "volume_multiple", 0) or 0
                last_price = get_data_field(quote, "last_price", 0) or 0
                one_lot_notional = last_price * volume_multiple if last_price and volume_multiple else 0
                max_position_notional = one_lot_notional

                print("\n========== 收益率归因 ==========")
                print(f"回测初始权益: {base_balance:,.2f}")
                print(f"配置初始资金: {cfg.INITIAL_CAPITAL:,.2f}")
                print(f"每次目标仓位: 1手")
                if one_lot_notional:
                    print(f"单手名义价值估算: {one_lot_notional:,.2f}")
                    print(f"最大名义仓位/回测权益: {max_position_notional / base_balance * 100:.3f}%")

                print(f"最终权益: {account.balance:,.2f}")
                print(f"总盈亏: {pnl:,.2f}")
                print(f"收益率: {pnl / base_balance * 100:.2f}%")

            except:
                pass

            api.close()

        print("==============================")
