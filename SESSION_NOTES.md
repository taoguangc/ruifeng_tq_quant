# Session Notes

## Current Context

- Project: TQSDK intraday low-frequency futures strategy.
- Goal: Gradually migrate a simplified TQSDK backtest/simulation script toward a safer live-trading-ready structure.
- Keep changes small. Do not redesign the project or strategy in one step.

## Files Added Or Updated

- `AGENTS.md`: project-level instructions for TQSDK, backtest validation, risk control, and minimal diffs.
- `opencode.json`: loads `AGENTS.md` and project skills under `.agents/skills`.
- `.env.example`: template for `TQ_USER` and `TQ_PASSWORD`.
- `.gitignore`: ignores `.env`, Python caches, and bytecode.
- `.opencodeignore`: ignores secrets, virtualenv, caches, editor files, logs, large data/archive files.
- `config.py`: now loads `.env` with `python-dotenv` and reads TQ credentials from environment variables.
- `requirements.txt`: added `python-dotenv`.
- `strategy.py`: fixed backtest PnL/return calculation to use actual TQSDK account initial balance instead of `cfg.INITIAL_CAPITAL`.

## Verified

- `python -m py_compile "config.py" "strategy.py"` passed.
- `python strategy.py` ran and produced 0 trades, 0.00 PnL, 0.00% return after the accounting fix.
- Added small signal diagnostics to `strategy.py`: current backtest has 521 valid bars, 40 KAMA long signals, 91 KAMA short signals, but 0 trend-enabled bars.
- Root cause for 0 trades is the H1 Hurst trend filter: smoothed H1 range is `-0.176 ~ 0.431`, never reaching `TREND_ENABLE_H1 = 0.51`, so all KAMA signals are blocked.
- Chose to fix the Hurst calculation rather than lower thresholds. Updated lag alignment, removed the extra square-root transform, and clipped Hurst output to `0.0 ~ 1.0`.
- After the Hurst fix, `python strategy.py` produced 7 non-zero target signals, 9 trend-enabled bars, H1 range `0.000 ~ 0.542`, final equity `9,999,902.97`, PnL `-97.03`.
- Replaced the misleading "总成交手数" summary with separate signal and TQSDK execution diagnostics. Current run: 7 non-zero target signals, 2 TQSDK trade records, 2 filled lots, 2 orders.
- Added target-position timeline diagnostics. The 7 non-zero target signals are all repeated `target=-1` bars in one short-holding segment; actual target changes are `0 -> -1 -> 0`, matching 2 TQSDK orders/fills.
- Extended the backtest window from `2024-01-01 ~ 2024-02-01` to `2024-01-01 ~ 2024-04-01`. Three-month run produced 10 non-zero target signals, 5 target changes, 4 TQSDK orders/fills, final equity `10,000,065.94`, PnL `65.94`.
- Investigated low return. Root cause 1 was account-size mismatch: TQSDK default `TqSim` initial balance is `10,000,000`, while `cfg.INITIAL_CAPITAL` is `200,000`. Added `TqSim(init_balance=cfg.INITIAL_CAPITAL)` so backtest equity matches config.
- After the balance fix, the same three-month run produced final equity `200,065.94`, PnL `65.94`, return `0.03%`. Single-lot rb notional is about `34,560`, so max notional exposure is about `17.28%` of `200,000`.
- Remaining low-return driver is low exposure time / few trades: only 25 trend-enabled 15m bars, 10 non-zero target bars, and 2 complete round-trip trades over three months.
- Added `DEBUG_SIGNAL_DIAGNOSTICS = True` in `config.py` to make the temporary diagnostics explicitly configurable.
- Added Hurst filter attribution counters. Three-month run: H15 reaches enable threshold on 148 bars, H1 reaches enable threshold on 57 bars, but both are true together on only 11 bars; trend-enabled bars are 25 due to hysteresis. This confirms the dual Hurst filter, especially high-cycle alignment, is the main exposure bottleneck.
- Lowered Hurst thresholds conservatively from enable `H15=0.52/H1=0.51`, disable `H15=0.48/H1=0.47` to enable `H15=0.48/H1=0.47`, disable `H15=0.44/H1=0.43`.
- After lowering thresholds, exposure increased but performance did not improve: trend-enabled bars `25 -> 48`, non-zero target signals `10 -> 23`, TQSDK filled lots `4 -> 6`, PnL `65.94 -> 48.90`, return `0.03% -> 0.02%`.
- Important observation: even after lowering thresholds, target `1` bars remain `0`; all trades are short-side only. This suggests the next diagnostic should focus on why long KAMA signals do not overlap with the Hurst trend gate.
- Added long/short overlap diagnostics. With thresholds `H15 enable=0.48`, `H1 enable=0.47`: total KAMA bull/bear counts are `82/276`, but Hurst-both-pass bull/bear counts are `0/16`, and trend-enabled bull/bear counts are `0/23`.
- Split H15/H1 overlap diagnostics showed the high-cycle filter is a major bottleneck but not the only issue: H15-pass bull/bear `10/34`, H1-pass bull/bear `1/40`, both-pass bull/bear `0/16`.
- Lowered only H1 further to enable `0.43`, disable `0.39`. Exposure increased but performance worsened and longs still did not appear: trend-enabled bars `73`, target changes `13`, filled lots `12`, PnL `-412.19`, return `-0.21%`, both-pass bull/bear `0/22`, trend-enabled bull/bear `0/27`.
- Conclusion: simply lowering Hurst thresholds increases low-quality short churn and does not restore long trades. The long-side issue is timing misalignment between KAMA bull signals and the dual Hurst gate, not just a too-high H1 threshold.
- Larger structural test: changed the regime logic so 15m Hurst controls trend environment and 1h KAMA controls high-cycle direction. Added `HTF_KAMA_SLOPE_THRESHOLD` and `MIN_HOLD_BARS`.
- Aggressive environment threshold `TREND_ENV_ENABLE_H15=0.38`, `TREND_ENV_DISABLE_H15=0.32` restored longs but overtraded: target `1/-1` bars `7/118`, filled lots `66`, PnL `-512.06`, return `-0.26%`.
- Added `MIN_HOLD_BARS=3` to reduce one-bar churn. It reduced fills to `56` and improved PnL to `-486.90`, but still underperformed.
- Tightened environment threshold to `TREND_ENV_ENABLE_H15=0.42`, `TREND_ENV_DISABLE_H15=0.36`. Current three-month result: target `1/-1` bars `12/109`, target changes `45`, filled lots `44`, final equity `199,895.30`, PnL `-104.70`, return `-0.05%`.
- Current state restores long trades and has richer diagnostics, but on this three-month sample it is still worse than the earlier conservative Hurst gate. Do not continue curve-fitting on this short sample without expanding the validation window.
- Added `FILTER_MODE` config, read from environment variable, with modes `directional` and `dual_hurst`. This allows comparing the newer 15m-Hurst + 1h-KAMA direction filter against the dual-Hurst gate without editing code.
- Extended the backtest window to `2023-01-01 ~ 2024-04-01` for validation.
- Long-period directional mode result: target `1/-1` bars `82/122`, target changes `77`, filled lots `76`, final equity `197,848.26`, PnL `-2,151.74`, return `-1.08%`.
- Long-period dual_hurst mode result using current lowered thresholds: target `1/-1` bars `11/39`, target changes `17`, filled lots `16`, final equity `199,594.90`, PnL `-405.10`, return `-0.20%`.
- Conclusion from long-period comparison: directional mode restores more balanced long/short exposure but overtrades and underperforms; dual_hurst is more selective and loses less. The next comparison should include the original conservative dual-Hurst thresholds before keeping the directional structure.

## Important Notes

- Real credentials should live only in local `.env`, not in tracked code.
- Current strategy is intentionally simplified and is only being used to run through the backtest flow.
- The next useful task is to add named threshold presets so `dual_hurst_conservative` can be compared against the current lowered-threshold `dual_hurst` and `directional` modes on the same long period.
- A local `tqsdk-trading-and-data.zip` exists and may be the official TQSDK skills package. Consider extracting it into `.agents/skills/tqsdk-trading-and-data/` after restart.

## Suggested Restart Prompt

Continue this TQSDK intraday low-frequency strategy project. First read `AGENTS.md`, `SESSION_NOTES.md`, `opencode.json`, `strategy.py`, and `config.py`. We just fixed the backtest return baseline. Next, diagnose why the simplified strategy has 0 trades, using small verifiable changes only.
