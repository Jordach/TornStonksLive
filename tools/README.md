# tools/

Standalone analysis scripts. Nothing here is imported by the bot (`tsl_*`), and
they only need numpy, pandas and scipy. All scripts open the per-stock SQLite
files (`db/db_<ticker>.db`, table `m1`) **read-only**.

Run from the repo root. `--db-dir` defaults to `db/` in the main checkout; when
running from a git worktree, point it at the main checkout's `db/` folder.

## noise_cross_stock.py — is the minute "fuzz" shared across stocks?

Cross-stock return correlation and PCA share at several horizons, co-occurrence
of price changes, synchronised jumps, cents-vs-percent noise scaling, Roll noise
estimates per stock, time-of-day/day-of-week volatility, and optional stability
across windows of history.

    python tools/noise_cross_stock.py --days 30
    python tools/noise_cross_stock.py --days 90 --stability 10 --out noise_report.md

## noise_single_stock.py — noise shape and genuine-move detection per stock

Model: observed log price = hidden random-walk price + i.i.d. noise.

    python tools/noise_single_stock.py characterise --tickers ass fhg --days 30
    python tools/noise_single_stock.py filter --tickers ass --days 7 --out out/
    python tools/noise_single_stock.py evaluate --tickers ass --days 30

* `characterise`: cent-change histogram, ACF, variance signature, noise vs
  diffusion variance, Kalman gain.
* `filter`: CSV of latent price (Kalman / EWMA / rolling median) plus flagged
  jumps (`|innovation z| > 6`) and trends (two-sided CUSUM, k=0.125, h=25).
* `evaluate`: false-alarm rate on simulated noise and detection delay for
  injected steps/trends.

Findings (Nov 2026 data): the noise is independent per stock, proportional to
price, and small (~5–15% of 1-minute variance). Volatility dropped for every
stock on 2023-07-13, so treat earlier data as a separate regime.
