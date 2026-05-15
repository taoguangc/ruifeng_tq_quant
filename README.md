# Ruifeng TQ Quant

TQSDK-based intraday low-frequency futures strategy research project.

The current focus is to gradually migrate a simplified backtest/simulation script toward a safer structure that can later be adapted for live trading.

## Environment

- Python 3.13
- Windows
- TQSDK

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Credentials

Do not commit real TQSDK credentials.

Create a local `.env` file:

```env
TQ_USER=your_user
TQ_PASSWORD=your_password
```

The `.env` file is ignored by git.

## Run Backtest

```powershell
python strategy.py
```

Optional filter mode:

```powershell
$env:FILTER_MODE = "dual_hurst"
python strategy.py
```

Supported modes:

- `directional`: 15m Hurst regime filter plus 1h KAMA direction filter
- `dual_hurst`: dual Hurst regime filter

## Notes

- This project is for strategy research and backtest diagnostics.
- Live trading requires additional risk controls, order timeout handling, market-state checks, and account safety checks.
- See `SESSION_NOTES.md` for the latest debugging and validation context.
