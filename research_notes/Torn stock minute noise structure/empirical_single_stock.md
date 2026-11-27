# Empirical per-stock structure of Torn stock minute noise, and detecting genuine moves

All findings come from my own computations on the local m1 SQLite data (`db/db_<ticker>.db`, opened read-only), not from web sources. Every number can be reproduced with `tools/noise_single_stock.py` in this worktree. Source labels used below:

- **[C30]**: `python tools/noise_single_stock.py characterise --db-dir <db> --tickers yaz pts los iil tmi hrg ass tcp sys cnc fhg tsb tci --days 30`. The window is 2026-10-26 to 2026-11-25: 43,073 rows, 43,039 valid consecutive 1-minute differences per stock. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **[C90]**: the same tickers with `--days 90` (2026-08-27 to 2026-11-25, about 129.3k differences). — [C90](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **[C22]**: older-window check with `--days 90 --end 2022-09-01` (2022-06-03 to 2022-09-01). pts was not listed then. — [C22](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **[EV]**: `evaluate --days 30` on yaz, ass, tcp, fhg and tsb with k=0.5 and h-grid 5..20 (the first-pass settings). ass and fhg were also run with `--kref 0.125 --h 25`, which are now the script defaults. Each run used 200 injections into real data and 30 simulated days. — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **[ADHOC]**: one-off numpy queries on the same DBs: per-quarter sd of 1-minute log changes over the full history, daily sd around July 2023, hour-of-day and weekday sd, zero-run conditional probabilities, and relative-change histograms. — [ADHOC](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/db)

Units: bp means a basis point of price (0.01 %). 1 cent equals 1e4/(price×100) bp, for example 0.284 bp for ass at 351.6 and 1.89 bp for yaz at 52.85. Notation: σe is the transient noise sd, σu is the per-minute sd of the hidden random-walk price, q = σu²/σe², and K is the steady-state Kalman gain.

## Q1. Distribution of 1-minute cent changes: bounded, uniform, triangular, Gaussian or heavy-tailed? How many zero-change minutes?

### Takeaway
The 1-minute change is unbounded and heavy-tailed: Student-t or Laplace fits beat a Gaussian, and a bounded triangular or uniform fit is far worse. Measured in bp the spread is nearly identical across stocks, about 1.0–1.4 bp per minute. The distribution also has two structural oddities. Zero-change minutes are far more common than a smooth distribution allows, and they cluster in time. Expensive stocks show a stock-specific "comb", where some cent sizes are preferred over others.

### Cited Findings
- In 30-day recent windows, the sd of the 1-minute change is 0.74 c for yaz (price 52.85), 3.90 c for ass (351.6), 7.14 c for sys (656.6), 11.47 c for fhg (894.6) and 12.06 c for tsb (1162). In bp this is 1.40, 1.11, 1.09, 1.28 and 1.04, and all 13 stocks fall between 1.01 and 1.40 bp. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- The largest single-minute change grows with sample size and price, so there is no hard ±k bound. In 30 days the maximum |Δ| was 4 c for yaz, 23 c for ass and 93–99 c for fhg. The 99.9th percentile of |Δ| was 3 c for yaz, 17 c for ass, 77 c for fhg and 52 c for tsb. — [ADHOC/C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Distribution fits use mean log-likelihood per observation, with each continuous distribution discretised to whole cents (higher is better):
  - ass: normal −2.781, Laplace −2.749, Student-t −2.751 (df 4.8), triangular on the maximum support −3.298.
  - fhg: normal −3.874, Laplace −3.661, t −3.654 (df 2.1).
  - cnc: normal −3.668, Laplace −3.490, t −3.522 (df 2.1).
  - yaz: normal −1.125, Laplace −1.113, t −1.107 (df 6.5).

  — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Excess kurtosis of Δ over 30 days is 1.0–1.7 for most stocks, 2.2 for tcp, 3.4 for sys, 5.6 for cnc and 9.1 for fhg. After dividing by a 60-minute EWMA volatility it falls but stays positive: ass 1.55, fhg 6.9, cnc 4.9, tci 0.89. Over 90 days, tci reaches 14.8 raw and 6.7 vol-normalised, and ass reaches 5.8 and 3.7. — [C30, C90](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Fraction of zero-change minutes (30 days): yaz 0.589, pts 0.465, los 0.398, iil 0.322, tmi 0.242, hrg 0.194, ass 0.157, tcp 0.176, sys 0.159, cnc 0.287, fhg 0.162, tsb 0.136, tci 0.056. A smooth distribution with the same sd would put only about 0.04–0.10 at zero for the expensive stocks (for example about 0.04 for sd 9.5 c). — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Zeros cluster in time. P(zero | previous minute zero) is 0.55 for cnc against an unconditional 0.29, 0.42 against 0.23 for wlt, 0.23 against 0.16 for fhg, and 0.19 against 0.16 for ass. The change after a zero minute is not larger than usual: for cnc its variance is 83.6 c² after a zero against 92.3 c² otherwise, and for ass 13.9 against 15.5. So zeros are not missed samples that catch up in the next minute. — [ADHOC](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/db); [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Histograms of 1-minute changes in cents (30 days):
  - ass (smooth, unimodal): −3:2876 −2:3864 −1:4751 0:6754 1:4767 2:3875 3:2913.
  - yaz: −2:813 −1:7955 0:25360 1:7957 2:830.
  - fhg (comb): −4:1312 −3:2515 −2:2291 −1:1015 0:6986 1:1048 2:2363 3:2606 4:1368 5:1658.
  - tsb (comb): −3:996 −2:1274 −1:637 0:5842 1:636 2:1361 3:1001 4:1559 5:1860.
  - cnc: 0:12357, then a flat ~1,070–1,290 per value for |Δ| = 1..5 c, then peaks at ±6 (1816/1847) and ±7 (2180/2283), and a drop to ~650 at ±8.

  — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- The preferred step sizes are not a common percentage: cnc peaks near 0.75–0.85 bp, fhg near 0.22–0.34 bp, and tsb and tci have several peaks. A scan for a common multiplicative unit (the phase-concentration test in the ADHOC query) only recovered 1 cent divided by price, which is just the cent grid. — [ADHOC](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/db)

### Inferences
- A model of "difference of two uniform jitters" (triangular Δ) is rejected. What dominates Δ is the hidden price's own per-minute move, which is heavy-tailed and close to uniform across stocks in percentage terms. The transient jitter is a small add-on (see Q2).
- Applying an EWMA volatility only partly removes the fat tails. That fits a mixture of volatility clustering and genuine one-minute jumps (see the jump counts in Q6).
- The hidden-price generator looks like a mixture: an atom at "no change" whose regimes persist for several minutes, plus a non-Gaussian and sometimes multimodal step distribution in whole cents. Any Gaussian noise model will under-predict both zeros and large moves.

### Gaps
- I could not identify the mechanism behind the comb. The preferred sizes differ by stock and are neither a fixed bp unit nor a fixed cent unit. Candidates such as a hidden price with more decimals, a fixed share count, or a discrete step menu were not tested to a conclusion.

## Q2. Memory: autocorrelation, variance signature, and the noise vs diffusion split

### Takeaway
At one minute, returns show a small negative lag-1 autocorrelation (−0.02 to −0.10, or −0.18 for yaz) that dies out within 2–3 lags. The variance-signature plot Var(k)/k falls over roughly 10–30 minutes and then plateaus. That is the textbook pattern of a random walk plus a small independent noise. The transient noise is small: σe is about 0.1–0.4 bp, roughly 1–3 c on expensive stocks. The hidden random walk carries σu of about 1.0–1.3 bp per minute. So q = σu²/σe² is about 8–20 (as high as about 150 in some windows), and the noise is only about 5–15 % of one-minute variance.

### Cited Findings
- ACF of 1-minute log changes at lags 1, 2, 3, 30 (30 days): yaz −0.184/−0.009/+0.001/0.000, ass −0.080/−0.021/−0.007/+0.002, tsb −0.053/0.000/−0.004/−0.001, fhg −0.006/−0.009/−0.004/−0.002. Lag 1 for the other stocks: pts −0.099, los −0.087, iil −0.082, tmi −0.057, hrg −0.086, tcp −0.094, sys −0.023, cnc −0.078, tci −0.043. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Signature Var(k)/k in bp² for k = 1, 5, 30, 240, 1440 (90 days):

  | Stock | k=1 | k=5 | k=30 | k=240 | k=1440 |
  |---|---|---|---|---|---|
  | yaz | 1.93 | 1.33 | 1.16 | 1.06 | 0.89 |
  | ass | 1.57 | 1.32 | 1.19 | 1.06 | 1.07 |
  | fhg | 1.46 | 1.23 | 1.20 | 1.19 | 1.05 |
  | tsb | 1.13 | 1.01 | 0.92 | 0.95 | 0.83 |
  | sys | 1.16 | 1.09 | 1.04 | 0.98 | 1.14 |
  | tci | 1.33 | 1.21 | 1.13 | 1.06 | 1.25 |

  — [C90](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Noise and diffusion estimates for ass over 30 days (bp²):

  | Estimator | σe² | σu² |
  |---|---|---|
  | Signature intercept (k = 1..30) | 0.203 | 0.953 |
  | MA(1) moment (−γ1) | 0.098 | 1.034 |
  | Kalman MLE | 0.103 | 1.024 |
  | AR(1)-noise signature fit | 0.204 (φ = 0.32) | — |

  The rounding-only floor is 0.0067. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Per-stock Kalman MLE over 30 days. Each entry lists σe in bp (in cents), then σu in bp/min (in cents), then q and K:
  - yaz: 0.61 (0.32 c); 1.11 (0.59 c); q 3.4, K 0.81.
  - pts: 0.38 (0.31 c); 1.09; q 8.2, K 0.90.
  - iil: 0.33 (0.44 c); 1.05; q 10.1, K 0.92.
  - tmi: 0.25 (0.57 c); 0.97; q 14.6, K 0.94.
  - hrg: 0.33 (0.89 c); 1.02; q 9.3, K 0.91.
  - ass: 0.32 (1.13 c); 1.01 (3.56 c); q 9.9, K 0.92.
  - tcp: 0.34 (1.93 c); 1.00 (5.62 c); q 8.5, K 0.90.
  - sys: 0.16 (1.08 c); 1.06; q 42, K 0.98.
  - cnc: 0.33 (2.70 c); 1.06; q 10.3, K 0.92.
  - fhg: 0.10 (0.93 c); 1.27 (11.4 c); q 150, K 0.993.
  - tsb: 0.24 (2.76 c); 0.98 (11.4 c); q 17.0, K 0.95.
  - tci: 0.21 (2.42 c); 0.96 (11.1 c); q 21, K 0.96.

  — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- The 90-day values are similar: ass σe 0.38 bp, q 7.4, K 0.89; fhg 0.15 bp, q 57, K 0.98; tsb 0.25 bp, q 16, K 0.94; sys q 35. A 7-day fhg window gave σe² = 0.077 bp² against 0.011 over 30 days, so the noise level differs from window to window. — [C90](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py); `filter --days 7` run
- For yaz the estimated noise is mostly cent rounding. The MLE gives σe² = 0.367 bp² against a rounding-only 0.298 bp², leaving 0.26 bp (0.14 c) of genuine jitter. For ass the rounding floor is only 0.0067 bp², so its jitter of 0.31 bp (1.09 c) is real. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Volatility clusters. The ACF of |Δ| at lag 1 is 0.08–0.13, and for ass it is 0.107/0.079/0.053/0.035/0.011 at lags 1/5/30/60/240. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)

### Inferences
- The MA(1) estimate is about half the signature intercept for ass, and the ACF decays over 2–3 lags instead of cutting off after lag 1. So the transient component has a memory of roughly 1–3 minutes, with AR(1) φ of about 0.3–0.6 (unstable across stocks). It is not strictly i.i.d. Either way it is small, and the signature plateaus by about k = 20–30.
- Past about 30 minutes the signature is flat to within about ±10 %, so the hidden price behaves like a random walk at 0.5–4 hour scales. At 1440 minutes the ratio drifts down for some stocks (yaz, tsb, fhg: mild mean reversion over a day) and up for others (sys, tci, pts: mild trending). With only 30–90 days of data these deviations are weakly determined.

### Gaps
- The model with i.i.d. noise and the model with short-memory noise cannot be separated cleanly from the signature alone. Negatively autocorrelated hidden increments would produce the same curve.

## Q3. Is the noise mean-reverting around a hidden level? Rolling-median residuals

### Takeaway
Residuals from a centred rolling median are not bounded and not uniform. They grow roughly like √(window) because the hidden price keeps diffusing inside the window, and their kurtosis is above 0. No window shows a hard noise band. The only "bounded" component is the 0.1–0.4 bp jitter, which sits well below the residual spread for any window of 15 minutes or more.

### Cited Findings
- Residual of the observed log price minus a centred median of width w. Values are sd / 99th percentile of |residual| / maximum, in bp, with excess kurtosis in brackets (30 days):
  - ass: w5 0.65/2.27/5.3 (4.3); w15 1.06/3.41/9.7 (2.7); w31 1.46/4.55/11.4 (2.5); w61 2.00/6.23/14.2 (2.3).
  - yaz: w15 1.34/3.80/7.6 (1.7); w61 2.33/7.55/13.4 (1.8).
  - tsb: w15 1.01/3.20/8.4 (2.8); w61 1.97/6.05/13.1 (1.8).
  - fhg: w15 1.15/4.27/12.2 (8.3); w61 2.42/8.48/15.3 (3.3).
  - cnc: w15 1.07/3.74/10.0 (5.3).

  — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- From w15 to w61 the residual sd rises by a factor of about 1.9–2.1, close to √(61/15) = 2.0. That is the scaling expected from random-walk curvature, not from fixed noise. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- In the 2022 window residuals were about 3× larger: yaz w15 sd 3.04 bp, w61 sd 5.69 bp. — [C22](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)

### Inferences
- A rolling median of 15–61 minutes is a poor latent-price estimate here, because it lags and smooths genuine diffusion. The Kalman K of about 0.9 shows that the best estimate of the hidden price is close to the latest print.

### Gaps
- I did not test whether the jitter itself, once separated from diffusion, has a hard bound such as uniform ±a. It is too small relative to diffusion to measure directly with 2-decimal prices on cheap stocks.

## Q4. Does noise magnitude scale with price level?

### Takeaway
Yes, proportionally. Across stocks, the one-minute sd in bp is about constant (1.0–1.4 bp) for prices from 52 to 1162, so in cents it is roughly 0.011 % × price. Within a stock over time, volatility changes because of a game-wide regime shift rather than because of price level: per-minute sd fell by about half around 2023-07-13 for every stock checked.

### Cited Findings
- In cents the 30-day sd grows almost linearly with price: yaz 0.74 c at 52.85, iil 1.54 c at 134, ass 3.90 c at 352, tcp 6.24 c at 562, cnc 9.48 c at 818, tsb 12.06 c at 1162, tci 11.59 c at 1150. In bp the same stocks are 1.40, 1.14, 1.11, 1.11, 1.16, 1.04 and 1.01. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Jitter σe in cents also grows with price, while in bp it stays at 0.1–0.4. The MLE σe excluding rounding is 0.14 c for yaz, 0.25 c for iil, 1.09 c for ass, 1.93 c for tcp, 2.7 c for cnc and 2.76 c for tsb. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Quarterly sd of 1-minute log changes in bp. In 2022 it was 2.1–3.3 for ass, fhg, yaz, tsb and sys. In 2023Q2 it was ass 4.54 and fhg 3.44. From 2023Q3 to 2026Q4 it was 1.04–1.45 for all five stocks. Daily ass sd ran 1.6–2.3 bp in late June to early July 2023, dropped to 0.20 on 2023-07-13 and 0.64 on 07-14, then settled at about 1.1–1.3 from 07-17. — [ADHOC](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/db)
- 2022 window parameters for comparison:
  - σu in bp/min: yaz 2.99, iil 2.86, ass 1.82, sys 3.47, tsb 2.69, against about 1.0–1.1 in 2026.
  - σe in bp: yaz 0.92, ass 0.49, tsb 0.70, tci 0.71.
  - q stayed in the same 9–20 range for most stocks (ass 13.7, tsb 14.7, tci 11.9), with outliers iil 88 and cnc 97.

  — [C22](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- There is no intraday seasonality. For ass over the last 90 days, the sd by UTC hour ranges 1.21–1.34 bp and by weekday 1.18–1.33 bp. — [ADHOC](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/db)

### Inferences
- Thresholds should be set in bp, or as a percentage of price, not in cents. Under the current regime one universal set of bp thresholds works for all stocks. The noise-to-diffusion ratio q stayed similar through the 2023 volatility change, so thresholds in σ units carry across regimes, while thresholds in absolute bp have to be re-fitted after a regime change.

### Gaps
- No public source was checked for the cause of the 2023-07-13 change (presumably a game update), and I did not search for one. The within-window log-log regression of daily sd on price was not informative: price ranges within 30–90 days are only a few percent, so the script now reports it only when the price range exceeds 20 %.

## Q5. Latent-price filter: Kalman local-level vs EWMA vs rolling median

### Takeaway
The MLE local-level Kalman filter gives a steady-state gain K of about 0.90–0.96 for most stocks under the current regime: 0.81 for yaz, where rounding dominates, and 0.98–0.99 for sys and fhg. The filtered price therefore hugs the last print and removes only about 1–3 c of jitter on expensive stocks. An EWMA with α = K is equivalent once at steady state. A rolling median is clearly worse, since it adds lag on the order of half the window under random-walk dynamics.

### Cited Findings
- The MLE values of q and K per stock are listed in Q2. Under pure noise, the filtered level's deviation from the true constant level has sd 0.294 bp for ass (0.92 σe), with a maximum of 4.0 σe over 30 simulated days. For tsb it is 0.224 bp (max 4.07 σe), for tcp 0.310 bp (max 3.88 σe), and for fhg 0.103 bp (max 4.27 σe). — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- The `filter` subcommand writes, per minute: the price, the Kalman level and its sd in cents, an EWMA with α = K, a trailing 15-minute median, the standardised innovation z, and the CUSUM, level and jump flags. For ass over 7 days the Kalman sd is about 0.96 c. — `filter --tickers ass fhg yaz --days 7` run, [script](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- The 15–61 minute rolling-median residual sd (1.0–2.4 bp, Q3) is 3–8× the jitter σe (0.1–0.4 bp). In other words, the median removes genuine movement along with the noise. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)

### Inferences
- In practice, filtering adds little at one-minute resolution. Its main value is a calibrated σe, which gives the "beyond noise" bar, and standardised innovations to feed detectors. Fat tails and volatility clustering mean the Gaussian MLE is a working approximation. A robust or Student-t filter, or a time-varying σu, would be the natural next step.

### Gaps
- No t-distributed or regime-switching filter was fitted. The MLE uses only the last 60,000 grid minutes of each window, to bound run time.

## Q6. Genuine move detection: rules, false-alarm rates, detection delay and recommended thresholds

### Takeaway
"Genuine vs noise" separates into three practical rules, all expressed in σ units, which carry across stocks.

1. **Level rule: beyond noise.** The filtered price leaving its anchor by more than 5σe (about 1.2–1.9 bp, for example 4.9 c on ass, 12–14 c on tsb and fhg, 1.5 c on yaz) gave 0 false alarms in 30 days of simulated pure noise for every stock tested. 4σe gave 0–4.2 per day. On real data this fires about 100–700 times a day, because the hidden price really does move by that much every few minutes. Nearly every move larger than about 5σe is genuine.
2. **Jump rule.** A Kalman innovation with |z| > 6 is about 0 per day under the Gaussian model. Real data shows 0.03 per day on ass and 2.7 per day on fhg, so these are genuine one-minute jumps.
3. **Trend rule.** A two-sided CUSUM on standardised innovations with k = 0.125 and h = 25 gives 0.13 false alarms per day under the zero-drift fitted model and 0.23–0.60 per day on real data. It detects a drift of 0.5σu per minute (about 0.3 % per hour) with a median delay of about 56 minutes, and 0.25σu per minute (about 0.15 % per hour) in about 143–160 minutes, with 82–84 % detected within 4 hours.

### Cited Findings
- **Pure-noise simulation** (constant price, fitted σe, cent rounding; level rule, false alarms per day):
  - ass: band 3σe 27.9, band 4σe 0, band 5σe 0.
  - fhg: 3σe 75.6, 4σe 2.13, 5σe 0.
  - tsb: 3σe 36.5, 4σe 4.2, 5σe 0.
  - tcp: 3σe 17.5, 4σe 0.4, 5σe 0.
  - yaz: 0 at all bands, because rounding to cents absorbs the jitter.
  - CUSUM: 0 per day at every h for all stocks.

  — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **Level rule on real data**, alarms per day at 5σe / 8σe: ass 259/129, tcp 227/113, tsb 369/201, fhg 741/503, yaz 117/55. — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **CUSUM with k = 0.5**, alarms per day under the zero-drift random-walk-plus-noise simulation: h = 5: 2.4–2.6; h = 8: 0.07–0.13; h = 10: 0. On real data with h = 10 (plain / volatility-adaptive, 120-minute half-life): ass 0.50/0.40, tcp 0.57/0.30, tsb 0.37/0.30, fhg 1.34/0.80, yaz 0.57/0.47. — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **CUSUM with k = 0.125**: the zero-drift simulation gives, by h, 10: 6.3, 15: 1.27, 20: 0.30, 25: 0.13, 30: 0.03, 40: 0 per day. On real data at h = 25: ass 0.23 plain / 0.27 adaptive, fhg 0.60 / 0.33. At h = 30: ass 0.17 / 0.13, fhg 0.30 / 0.07. — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **Detection delay for trends injected into real data** (200 random start points; horizon 240 minutes; values are median delay and the share detected within the horizon):
  - k = 0.5, h = 10, same pattern on ass, tcp, tsb, fhg and yaz:
    - 1σu/min: 17–18 minutes, 100 %.
    - 0.5σu/min: 102–128 minutes, 76–89 %.
    - 0.25σu/min: not detected (14–20 %, against a 2–6 % baseline).
    - 0.1σu/min: 9 % against a 6 % baseline.
  - k = 0.125, h = 25:
    - ass: 1σu 25 minutes; 0.5σu 57 minutes (100 %); 0.25σu 143 minutes (84 %); 0.1σu 14 % against a 4 % baseline.
    - fhg: 26, 56 and 160 minutes (82 %).

  — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **Steps injected into real data:**
  - Level rule (5σe or 6σe): a step of at least 6σe is flagged within a median of 0–1 minute. Without injection, a same-direction alarm happens anyway within 2–22 minutes (median 9 for ass, 2 for fhg, 22 for yaz).
  - Jump rule (|z| > 6): ass steps of 6.3σu (22.6 c) are caught 36 % of the time and 9.5σu (33.9 c) 99 % of the time, against a 1 % baseline.
  - CUSUM barely responds to single steps (detection 2–11 %).

  — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **Jump rule frequency** (|z| > jz, events per day, Gaussian simulation | real data):
  - ass: jz 4: 0.13 | 3.0; jz 5: 0 | 0.23; jz 6: 0 | 0.03; jz 8: 0 | 0.
  - fhg: jz 4: 0.10 | 14.0; jz 5: 0 | 6.3; jz 6: 0 | 2.7; jz 8: 0 | 0.17.

  — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- **Follow-through after CUSUM alarms** (k = 0.5, h = 10; move over the next 60 minutes in the alarm direction):
  - ass: +5.4 bp, P(>0) = 0.64 (n = 14).
  - tcp: +1.2 bp, 0.59 (n = 17).
  - tsb: +2.0 bp, 0.55 (n = 11).
  - fhg: +0.5 bp, 0.50 (n = 40).
  - yaz: +4.7 bp, 0.53 (n = 17).

  The random-walk null is 0 bp and 0.5. — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)

### Inferences
- **Recommended universal settings in σ units:** level band 5σe as the noise bound, jump |z| > 6, and trend CUSUM with k = 0.125 and h = 25–30. Use volatility-adaptive scaling (half-life about 120 minutes) on high-kurtosis stocks such as fhg, where it cut real-data CUSUM alarms by about 45 % (0.60 to 0.33 per day). For drifts of 1σu per minute or more, k = 0.5 with h = 10 is faster (about 17 minutes).
- In the current regime 1σu is about 1 bp per minute, so the CUSUM settings translate to "a trend of about 0.15–0.3 % per hour is confirmed within 1–2.5 hours". Real data has 2–5× the model's false-alarm rate, which reflects volatility clustering and genuine trend episodes.
- Follow-through after an alarm is weak and based on small samples, so CUSUM alarms show at best mild momentum. That fits a hidden price that is close to a pure random walk.

### Gaps
- The CUSUM false-alarm rates on real data cannot be split into "false" and "genuine trend", because there is no ground truth.
- Detection delays were measured on 30-day windows of five stocks only, and thresholds were not re-checked in the 2022 high-volatility regime.

## Q7. Is there visible discrete regime structure in the hidden price (steps vs smooth drift)?

### Takeaway
Three kinds of discrete structure are visible. There is one large game-wide volatility regime change around 2023-07-13. There are persistent "quiet" stretches, where zero-change minutes cluster. And there are occasional one-minute jumps, at rates that vary strongly by stock. Between those, the hidden price is a near-random walk at 30-minute to 4-hour scales, with no evidence of frequent discrete level steps.

### Cited Findings
- Volatility regime: the per-minute sd was about 2–3.3 bp in 2021–2023Q2 and about 1.04–1.45 bp from 2023Q3 to 2026Q4 for ass, fhg, yaz, tsb and sys, with the drop on about 2023-07-13. — [ADHOC](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/db)
- Zero clustering: P(0 | previous 0) is above the unconditional P(0) for every stock checked, for example cnc 0.55 against 0.29, and pts 0.49 against 0.46 over 30 days. — [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py); [ADHOC](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/db)
- Jumps: |z| > 6 innovations occur 0.03 per day on ass and 2.7 per day on fhg, against about 0 under the Gaussian model. fhg's raw excess kurtosis over 30 days is 9.1. — [EV](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py); [C30](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Signature flatness: Var(k)/k varies by less than about 10 % between k = 30 and k = 240 for all 13 stocks over 90 days. — [C90](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/.claude/worktrees/m1-noise-tools/tools/noise_single_stock.py)
- Data quality: OHLC values are flat (open = high = low = close) in 100 % of sampled rows from 2021 to 2025 for ass, so each row is one sampled price. The 2024 and 2025 windows have large gaps, about 8,500 missing-minute breaks in 30 days. — [ADHOC](file:///C:/Users/Jordach/Desktop/Dev/TornStonksLive/db)

### Inferences
- A practical model of the latent price under the current regime:
  - a multiplicative random walk with σu of about 1 bp per minute, heavy-tailed, with clustered volatility and occasional jumps;
  - an intermittent "no-move" state;
  - plus 0.1–0.4 bp of short-memory jitter and cent rounding.
- A hidden-Markov or regime-switching model (quiet / normal / jump) is the natural extension and was not fitted.

### Gaps
- No explicit change-point segmentation was run, for example to estimate the distribution of trend-segment lengths or to test for hidden "target price" steps over days or weeks. The long-horizon signature deviations (k = 1440 and above) are too noisy with 90 days of data to decide between mean reversion and trending.
