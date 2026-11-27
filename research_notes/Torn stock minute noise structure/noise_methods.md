# Statistical methods for separating per-minute additive noise from genuine price changes

Context: Torn stock prices are sampled every minute, rounded to $0.01, and may be jittered each minute around a hidden "true" price. Notation used throughout:
- `p_t` observed price at minute t, `x_t` latent true price, `e_t` noise: `p_t = x_t + e_t`
- `r_t = p_t - p_{t-1}` (absolute, cents) or `log p_t - log p_{t-1}` (proportional)
- `sigma_u^2` = variance of true-price increments per minute, `omega^2` = noise variance

Source caveat: the fetch tool could not extract text from several primary PDFs (the NBER TSRV paper, Hansen-Lunde, and the jump-test survey PDF). Formulas below come from HTML/arXiv renderings and secondary summaries, as cited. Standard textbook derivations that I could not tie to a fetched page are placed under "Inferences" and labelled as derivations.

## (a) Microstructure noise models and noise-variance estimation

### Takeaway
Assume `p = x + e`, with i.i.d. noise independent of a random-walk `x`. Then returns follow an MA(1): `Var(r) = sigma_u^2 + 2 omega^2` and `Cov(r_t, r_{t-1}) = -omega^2`. So `omega^2_hat = -autocov_1(r)` (Roll), and the lag-1 autocorrelation shows directly how much of the 1-minute return variance is noise (pure noise gives rho_1 = -0.5). Three other estimates give consistent cross-checks: the variogram/signature-plot intercept, TSRV, and RV/(2n).

### Cited Findings
- Roll (1984), "A Simple Implicit Measure of the Effective Bid-Ask Spread in an Efficient Market", J. Finance 39, 1127-1139. The spread is estimated as `2 * sqrt(-Cov(dp_t, dp_{t-1}))`. The key assumption is that efficient-price innovations are serially uncorrelated, so the transitory component is the only source of serial covariance — [Roll 1984 PDF](https://www.bauer.uh.edu/rsusmel/phd/roll1984.pdf); [Odegaard lecture notes](https://ba-odegaard.no/teach/notes/liquidity_estimators/roll_spread_estimator/roll_lectures.pdf)
- Practical failure mode: in real data the sample first-order autocovariance is often positive, which leaves the Roll estimator undefined (the square root of a negative number) — [Odegaard lecture notes](https://ba-odegaard.no/teach/notes/liquidity_estimators/roll_spread_estimator/roll_lectures.pdf)
- The additive noise model used in the realized-volatility literature is `Y_t = X_t + eps_t`, with eps i.i.d., mean 0, finite 4th moment, and independent of X — [Zhang 2006 multi-scale paper, arXiv math/0411397](https://ar5iv.labs.arxiv.org/html/math/0411397)
- Decomposition of lag-K realized variance: `[Y,Y]^(n,K) = [X,X]^(n,K) + (2/K) sum eps_i^2 + U + V`, with cross term `U = -(2/K) sum eps_i eps_{i-K}`. At K=1 the noise contributes about `2 n E[eps^2]`, so as n grows, RV computed at the highest frequency is dominated by noise — [arXiv math/0411397](https://ar5iv.labs.arxiv.org/html/math/0411397)
- Two-scales realized variance (TSRV; Zhang, Mykland & Ait-Sahalia 2005): `TSRV = RV_avg^(K) - (n_bar/n) * RV_all`, where
  - `RV_avg^(K)` is the average of the RVs on K offset sparse subgrids;
  - `RV_all` uses every observation;
  - `n_bar = n/K` in the original paper, or `(n-K+1)/K` in later versions;
  - an optional finite-sample factor `(1 - n_bar/n)^-1` can be applied.

  The averaged slow-scale estimator has bias `2 n_bar E[eps^2]`, which the scaled RV_all removes — [arXiv 0906.1444](https://arxiv.org/pdf/0906.1444); [bookdown financial econometrics](https://bookdown.org/jarneric/financial_econometrics/5.1-realized-measures-of-volatility.html); [NBER w10111](https://www.nber.org/papers/w10111.pdf)
- An alternative published form writes TSRV as `[Y,Y]^(n,K) - 2((n-K+1)/(nK)) [Y,Y]^(n,1)`, with `[Y,Y]^(n,K) = (1/K) sum (Y_i - Y_{i-K})^2` (lag-K differences). The factor 2 comes from that lag-K normalisation — [arXiv math/0411397](https://ar5iv.labs.arxiv.org/html/math/0411397)
- TSRV is unbiased, consistent and asymptotically normal, but converges only at rate n^(-1/6). The multi-scale MSRV estimator (Zhang 2006) reaches n^(-1/4) and stays consistent when the noise is dependent — [CMU tech report](https://www.stat.cmu.edu/tr/tr786/tr786.pdf); [arXiv math/0411397](https://ar5iv.labs.arxiv.org/html/math/0411397)
- Ait-Sahalia, Mykland & Zhang show that the two-scales approach still works when the noise has time-series dependence — [Bundesbank DP](https://bundesbank.de/resource/blob/703260/33aac44ae631de6e7a1a2b3842180180/472B63F073F071307366337C94F8C870/2005-09-12-dkp-30-data.pdf)
- Hansen & Lunde (2006), "Realized Variance and Market Microstructure Noise" (JBES):
  - studies bias corrections of RV under noise;
  - the bias is "particularly evident from volatility signature plots" (Andersen, Bollerslev, Diebold & Labys);
  - a simple kernel-based estimator dominates RV;
  - empirically, noise is negatively correlated with efficient returns, so the independent-noise assumption fails for real stocks.

  [Hansen-Lunde PDF](https://web-docs.stern.nyu.edu/salomon/docs/Hansen-Lunde.pdf); [Fed IFDP](https://www.federalreserve.gov/Pubs/Ifdp/2007/905/ifdp905r.pdf). These points come from search summaries because the PDF text could not be extracted.
- Realized kernels (Barndorff-Nielsen, Hansen, Lunde & Shephard) are the practical reference for kernel-based, noise-robust variance estimation — [Realised kernels in practice, Econometrics Journal](https://scholar.harvard.edu/sites/scholar.harvard.edu/files/RKpractice-ECTJ.pdf)
- Signature plots, plus the ACF/PACF of returns, are the standard graphical diagnostics for the noise assumptions — [IFDP 905](https://webarchive.library.unt.edu/web/20090513183858/http:/www.federalreserve.gov/pubs/ifdp/2007/905/ifdp905.pdf)

### Inferences
These are standard MA(1) derivations, not quoted from a fetched page, together with how to apply them to Torn 1-minute data.
- **MA(1) moments.** Let `x_t = x_{t-1} + u_t` with `u ~ (0, sigma_u^2)`, and let `e` be i.i.d. `(0, omega^2)`, independent of u. Then:
  - `gamma_0 = Var(r) = sigma_u^2 + 2 omega^2`
  - `gamma_1 = -omega^2`
  - `gamma_k = 0` for k >= 2
  - `rho_1 = -omega^2 / (sigma_u^2 + 2 omega^2)`, which lies in `[-0.5, 0]`

  The estimators follow: `omega^2_hat = -gamma_1_hat`, `sigma_u^2_hat = gamma_0_hat + 2 gamma_1_hat`, and noise-to-signal ratio `lambda = omega^2 / sigma_u^2`.

  How to read the result:
  - rho_1 near -0.5 means 1-minute moves are almost all jitter.
  - rho_1 near 0 means there is no detectable i.i.d. noise.
  - Significant gamma_2 or gamma_3 means the noise is autocorrelated (for example, jitter that persists for several minutes). The i.i.d. model is then invalid: fit an MA(q) and use MSRV or realized kernels instead.
- **Fitting it as a model.** There are two routes:
  - `statsmodels.tsa.arima.model.ARIMA(p, order=(0,1,1))` estimates theta. Under the standard random-walk-plus-noise mapping, `theta = -(1 - K)`, where K is the steady-state Kalman gain from (d), and `omega^2 = -theta * sigma_a^2`, where sigma_a^2 is the innovation variance.
  - `statsmodels.tsa.statespace.structural.UnobservedComponents(p, level='local level')` estimates `sigma2.irregular` (= omega^2) and `sigma2.level` (= sigma_u^2) directly by maximum likelihood.

  Both routes should agree with the moment estimator.
- **Signature plot (variogram) — the recommended estimator.** For a lag of h minutes, compute `V(h) = mean((p_t - p_{t-h})^2)` (overlapping differences are fine). Under the model, `E[(p_t - p_{t-h})^2] = h sigma_u^2 + 2 omega^2`. Plotted against h this is a straight line with slope sigma_u^2 and intercept 2 omega^2, so regressing V(h) on h = 1..60 gives a robust joint estimate of both parameters. How to read the shape:
  - Concave at small h: autocorrelated noise, or mean reversion in the true price.
  - Still bending at large h: the true price itself may be mean-reverting (possible for Torn stocks).

  Code: `v = [np.mean((p[h:]-p[:-h])**2) for h in H]; slope, icpt = np.polyfit(H, v, 1); omega2 = icpt/2`.
- **RV/(2n).** Over a window of n minutes, `omega^2 ≈ RV_1min/(2n)` is valid only when `n omega^2` is much larger than the total true variance. The variogram intercept is strictly better because it removes the signal component.
- **Pre-averaging** (Jacod, Podolskij & Vetter). Average prices over blocks of k_n ~ c sqrt(n) observations before differencing; this shrinks the noise variance by about 1/k_n. In practice here, a centred rolling mean of width w reduces the sd of i.i.d. noise by sqrt(w) but smears genuine steps over w minutes. I did not fetch a primary pre-averaging source (see Gaps).
- **Bounded uniform jitter.** Roll, the variogram intercept and TSRV need only finite variance and independence, so they work unchanged for uniform jitter.
  - Continuous `U(-k, k)`: `omega^2 = k^2/3`, so `k ≈ sqrt(3 omega^2)`.
  - Discrete uniform on integer cents `{-k..k}`: `omega^2 = ((2k+1)^2 - 1)/12 = k(k+1)/3` cents^2, so solve `k(k+1) = 3 omega^2` for k.
- **Absolute vs proportional noise.** Estimate omega^2 per stock and per price regime (for example per day, using `-gamma_1` or the variogram intercept). Then regress `log omega_hat` on `log price_level`:
  - slope ≈ 0 means fixed-cents jitter;
  - slope ≈ 1 means percentage jitter (noise sd proportional to price).

  Run this across stocks with very different price levels. Torn stocks span roughly cents to hundreds of dollars, which gives far more leverage than within-stock variation. An equivalent check is to compare the dispersion of `omega_hat/price` with the dispersion of `omega_hat` across stocks: whichever is more constant indicates the noise type.

### Gaps
- I could not extract the Hansen-Lunde PDF text, so their exact `RV_AC1` estimator and their empirical noise-to-signal ratios for equities are not quoted.
- The optimal K for TSRV (often quoted as `K* ~ c n^(2/3)`) is not confirmed from a fetched page. The fetched text confirmed only the n^(-1/6) rate.
- No primary pre-averaging source was fetched, so the weight function (g(x) = min(x, 1-x)) and its constants are unverified.

## (b) Shared vs independent noise across series

### Takeaway
There are two distinguishable patterns:
- **Shared noise** (one jitter draw, or a common clock artefact, hits all stocks each minute): 1-minute cross-correlations are noticeably non-zero at lag 0, and the lag-1 cross-autocovariance is negative.
- **Independent noise** (separate jitter per stock): cross-correlation at the 1-minute scale is smaller than at coarser scales, because independent noise dilutes the common signal. This is a synthetic Epps effect.

### Cited Findings
- Epps (1979) observed that measured correlations between stock returns decrease as the sampling frequency rises — [arXiv 2005.10568](https://arxiv.org/html/2005.10568v4)
- Asynchronous trading and discrete price increments cause much of that decline. The Hayashi-Yoshida (2005) cumulative covariance corrects for asynchrony, and in simulation the Epps effect at very high frequency is dominated by asynchronous sampling — [arXiv 1011.1011](https://ar5iv.arxiv.org/html/1011.1011); [arXiv 1009.6157](https://arxiv.org/pdf/1009.6157)
- Microstructure noise itself is one statistical cause of the Epps effect — [arXiv 1009.6157, "Statistical causes for the Epps effect in microstructure noise"](https://arxiv.org/abs/1009.6157)

### Inferences
- **Derivation (mine).** For two stocks a and b with a common true factor and noise terms `e^a`, `e^b`:
  - `Cov(r^a_t, r^b_t) = Cov(u^a, u^b) + 2 Cov(e^a, e^b)`
  - `Cov(r^a_t, r^b_{t-1}) = -Cov(e^a, e^b)`

  So the lag-1 cross-autocovariance directly estimates the shared-noise covariance, with the sign flipped. If `Cov(r^a_t, r^b_{t-1}) + Cov(r^a_{t-1}, r^b_t) ≈ 0`, the noise is not shared.
- **Scale comparison test.** Compute `corr_h(a, b)` of h-minute returns for h = 1, 2, 5, 15 and 60.
  - Independent noise: the correlation rises with h toward the signal correlation (Epps-like).
  - Shared noise: the correlation at h = 1 is inflated relative to h = 60, because shared noise is a large common component at fine scales and vanishes at coarse scales.

  Torn data is sampled synchronously (all stocks update on the same minute tick), so asynchrony is not a confound: any Epps pattern is driven by noise.
- **PCA / factor share.** Standardise the 1-minute returns of all N stocks and take the eigenvalues of their correlation matrix. Compare the fraction of variance in PC1 at h = 1 with that at h = 60. Shared jitter shows up as a strong PC1 at 1 minute that:
  - has equal-signed loadings;
  - disappears at coarse h;
  - has PC1 scores with rho_1 ≈ -0.5 (a factor that is pure noise mean-reverts).
- **Null distribution.** Under independence, sample correlations are approximately N(0, 1/T) for T minutes. With T = 10,000, |rho| > 0.03 is about 3 sigma. Use the Fisher z transform for confidence intervals. To build a null that keeps each series' own autocorrelation, use a block bootstrap, or circularly shift one series by a random offset of more than 60 minutes.
- **Separating shared noise from rounding.** Rounding alone cannot create a shared pattern unless the true prices move together. A negative lag-1 cross-covariance therefore points to a genuinely shared jitter draw or a shared update artefact. One such artefact to check for: occasional stale or duplicated minutes across all stocks, i.e. minutes where every stock shows r = 0.

### Gaps
- I found no source on testing shared vs independent noise specifically through the lag-1 cross-autocovariance. The derivation above is mine and should be validated by simulation.

## (c) Rounding / discreteness to $0.01

### Takeaway
How rounding behaves depends on the size of the moves:
- When the price moves much more than a cent between observations, rounding adds an extra, roughly i.i.d. noise component with variance about 1/12 cent^2.
- When true moves are sub-cent, rounding becomes strongly dependent on the true price and is no longer i.i.d. For cheap Torn stocks this can dominate.

The practical starting point is the empirical distribution of 1-minute changes in integer cents.

### Cited Findings
- Discrete price increments contribute materially to the Epps effect and to measured noise in high-frequency data — [arXiv 1011.1011](https://ar5iv.arxiv.org/html/1011.1011)
- The primary rounding-error literature (Delattre & Jacod 1997; Li & Mykland) was not fetched (see Gaps).

### Inferences
- **Rounding noise model.** `p_t = round(x_t + e_t, 2)`.
  - If `x_t + e_t` is spread over many cents, the rounding error is about U(-0.5, 0.5) cents: independent, with variance 1/12 ≈ 0.083 cents^2. It simply adds to omega^2.
  - If the true price is nearly constant and the jitter is small (k < 1 cent), rounding produces long runs of identical prices and a non-Gaussian, price-dependent error. Moment estimators then measure rounding and jitter together.
- **Direct tests for discrete uniform jitter of ±k cents:**
  1. **Change histogram.** Tabulate `dp_t` in integer cents during periods where the true price looks flat (for example after removing a long rolling median). For i.i.d. discrete-uniform noise on {-k..k}, the difference `e_t - e_{t-1}` has a triangular distribution on {-2k..2k} with `P(d) = (2k+1-|d|)/(2k+1)^2`. There is a hard support boundary: |dp| never exceeds 2k plus the true drift. Gaussian noise would show tails, while uniform noise shows a cliff. Test the observed dp histogram against the triangular pmf with a chi-square goodness-of-fit test (`scipy.stats.chisquare`).
  2. **Detrended residual distribution.** The residual `p_t - smooth_t` (using a centred rolling median or mean of width about 31) should look flat-topped and uniform on [-k, k], with excess kurtosis -1.2 (Gaussian: 0). Compute it with `scipy.stats.kurtosis`, and test against a uniform with fitted range using KS or Anderson-Darling. Kurtosis near -1.2 is a strong uniform signature.
  3. **Range statistic.** In a flat window of m minutes, `max(p) - min(p)` quickly approaches 2k for uniform noise and rarely exceeds it. For Gaussian noise the range keeps growing like sqrt(2 log m).
  4. **Last-digit (cents) test.** When the noise sd is much larger than 1 cent, the cents digit (`round(p*100) % 10` or `% 100`) should be uniform; check with a chi-square test. Non-uniform last digits point to rounding onto a coarser grid, price-dependent formula artefacts, or a structured PRNG.
  5. **Runs test** on the signs of dp (Wald-Wolfowitz; `statsmodels.sandbox.stats.runs.runstest_1samp`). Pure i.i.d. noise produces too many sign alternations. For i.i.d. continuous noise on a flat true price, the expected fraction of sign reversals between consecutive non-zero differences is 2/3; for a random walk it is 1/2. The 2/3 comes from the sign of `e_{t+1} - e_t` vs `e_t - e_{t-1}`: a standard result, not taken from a fetched source.
  6. **PRNG patterns.** Look for structure beyond i.i.d. noise:
     - residual ACF at many lags (Ljung-Box, `statsmodels.stats.diagnostic.acorr_ljungbox`);
     - spectral peaks indicating periodic patterns (`scipy.signal.periodogram`);
     - dependence on minute-of-hour or hour-of-day;
     - residual correlation across stocks at the same minute (one PRNG call sequence shared across stocks would show cross-sectional structure);
     - residual correlation at lag 1440 (a generator seeded by timestamp may repeat residuals on matching minutes of different days).

### Gaps
- The primary rounding-error literature (Delattre & Jacod 1997; Li & Mykland 2015, "Rounding errors and volatility estimation") was not retrieved, so exact formulas for the RV bias under rounding are unverified.
- I found no source specifically on detecting PRNG-driven jitter in game economies. The tests above are generic statistics.

## (d) Filtering a latent true price: local-level Kalman filter

### Takeaway
The random-walk-plus-noise (local level) model is exactly the model above. Its steady-state Kalman filter is an EWMA whose gain K depends only on `q = sigma_u^2 / omega^2`. Estimate q from the variogram or MA(1) fit, then filter. For bounded uniform noise, use a robust variant or a median prefilter.

### Cited Findings
- The signal-to-noise ratio of the local level model is `q = sigma_eta^2 / sigma_eps^2` (level variance divided by irregular variance) — [Koopman, Aarhus lecture slides](https://econ.au.dk/fileadmin/user_upload/2016Aarhus_Day1.pdf)
- Steady state, with variances scaled by sigma_eps^2: `K = P/(P+1)` and `P = K + q`, so `K^2 + qK - q = 0` and `K = (-q + sqrt(q^2 + 4q))/2`. Convergence to the steady state is slowest for small q — [arXiv 2512.16745](https://arxiv.org/pdf/2512.16745)
- The exponential smoothing parameter alpha equals the steady-state Kalman gain of the local level model — [state-space chapter](https://kundeng.github.io/bayeslearner-scikit-refresh/chapters/16-state-space-kalman.html)
- The equivalent causal exponential-kernel time constant is `tau_eff = -dt / ln(1 - K_ss)` — [arXiv 2610.24018](https://arxiv.org/pdf/2610.24018)

### Inferences
- **Filter equations (per minute):**
  - predict: `x_pred = x_hat`, `P_pred = P + sigma_u^2`
  - gain: `K = P_pred / (P_pred + omega^2)`
  - update: `x_hat = x_pred + K (p_t - x_pred)`, `P = (1-K) P_pred`

  The innovation `v_t = p_t - x_pred` has steady-state variance `F = P_pred + omega^2`. The standardised innovations `z_t = v_t / sqrt(F)` are the natural input to change detection (CUSUM and others) in noise-sigma units.
- **Worked numbers** (from the steady-state formula):

  | q | K | Meaning |
  |---|---|---|
  | 0.01 | ≈ 0.095 | true sd per minute is 10% of noise sd; tau ≈ 10 minutes |
  | 0.1 | ≈ 0.27 | |
  | 1 | ≈ 0.62 | |

  Small q means heavy smoothing and a slow reaction to genuine jumps.
- **Implementation.** `statsmodels.tsa.statespace.structural.UnobservedComponents(p, 'local level').fit()` provides:
  - `res.smoothed_state[0]`: two-sided, best for offline reconstruction;
  - `res.filtered_state[0]`: causal.

  For the steady-state filter alone, `p.ewm(alpha=K, adjust=False).mean()` in pandas is equivalent.
- **Robust variants:**
  1. Student-t observation noise via iterative reweighting: use weight `w_t = (nu+1) / (nu + z_t^2)` and scale omega^2 by 1/w_t for that step.
  2. Huber-style clipped innovation: replace `v_t` with `clip(v_t, -c sqrt(F), c sqrt(F))`.
  3. Bounded uniform noise: the Kalman filter is still the best linear estimator, but nonlinear estimators do better. In a flat window, the midrange `(max+min)/2` estimates the centre of a uniform with variance O(1/m^2), compared with O(1/m) for the mean. A rolling midrange, or the intersection of the intervals `[p_t - k, p_t + k]` over the window (a set-membership filter), can pin the true price very tightly if the jitter is truly bounded. If the intersection becomes empty, the true price must have moved, so this is also an exact change detector under hard-bounded noise.
- **Jump-aware filtering.** Genuine discrete jumps (for example game events) violate the Gaussian random-walk assumption. Two fixes let the filter snap to a new level quickly: a mixture state noise (small sigma most minutes, occasionally large), or resetting P to a large value whenever a change point is flagged.

### Gaps
- No fetched source covers robust Kalman variants (Student-t, Huber) or set-membership filters specifically. The formulas above are standard but unverified here.

## (e) Detecting genuine changes

### Takeaway
First convert prices to standardised innovations or residuals in noise-sigma units. Then choose a detector:
- **CUSUM:** online, fastest when the shift size is known.
- **BOCPD:** online and probabilistic.
- **PELT:** offline, exact segmentation.

Jump tests (Lee-Mykland, BNS bipower) are designed for diffusions with occasional jumps. At 1-minute sampling they are distorted by i.i.d. noise unless the noise is removed first.

### Cited Findings
- **BOCPD (Adams & MacKay 2007).** The method maintains a posterior over the run length r_t (time since the last change):
  - growth: `P(r_t=r_{t-1}+1, x_{1:t}) = P(r_{t-1}, x_{1:t-1}) * pi_t^(r) * (1-H)`
  - changepoint: `P(r_t=0, x_{1:t}) = sum_r P(r_{t-1}, x_{1:t-1}) * pi_t^(r) * H`
  - normalise to get `P(r_t | x_{1:t})`

  The hazard is constant, `H = 1/lambda`, for geometric gaps. Each run keeps conjugate exponential-family statistics, `nu^(r) = nu_prior + r` and `chi^(r) = chi_prior + sum u(x)`, which reset to the prior on a change. Cost per step is linear in t; pruning run lengths with probability below 1e-4 gives a constant average cost of about the expected run length — [Adams & MacKay, arXiv 0710.3742](https://ar5iv.arxiv.org/html/0710.3742)
- **PELT (Killick, Fearnhead & Eckley 2012) in ruptures.** `rpt.Pelt(model=..., min_size=..., jump=...).fit(signal).predict(pen=...)` minimises the sum of segment costs plus a penalty per change point. `min_size` sets the minimum segment length; `jump` restricts candidate indices to multiples of that value — [ruptures Pelt reference](https://centre-borelli.github.io/ruptures-docs/code-reference/detection/pelt-reference); [ruptures source](https://ctruong.perso.math.cnrs.fr/ruptures-docs/build/html/_modules/ruptures/detection/pelt.html)
- Common penalty defaults: a BIC-type penalty `p * ln(n)` (u-analytics implementation), and pen = 10 in tsseg's ruptures wrapper — [u-analytics docs](https://docs.rs/crate/u-analytics/0.3.0/source/src/detection/pelt.rs); [tsseg](https://fchavelli.github.io/tsseg/api/tsseg.algorithms.pelt.html)
- **Lee-Mykland test.**
  - Standardised return: `L_i = |r_i| / sqrt(V_hat_i)`, where V_hat is a local variance estimate.
  - Test statistic: `(max_i L_i - C_M) / S_M`, which is Gumbel-distributed under no jumps.
  - Constants: `C_M = (2 log M)^{1/2}/0.8 - (log pi + log log M)/(1.6 (2 log pi)^{1/2})` and `S_M = 1/(0.6 (2 log pi)^{1/2})`.
  - Reject when the statistic exceeds `-log(-log(1-alpha))`.

  [Survey, arXiv 1708.09520](https://ar5iv.labs.arxiv.org/html/1708.09520); [ISCTE note](https://repositorio.iscte-iul.pt/bitstream/10071/31168/1/article_100198.pdf)
- Nunes & Ruas (2024) report that the commonly reproduced norming constants contain a non-negligible typo relative to the original definition of the critical region. Verify the constants before use — [Finance Research Letters note](https://ideas.repec.org:443/a/eee/finlet/v59y2024ics1544612323011868.html)
- **BNS bipower test.**
  - Bipower variation: `BV = (pi/2)(M/(M-1)) sum_{i>=2} |r_i||r_{i-1}|`.
  - Tripower quarticity: `TP = mu_{4/3}^{-3} (M^2/(M-2)) sum |r_{i-2}|^{4/3}|r_{i-1}|^{4/3}|r_i|^{4/3}`, with `mu_{4/3} = 2^{2/3} Gamma(7/6)/Gamma(1/2)`.
  - Test statistic: `z = (1 - BV/RV) / sqrt(((pi/2)^2 + pi - 5) M^{-1} max(1, TP/BV^2))`, which is N(0,1) under no jumps. The test is one-sided (upper tail).

  [arXiv 1708.09520](https://ar5iv.labs.arxiv.org/html/1708.09520)
- Under microstructure noise, the survey recommends noise-robust jump tests: LM12, which uses block-averaged prices, and ASJL, which uses locally smoothed prices. The size and power of the plain tests degrade with noise — [arXiv 1708.09520](https://ar5iv.labs.arxiv.org/html/1708.09520)

### Inferences
- **Do not apply raw LM or BNS to jittered 1-minute returns.** With rho_1 strongly negative, BV (built from products of adjacent |r|) is biased relative to RV. A single noise draw also creates two equal and opposite returns, a spike-and-revert that looks like two jumps. A genuine level shift produces one large return with no reversal.
  - Quick discriminator: for a candidate large r_t, compare `r_t` with `r_{t+1}`. A noise outlier gives `r_{t+1} ≈ -r_t`; a genuine change keeps `p_{t+1..t+m}` at the new level.
  - Formal version: a two-sample test of `mean(p[t-m:t])` vs `mean(p[t:t+m])` with standard error `omega*sqrt(2/m)`. If q is not negligible, add a random-walk term of roughly `sigma_u^2 m/3`.
- **CUSUM on standardised data** (Page 1954; standard method). For residuals `z_t` in noise-sigma units and a target shift of size delta:
  - `S+_t = max(0, S+_{t-1} + z_t - delta/2)`
  - `S-_t = max(0, S-_{t-1} - z_t - delta/2)`
  - alarm when either exceeds h.

  With h = 4-5 and delta = 1, the in-control average run length (ARL) for Gaussian i.i.d. data is typically in the hundreds to around a thousand observations. Detection delay is about h / (delta/2) observations for a shift of delta, so a change of 1 noise-sigma takes about 8-10 minutes to detect and a 4-sigma change about 1-3 minutes. Raising h increases the in-control ARL roughly exponentially, but the delay only linearly.

  Input choice: use Kalman innovations (`p_t - x_hat_{t-1}`) or `p_t - baseline`, where baseline is a fixed pre-change level. Raw differences r_t are a poor input because the noise in differences is MA(1).
- **Uniform jitter makes thresholds sharper.** If the noise is hard-bounded at ±k, any observation outside `[x_hat - k, x_hat + k]` (allowing 0.005 for rounding) proves a genuine change, with a false-alarm rate of zero under the model. The set-membership filter from (d) gives this naturally. Gaussian sigma thresholds are conservative for uniform noise, which has no tails: P(|e| > sqrt(3) sigma) = 0.
- **BOCPD set-up for this problem.**
  - Model: Gaussian with unknown mean and known variance omega^2 (from the variogram), with a conjugate Normal prior on the mean. The predictive distribution is `N(mu_r, omega^2 + s_r^2)`.
  - Hazard: `1/lambda`, where lambda is the expected number of minutes between genuine changes (for example 60).
  - Output: read `P(r_t < 5)` as the probability that a change happened in the last 5 minutes.

  If the true price drifts as a random walk rather than being piecewise constant, BOCPD with a constant-mean model will fire spuriously. In that case either model a slope or run BOCPD on Kalman innovations.
- **PELT set-up.**
  - Call: `rpt.Pelt(model='l2', min_size=3).fit(p.values).predict(pen=beta)`.
  - Penalty units: the l2 cost is unscaled squared error, so the penalty must be in the same units. Use `beta ≈ 2 * omega^2 * log(n)` (BIC-style, with known variance omega^2), or equivalently divide the signal by omega first and use `pen ≈ 2 log n`.
  - Use `model='normal'` to also catch variance changes, such as a change in jitter amplitude.

  PELT is offline only. It is good for labelling historical changes in order to evaluate online detectors.
- **Other ruptures options.** Binary segmentation (`rpt.Binseg`) is faster but approximate. Window (`rpt.Window(width=w)`) is a sliding two-sample approach that maps directly onto the before-vs-after mean test above.
- **Evaluation.** When noise is non-Gaussian, the most reliable way to calibrate thresholds is by simulation:
  1. Simulate the fitted model: a random walk with q_hat, plus discrete-uniform or Gaussian jitter, plus injected steps of known size.
  2. For each method and threshold, measure false alarms per day and median detection delay.
  3. Choose the operating point on the resulting ROC-style curve.

### Gaps
- No primary CUSUM source was fetched. The ARL figures are standard SPC rules of thumb, not verified here. statsmodels has no built-in CUSUM change detector, so implement it manually (ruptures covers offline detection).
- The ruptures documentation gives no guidance on calibrating the penalty. The BIC-style suggestion is a heuristic.
- The original Lee-Mykland window-size (K) recommendations for 1-minute data were not retrieved, and the 2024 note on the constant typo was not read in full.
