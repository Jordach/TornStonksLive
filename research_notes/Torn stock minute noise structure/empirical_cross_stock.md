# Empirical cross-stock structure of Torn City 1-minute price noise

Scope: is the per-minute price "fuzz" in Torn City stock prices shared across stocks or independent per stock? Every number below comes from my own computations on the local TornStonks Live SQLite data (`db/db_<ticker>.db`, table `m1`, opened read-only), run with the reusable script `tools/noise_cross_stock.py`. I did no web research. The "source" links point to the script and to the run that produced each number.

Source key (all runs: `python tools/noise_cross_stock.py ...`):
- **[R30]** `--days 30`: window 2026-10-26 14:36 to 2026-11-25 14:35 UTC, 43,200 grid minutes — [noise_cross_stock.py](../../tools/noise_cross_stock.py)
- **[R90]** `--days 90 --horizons 1,5,15,60,240,1440 --stability 10`: window ending 2026-11-25, 129,600 grid minutes, plus ten 90-day windows spread from 2022-11-29 to 2026-11 — [noise_cross_stock.py](../../tools/noise_cross_stock.py)
- **[R365]** `--days 365 --horizons 1,60,1440`: 2025-11-25 to 2026-11-25, 523,848 fully observed 1-minute returns — [noise_cross_stock.py](../../tools/noise_cross_stock.py)
- **[R2023]** `--end 2023-05-30 --days 30`: an old window from before the 2023 regime change — [noise_cross_stock.py](../../tools/noise_cross_stock.py)
- **[MONTHLY]** an ad-hoc scan of the full history (2021-04 to 2026-11). It reuses `load_m1` from the script and computes the median across stocks of the monthly m1 log-return standard deviation, the lag-1 autocorrelation and the zero-change fraction — [noise_cross_stock.py](../../tools/noise_cross_stock.py) loader
- **[DAILY2023]** an ad-hoc daily scan from 2023-06-20 to 2023-08-10 that locates the regime change — [noise_cross_stock.py](../../tools/noise_cross_stock.py) loader

Data facts that matter for reading the results:
- Only **35** stock DB files exist locally: ass, bag, cbd, cnc, elt, evl, ewm, fhg, grn, hrg, iil, iou, ist, lag, los, lsc, mcs, msg, mun, prn, pts, sym, sys, tcc, tci, tcm, tcp, tct, tgp, ths, tmi, tsb, wlt, wsu and yaz. `db_suggestions.db` has no `m1` table. If Torn has a 36th stock, it has no local DB. — [R30]
- Every m1 row has open=high=low=close: 0 of 129,407 recent ass rows have high≠low, and 0 of 1,242,964 rows before 2023-11 do either. All timestamps fall exactly on the minute (`date % 60 == 0`). Each row is therefore a single price sampled once a minute. — ad-hoc SQL check on db_ass.db

## Q1. Are 1-minute returns correlated across stocks at lag 0, and does correlation grow with horizon?

### Takeaway
No. Cross-stock correlation is zero within sampling error at every horizon from 1 minute to 1 day, for both log returns and cent changes. The first principal component explains exactly what pure sampling noise predicts for 35 independent series (the Marchenko–Pastur edge). There is no shared m1 noise and no detectable shared trend either: Torn stock prices behave as 35 independent processes.

### Cited Findings
- 90-day window, fully observed rows only, mean / median off-diagonal correlation, with PC1 share against the Marchenko–Pastur null `(1+sqrt(N/T))^2/N` — [R90]:

| horizon | rows T | mean ρ | median ρ | 5th–95th pct ρ | min / max ρ | 1/sqrt(T) | PC1 share | MP-null PC1 | 1/N |
|---|---|---|---|---|---|---|---|---|---|
| 1m log | 129,347 | +0.0001 | +0.0001 | −0.0047 … +0.0050 | −0.0082 / +0.0097 | 0.0028 | 0.0294 | 0.0295 | 0.0286 |
| 1m cents | 129,347 | +0.0001 | +0.0001 | −0.0047 … +0.0050 | −0.0082 / +0.0097 | 0.0028 | 0.0294 | 0.0295 | 0.0286 |
| 5m log | 25,868 | +0.0006 | +0.0004 | −0.0087 … +0.0106 | −0.0139 / +0.0178 | 0.0062 | 0.0302 | 0.0307 | 0.0286 |
| 15m log | 8,623 | +0.0006 | +0.0007 | −0.0163 … +0.0174 | −0.0317 / +0.0410 | 0.0108 | 0.0315 | 0.0323 | 0.0286 |
| 60m log | 2,155 | −0.0002 | −0.0003 | −0.0365 … +0.0376 | −0.0700 / +0.0682 | 0.0215 | 0.0362 | 0.0363 | 0.0286 |
| 240m log | 539 | −0.0015 | −0.0011 | −0.0710 … +0.0697 | −0.1471 / +0.1447 | 0.0431 | 0.0422 | 0.0450 | 0.0286 |
| 1440m log | 89 | −0.0023 | −0.0024 | −0.1665 … +0.1749 | −0.3561 / +0.3412 | 0.1060 | 0.0697 | 0.0756 | 0.0286 |

  The cents rows are identical to the log rows to 4 decimals at every horizon.
- 30-day window: 1m mean ρ = 0.0000, median = 0.0003, 51.6% of pairs positive, PC1 = 0.0301 against 1/N = 0.0286. At 60m, mean ρ = −0.0008 and PC1 = 0.0400 (T = 717). — [R30]
- 365-day window: 1m mean ρ = 0.0000 (p5…p95 = ±0.0023, T = 523,848), PC1 = 0.0290. 60m mean ρ = −0.0006, PC1 = 0.0321 (T = 8,739). Daily (1440m) mean ρ = −0.0023, PC1 = 0.0488 (T = 362; MP null ≈ 0.049). — [R365]
- Lead-lag: the mean over ordered pairs of corr(r_i(t), r_j(t−lag)) for m1 log returns is +0.0001 at lag −1, +0.0001 at lag +1 and −0.0000/−0.0001 at lag +2. One stock's minute move does not spill into others a minute later. — [R30], [R90]
- Before the 2023 regime change (May 2023): 1m mean ρ = 0.0000, PC1 = 0.0300. 60m mean ρ = −0.0030, PC1 = 0.0415 (T = 705; MP null ≈ 0.040). — [R2023]
- Ten 90-day windows from 2022-11 to 2026-11: m1 mean ρ ranges from −0.0002 to +0.0001 and m1 PC1 from 0.0294 to 0.0297. 60m mean ρ ranges from −0.0010 to +0.0004 and 60m PC1 from 0.0347 to 0.0387. — [R90] stability table

### Inferences
- The spread of pairwise correlations (p5–p95 ≈ ±1.65/sqrt(T)) and the PC1 share both match what independence predicts at every horizon. Correlations do **not** grow with aggregation, so there is neither common noise at m1 nor a common trend at hourly or daily scale. A factor model of "market + idiosyncratic" has no market factor to fit.
- Cents and log returns give identical correlation results. The absence of correlation therefore does not depend on how the move is scaled.
- In practice, other stocks carry no information about a given stock's next-minute (or next-day) move. Denoising one stock cannot borrow strength from the others by averaging, though see Q4/Q5: they do share the *parameters* of the noise.

### Gaps
- Days with 89–362 observations leave limited power at the daily horizon: a common factor with pairwise ρ below about 0.05 could go undetected there. At 1 minute, the power rules out |mean ρ| > ~0.001.
- I did not test nonlinear dependence, such as correlation in |r| (shared volatility bursts) at fine time scales, beyond the time-of-day profiles in Q5 and the jump co-occurrence in Q2.

## Q2. Do all stocks change price on the same minutes? Are there synchronised events?

### Takeaway
No. Whether a stock's price changes in a given minute is independent across stocks. The number of stocks changing per minute follows the independent Poisson-binomial distribution almost exactly (variance ratio ≈ 1.00). No minute-of-hour, hour-of-day or 00:00 UTC/TCT effect shows up. Large jumps essentially never coincide across more than 3 stocks. The only synchronised thing in the data is collector gaps, which hit all stocks on the same minutes.

### Cited Findings
- Per-stock fraction of consecutive-minute pairs with zero change (30d): mean 0.228, min 0.056 (tci), max 0.589 (yaz). Over 90d: mean 0.231, min 0.097 (mcs), max 0.606 (yaz). — [R30], [R90]
- Count of stocks changing per fully observed minute (35 stocks) — [R30], [R90], [R365]:

| window | mean # changing | independent mean | variance | independent variance | ratio | P(all 35 change) obs / indep | P(none change) obs / indep | mean φ between change indicators |
|---|---|---|---|---|---|---|---|---|
| 30d | 27.01 | 27.01 | 5.588 | 5.743 | 0.973 | 2e-5 / 8e-5 | 5e-5 / ~0 | −0.0006 (max 0.111) |
| 90d | 26.93 | 26.93 | 5.847 | 5.811 | 1.006 | 4e-5 / 7e-5 | 5e-5 / ~0 | +0.0003 (max 0.054) |
| 365d | — | — | — | — | 1.009 | 3e-5 / 5e-5 | 2e-5 / ~0 | +0.0003 |

- The observed histogram of the number of stocks changing per minute matches an independent-Bernoulli simulation to within about 0.002 in every bin. Example (30d): 27 stocks 0.1663 observed vs 0.1682 simulated, 24 stocks 0.0738 vs 0.0726, 32 stocks 0.0155 vs 0.0174. — [R30]
- Direction: among minutes where at least 10 stocks change, the standard deviation of the fraction moving up is 0.0968 against 0.0963 for independent fair coins (30d), and 0.0966 against 0.0967 (90d). Stocks do not move up or down together. — [R30], [R90]
- Seasonality of change counts: the mean number of stocks changing ranges only 26.77–27.24 across minute-of-hour and 26.86–27.18 across hour-of-day (UTC). Hour 00 (the Torn City Time daily reset; TCT = UTC) gives 27.02, which is typical. — [R30]
- Simultaneous jumps, defined as |log r| > 6× the robust (MAD) standard deviation. 30d: 4,468 minutes with at least 1 jump, 136 with at least 2, 4 with at least 3, 0 with at least 5. The top minutes (e.g. 2026-11-16 03:53, 2026-11-19 18:37) show no on-the-hour or 00:00 clustering. 90d: 7,744 / 218 / 5 / 0. 365d: 33,091 / 1,005 / 28 / 0. May 2023: 8,280 / 789 / 55 / 1 (maximum 5 stocks, 2023-05-23 21:57). — [R30], [R90], [R365], [R2023]
- Jumps concentrate in particular stocks rather than particular minutes. Over 30d the median stock had 16 jumps while ist had 2,609; over 90d fhg had 1,436; over 365d evl had 4,918. — [R30], [R90], [R365]
- Gaps are synchronised. In the last 30 days every stock has exactly 127 missing minutes, the same longest gap (67 min) and 43,039 consecutive-minute returns. Missing data is collector downtime, not per-stock. — [R30]
- In the recent windows, roughly 2–6 minutes in 30–90 days have no stock changing, against ~0 expected under independence (P(none) 5e-5 observed). They are most likely stale or duplicated collector samples. They are too few to matter. — [R30], [R90]

### Inferences
- With p = 0.004 for "≥3 simultaneous jumps", the observed counts are consistent with chance coincidence of independent per-stock jumps. I found no game-wide "tick" event that moves all stocks at once.
- The game's price update seems to happen at least once a minute for every stock (77% of minute pairs show a change). Zero-change minutes are better explained by price-dependent tick quantisation (Q3) than by skipped updates.

### Gaps
- The data has one sample per minute and no seconds. I could not test sub-minute timing, i.e. whether all stocks update at the same second, or seconds-of-hour effects.
- If the game updates every stock at the same instant, independence of the *values* (Q1) still holds. Synchronised timing alone would be invisible at this resolution.

## Q3. Is the noise in absolute cents or proportional to price?

### Takeaway
Proportional. The per-minute standard deviation in cents scales almost exactly linearly with price across the 35 stocks (log-log slope ≈ 0.98), while the percentage standard deviation is flat (slope ≈ −0.02) and nearly identical for every stock, about 0.011% per minute since mid-2023. The visible differences in cents (and in zero-change frequency) between cheap and expensive stocks come from price level plus the 1-cent tick.

### Cited Findings
- Cross-sectional fit over 35 stocks — [R30], [R90], [R365], [R2023]:

| window | slope log(sd_cents) vs log(price) | slope log(sd_pct) vs log(price) | Spearman sd_cents~price | CV of sd_cents | CV of sd_pct |
|---|---|---|---|---|---|
| 30d (2026) | 0.981 | −0.019 | 0.994 | 0.613 | 0.087 |
| 90d (2026) | 0.975 | −0.025 | 0.995 | 0.617 | 0.063 |
| 365d | 0.980 | −0.020 | — | 0.620 | 0.043 |
| May 2023 | 1.047 | +0.047 | — | 0.750 | 0.224 |

- Example stocks (30d): yaz at $52.88 has sd 0.74¢ (0.0140%); iou at $178 has 1.83¢ (0.0103%); ass at $352 has 3.90¢ (0.0111%); tcp at $562 has 6.24¢ (0.0111%); tsb at $1,164 has 12.06¢ (0.0104%). Mean absolute move scales with slope 0.993 (Spearman 0.997). — [R30]
- Tick effects scale with price as predicted. The share of non-zero moves that are exactly 1¢ falls from 0.90 (yaz, $53) to 0.03 (tsb, $1,164). The median absolute non-zero move rises from 1¢ (stocks under ~$200) to 7–8¢ (stocks over $1,100). The zero-change fraction falls with price: yaz 0.59, pts 0.46, wsu 0.40, … tci 0.056. — [R30]
- Some stocks have more zero-change minutes than their price predicts (30d): ths 0.32 at $383, cbd 0.31 at $434, cnc 0.29 at $818, tct 0.26 at $320, wlt 0.23 at $803, against about 0.11–0.18 for peers at similar prices. — [R30]
- The median per-stock sd_pct sits at 0.0113–0.0117% in every month from 2023-08 to 2026-11. — [MONTHLY]

### Inferences
- A proportional (multiplicative) noise model with a common percentage scale across all stocks fits; an additive cents model does not. Cross-stock CV of sd_pct is 4–9% now, against 61% for sd_cents.
- The excess zero-change stocks (ths, cbd, cnc, tct, wlt) suggest stock-specific step-like behaviour, such as periods where the price holds still. This is a per-stock trait, not a shared one.

### Gaps
- Within-stock tests (does one stock's cents sd scale with its own price as the price drifts over time?) were not run here. The cross-sectional evidence is strong, but a within-stock check would confirm the multiplicative model.

## Q4. Lag-1 autocorrelation and Roll noise estimate

### Takeaway
Every stock shows negative lag-1 autocorrelation in m1 returns (median about −0.07), the signature of a bounce around a hidden or smoothed price. The Roll estimate puts the transient noise at a median of about 0.003% of price (≈1.0–1.2¢ at current prices), proportional to price. This bounce explains only about 10–20% of m1 variance for a typical stock; most minute-to-minute variance is permanent random-walk increments. Both components are independent across stocks (Q1).

### Cited Findings
- 30d: ρ1 median −0.073 (min −0.201 cbd, max −0.0003 lag), all 35 negative. ρ2 is small (median about −0.010). Roll σ_e median 1.02¢ (IQR 0.55–1.77¢), 0.0029% of price. — [R30]
- 90d: ρ1 median −0.071 (range −0.177 to −0.027), all negative. Roll σ_e median 1.18¢ (IQR 0.78–1.87¢), 0.0029%. — [R90]
- 365d: ρ1 median −0.069 (range −0.185 to −0.044), all negative. Roll σ_e median 1.22¢ (IQR 0.80–1.93¢), 0.0031%. — [R365]
- May 2023 (old regime): ρ1 median −0.074, Roll σ_e median 2.15¢ (0.0066%). Noise and total volatility were both about 2× larger, while ρ1 stayed similar. — [R2023]
- Monthly median ρ1 across stocks stays between −0.045 and −0.081 in every month from 2021-04 to 2026-11, with no break at the 2023 volatility change. — [MONTHLY]
- Per-stock spread (30d). The share of variance attributable to bounce noise (2σ_e²/var) ranges from 0.0005 (lag) and 0.013 (fhg) to 0.37–0.40 (yaz, cbd), with a median of about 0.13. Roll σ_e in percent: yaz 0.0060%, cbd 0.0052%, ist 0.0051%, wlt 0.0043%, against 0.0010% for fhg and 0.0001% for lag. — [R30]

### Inferences
- The sign of ρ1 is the same for every stock and in every period. That points to one shared generating mechanism: the same "true price + transient fuzz" structure applied stock by stock with independent draws.
- The magnitude varies by stock and by window. lag and fhg showed ρ1 near 0 over 30d, yet over 365d the maximum across all stocks is −0.044, so their near-zero values look like short-term regime effects such as trending periods.
- Because ρ1 is only about −0.07, a filter that removes the Roll noise reduces m1 variance by only about 13% for a typical stock.

### Gaps
- The Roll estimator assumes i.i.d. noise on a martingale. Per-stock trends or mean reversion over minutes (the ρ2 values are mildly negative) could bias σ_e. A complementary analysis is in noise_single_stock.py, written by another agent, which I did not inspect.

## Q5. Is there a common time-of-day / day-of-week volatility pattern?

### Takeaway
No. Normalised |r| profiles by hour-of-day, day-of-week and minute-of-hour are flat within ±1.5%, and the profiles of different stocks are uncorrelated with each other (mean cross-stock profile correlation ≈ 0). The one thing all stocks *do* share is the noise **level** and its change over time: a single step change on 2023-07-12/13 roughly halved m1 volatility for all 35 stocks at once.

### Cited Findings
- Seasonality, with |r| normalised per stock to its mean — [R30], [R90], [R365]:

| window | hour-of-day avg range | mean cross-stock corr of hour profiles | day-of-week range | DOW profile corr | minute-of-hour range | MOH profile corr |
|---|---|---|---|---|---|---|
| 30d | 0.986–1.016 | +0.013 | 0.990–1.010 | −0.017 | 0.979–1.015 | +0.001 |
| 90d | 0.992–1.008 | +0.003 | 0.992–1.004 | −0.017 | 0.990–1.008 | +0.002 |
| 365d | 0.997–1.005 | −0.006 | 0.994–1.003 | +0.001 | 0.994–1.005 | +0.007 |

  The range narrows as the window grows (±1.5% at 30d, ±0.5% at 365d), which is what estimation noise around a flat profile looks like.
- Common regime change. Monthly median sd_pct across stocks was 0.055% in 2021-04 to 06, fell to about 0.024–0.027% from 2021-09 to 2023-06, then 0.016% in 2023-07, and has stayed at 0.0111–0.0117% every month from 2023-08 to 2026-11. Cross-stock CV of sd_pct fell from about 0.15–0.35 before 2023-07 to about 0.06–0.12 after. — [MONTHLY]
- Daily resolution of that change: the median sd_pct was 0.020–0.024% through 2023-07-11, 0.017% on 07-12, then 0.0027% on 07-13 and 0.0040% on 07-14. The number of stocks with daily sd below 0.016% jumped from 0–4 to 35 of 35 on 2023-07-13. After about two weeks of oscillation the level settled at about 0.011% from late July 2023. — [DAILY2023]
- That shared level shift is visible in the change-count statistic. The 90-day stability window starting 2023-04-30, which straddles 2023-07-13, has a variance ratio of 1.53, against 0.99–1.01 in every other window and 0.99 in the May 2023 30-day window. A simultaneous shift in every stock's change probability inflates the variance; the minute-level realisations are still independent. — [R90] stability, [R2023]
- Stability table, ten 90-day windows (start dates). m1 mean ρ −0.0002 to +0.0001. Zero-change fraction 0.19 (2022-11), 0.20 (2023-04), then 0.23–0.25. ρ1 median −0.058 to −0.071. sd_pct median 0.0254, 0.0236, then 0.0113–0.0115. Slope of sd_cents against price 0.95–1.02. Missing data 0.08–3.3%, except 11–20% in the windows from 2024-07 to 2025-05. — [R90]
- Data coverage: from about 2024-05 to 2025-06 the median stock has only about 23k–36k of about 44k minutes per month. Those gaps are shared across stocks (collector outages). Returns across gaps are excluded. — [MONTHLY], [R90]

### Inferences
- The game appears to use one global noise or volatility parameter for all stocks. It was changed (most likely a game update) around 2023-07-12/13, and possibly also around 2021-08. Per-stock draws are independent. Put simply, "shared" applies to the noise *distribution* (proportional scale of about 0.011%/min, bounce of about 0.003%, negative ρ1) and not to the noise *realisations*.
- Models trained on pre-July-2023 m1 data would see roughly twice today's minute volatility. Training data should be split or normalised at 2023-07-13.

### Gaps
- I did not search for or confirm the cause of the 2023-07-13 change (e.g. Torn changelogs). It is an empirical observation only.
- The early-2021 regime (sd about 0.055%) has partial coverage and only some tickers, because the earliest common date across all 35 is 2022-11-29. It was not analysed in depth.

## Q6. Gaps / missing minutes and how they were handled

### Takeaway
Gaps are collector downtime, shared by all stocks. They are small recently (0.29% of minutes in the last 30 days, longest gap 67 min) but large in 2024-05 to 2025-06 (11–20% missing). All returns are formed only between consecutive grid minutes where both prices exist, so no gap creates a fake multi-minute return.

### Cited Findings
- Method: each stock is reindexed onto a complete 1-minute UTC grid (`load_panel`). Returns are taken with `diff()` on the grid, so a missing minute makes both adjacent returns NaN. k-minute returns use grid points every k minutes and are kept only when both endpoints exist. The correlation matrix uses rows where all stocks have a return (129,347 of 129,600 minutes over 90d). — [noise_cross_stock.py](../../tools/noise_cross_stock.py)
- Last 30 days: 43,200 grid minutes, 43,073 present for every stock, 127 missing (0.294%), longest gap 67 min, 43,039 valid consecutive returns per stock. The per-stock figures are identical, so the gaps are synchronised. — [R30]
- May 2023: 1.35% missing, longest gap 142 min. — [R2023]
- Stability windows: 0.08–3.3% missing, except 11.3–19.8% in the windows starting 2024-07-29, 2024-12-28 and 2025-05-28. — [R90]

### Inferences
- Because gaps hit all stocks together, the all-stocks-present filter costs almost no extra data compared with pairwise deletion.

### Gaps
- Some older rows may be backfilled (the `backfill_pending` and `backfill_meta` tables exist; db_ass `gaps_scanned_to` = 1795577340). I did not identify which rows were backfilled or whether backfilled minutes have different noise. All m1 rows have O=H=L=C, so a backfill does not show up in the bar shape.

## Tooling notes (for the report writer)
- Script: `tools/noise_cross_stock.py`, standalone; needs numpy and pandas only. It includes a read-only loader (`load_m1(db_dir, ticker, start_ts=None, end_ts=None)` returns a close Series indexed by UTC datetime; `list_tickers(db_dir)`) and `load_panel` for grid-aligned wide frames. CLI options: `--db-dir` (defaults to `<repo>/db`, then the main checkout's `db/`), `--days`, `--end`, `--tickers`, `--horizons`, `--stability N`, `--jump-z` and `--out` (`.md` writes the full report, `.csv` the per-stock table). A 30-day run over all 35 stocks takes about 5 s, and a 90-day run with `--stability 10` about 1–2 min. — [noise_cross_stock.py](../../tools/noise_cross_stock.py)
