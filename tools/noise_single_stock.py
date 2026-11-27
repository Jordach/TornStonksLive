#!/usr/bin/env python3
"""Per-stock analysis of minute-level price noise ("fuzzing") in Torn City stocks.

Reads the TornStonks Live m1 SQLite files (db_<ticker>.db, table m1) read-only
and works on log prices in basis points (1 bp = 0.01 % of price), which makes
numbers comparable across cheap and expensive stocks.  Cent figures are given
alongside, using the window's median price.

Model used throughout (local-level / "random walk plus noise"):

    y_t = x_t + e_t        observed log price (bp), e_t ~ iid(0, s_e^2)
    x_t = x_{t-1} + u_t    hidden ("latent") log price, u_t ~ iid(0, s_u^2)

so that Var(k-minute change) = 2 s_e^2 + k s_u^2, and 1-minute changes are an
MA(1) with lag-1 autocovariance -s_e^2.  Price rounding to whole cents adds
uniform noise of variance (1 cent)^2/12 that is reported separately.

Subcommands
-----------
characterise  distribution of 1-min cent changes, ACF, variance signature,
              rolling-median residuals, price scaling, Kalman MLE.
filter        write latent price (Kalman / EWMA / rolling median) and detected
              moves to CSV.
evaluate      false-alarm rate on simulated noise and detection delay for
              steps / trends injected into real data.

Only consecutive minutes are differenced: rows are placed on a regular 1-min
grid and any difference touching a missing minute is dropped.

Examples
--------
  python tools/noise_single_stock.py characterise --tickers ass fhg --days 30
  python tools/noise_single_stock.py filter --tickers ass --days 7 --out out/
  python tools/noise_single_stock.py evaluate --tickers ass --days 30
  python tools/noise_single_stock.py characterise --tickers ass --end 2022-09-01 --days 90

Recommended detector settings (from `evaluate` on 30-day windows, Nov 2026):
  * jump flag: |Kalman innovation z| > 6 -> one-minute genuine jump
    (Gaussian model: ~0/day; real data 0.03/day ASS .. 2.7/day FHG).
  * trend: two-sided CUSUM on standardized innovations, k=0.125, h=25
    (~0.13 alarms/day under the zero-drift model, 0.2-0.6/day on real data;
    detects a 0.5 su/min (~0.3 %/h) drift in ~1 h, 0.25 su/min in ~2.5 h).
  * level: filtered level leaves anchor by > 5 noise sds -> "moved beyond
    noise" (0 false alarms/30 d on simulated pure noise; fires every few
    minutes on real data because the latent price itself diffuses ~1 bp/min).

Dependencies: numpy, pandas, scipy.  Standalone (no bot imports).
--db-dir defaults to the repo's db/ (or the main checkout's db/ from a worktree).
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
from scipy import optimize, stats

def _default_db_dir():
    """Repo db/, falling back to the main checkout's db/ when run from a git
    worktree at <repo>/.claude/worktrees/<name>."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.path.join(root, "db"), os.path.join(root, "..", "..", "..", "db")):
        if os.path.isdir(cand) and any(f.startswith("db_") and f.endswith(".db") for f in os.listdir(cand)):
            return os.path.normpath(cand)
    return os.path.join(root, "db")


DEFAULT_DB_DIR = _default_db_dir()
SIG_KS = [1, 2, 3, 5, 10, 20, 30, 60, 120, 240, 480, 1440]


# --------------------------------------------------------------------------
# Data loading (private loader, deliberately independent of other tools)
# --------------------------------------------------------------------------
def _parse_ts(s):
    if s is None:
        return None
    if str(s).isdigit():
        return int(s)
    d = dt.datetime.fromisoformat(str(s))
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp())


def list_db_tickers(db_dir):
    out = []
    for f in sorted(os.listdir(db_dir)):
        if f.startswith("db_") and f.endswith(".db") and f != "db_suggestions.db":
            out.append(f[3:-3])
    return out


def load_grid(db_dir, ticker, days=30, end_ts=None):
    """Return (grid_ts, price) on a regular 60 s grid; missing minutes are NaN.

    The window is the `days` days ending at end_ts (default: last row in DB).
    """
    path = os.path.abspath(os.path.join(db_dir, f"db_{ticker.lower()}.db"))
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if end_ts is None:
            end_ts = con.execute("select max(date) from m1").fetchone()[0]
        start_ts = end_ts - int(days * 86400)
        rows = con.execute(
            "select date, close from m1 where date > ? and date <= ? order by date",
            (start_ts, end_ts)).fetchall()
    finally:
        con.close()
    if len(rows) < 100:
        raise SystemExit(f"{ticker}: only {len(rows)} rows in window")
    a = np.asarray(rows, dtype=float)
    ts = a[:, 0].astype(np.int64)
    ts = ts - (ts % 60)  # snap to minute
    t0 = ts[0]
    idx = (ts - t0) // 60
    n = int(idx[-1]) + 1
    price = np.full(n, np.nan)
    price[idx] = a[:, 1]
    grid = t0 + 60 * np.arange(n, dtype=np.int64)
    return grid, price


def kdiff(g, k):
    """k-step differences on a grid with NaN gaps (only valid pairs kept, NaN otherwise)."""
    return g[k:] - g[:-k]


def finite(x):
    return x[np.isfinite(x)]


# --------------------------------------------------------------------------
# Statistics helpers
# --------------------------------------------------------------------------
def acf_grid(d, lags):
    out = []
    for L in lags:
        a, b = d[:-L], d[L:]
        m = np.isfinite(a) & np.isfinite(b)
        out.append(float(np.corrcoef(a[m], b[m])[0, 1]) if m.sum() > 10 else float("nan"))
    return out


def signature(y, ks):
    return {k: float(np.var(finite(kdiff(y, k)))) for k in ks}


def disc_loglik(cents, dist):
    """Mean log-lik of integer cent changes under a continuous dist rounded to integers."""
    v, c = np.unique(cents, return_counts=True)
    p = dist.cdf(v + 0.5) - dist.cdf(v - 0.5)
    p = np.clip(p, 1e-300, None)
    return float((c * np.log(p)).sum() / c.sum())


def fit_distributions(cents):
    sd = cents.std()
    res = {}
    res["normal"] = disc_loglik(cents, stats.norm(0, sd))

    def nll_lap(lb):
        return -disc_loglik(cents, stats.laplace(0, math.exp(lb)))
    r = optimize.minimize_scalar(nll_lap, bounds=(math.log(sd / 10 + 1e-3), math.log(sd * 3 + 1)), method="bounded")
    res["laplace"] = -r.fun

    def nll_t(p):
        df, ls = math.exp(p[0]), math.exp(p[1])
        return -disc_loglik(cents, stats.t(df, 0, ls))
    r = optimize.minimize(nll_t, [math.log(5), math.log(sd + 0.1)], method="Nelder-Mead",
                          options={"xatol": 1e-3, "fatol": 1e-6})
    res["student_t"] = -r.fun
    res["t_df"] = math.exp(r.x[0])
    # uniform / triangular (bounded) supports: best a s.t. all mass inside
    a = np.abs(cents).max() + 0.5
    res["triangular_maxsupport"] = disc_loglik(cents, stats.triang(0.5, loc=-a, scale=2 * a))
    return res


# --------------------------------------------------------------------------
# Local-level Kalman filter
# --------------------------------------------------------------------------
def kalman(y, su2, se2, x0=None):
    """Local-level filter on a NaN-gapped grid. Returns level, P, innovation, S, loglik."""
    n = len(y)
    L = np.full(n, np.nan)
    P = np.full(n, np.nan)
    V = np.full(n, np.nan)
    S = np.full(n, np.nan)
    first = int(np.argmax(np.isfinite(y)))
    x = y[first] if x0 is None else x0
    p = se2
    ll = 0.0
    yl = y.tolist()
    for i in range(first, n):
        p += su2
        yi = yl[i]
        if yi == yi:  # not NaN
            s = p + se2
            v = yi - x
            k = p / s
            x += k * v
            p *= (1 - k)
            V[i] = v
            S[i] = s
            ll += -0.5 * (math.log(2 * math.pi * s) + v * v / s)
        L[i] = x
        P[i] = p
    return L, P, V, S, ll


def kalman_mle(y, su2_0, se2_0, max_n=60000):
    """MLE of (su2, se2). Uses the last max_n grid points to bound run time."""
    yy = y[-max_n:]

    def nll(p):
        return -kalman(yy, math.exp(p[0]), math.exp(p[1]))[4]
    p0 = [math.log(max(su2_0, 1e-4)), math.log(max(se2_0, 1e-4))]
    r = optimize.minimize(nll, p0, method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-2, "maxiter": 200})
    return math.exp(r.x[0]), math.exp(r.x[1])


def steady_state(su2, se2):
    q = su2 / se2
    pbar = (q + math.sqrt(q * q + 4 * q)) / 2 * se2  # prior variance
    K = pbar / (pbar + se2)
    return q, K, pbar


# --------------------------------------------------------------------------
# Detectors
# --------------------------------------------------------------------------
def cusum_detect(z, kref=0.5, h=8.0, reset=True):
    """Two-sided CUSUM on a standardized series z (NaN = skip). Returns array of +1/-1/0 alarms."""
    n = len(z)
    out = np.zeros(n, dtype=np.int8)
    sp = sm = 0.0
    zl = z.tolist()
    for i in range(n):
        v = zl[i]
        if v != v:
            continue
        sp = max(0.0, sp + v - kref)
        sm = max(0.0, sm - v - kref)
        if sp > h:
            out[i] = 1
            sp = sm = 0.0 if reset else sp
        elif sm > h:
            out[i] = -1
            sp = sm = 0.0 if reset else sm
    return out


def level_detect(level, band):
    """Anchor-shift detector: alarm when filtered level leaves anchor +/- band; re-anchor there."""
    n = len(level)
    out = np.zeros(n, dtype=np.int8)
    ll = level.tolist()
    first = int(np.argmax(np.isfinite(level)))
    a = ll[first]
    for i in range(first, n):
        v = ll[i]
        if v != v:
            continue
        if v - a > band:
            out[i] = 1
            a = v
        elif a - v > band:
            out[i] = -1
            a = v
    return out


def standardized_innov(V, S, adapt_hl=None):
    z = V / np.sqrt(S)
    if adapt_hl:
        # scale by local volatility of past innovations (EWMA of z^2, excluding current)
        s = pd.Series(z ** 2).ewm(halflife=adapt_hl, ignore_na=True, min_periods=10).mean().shift(1)
        z = z / np.sqrt(s.clip(lower=0.25).to_numpy())
    return z


# --------------------------------------------------------------------------
# Core per-stock analysis
# --------------------------------------------------------------------------
def analyse(db_dir, ticker, days, end_ts, verbose=True):
    grid, price = load_grid(db_dir, ticker, days, end_ts)
    pmed = float(np.nanmedian(price))
    cent_bp = 1e4 / (pmed * 100)  # bp per cent at median price
    y = np.log(price) * 1e4  # bp
    cents = np.round(price * 100)
    dc = finite(kdiff(cents, 1)).astype(int)
    dy = kdiff(y, 1)
    res = {"ticker": ticker, "start": dt.datetime.utcfromtimestamp(int(grid[0])).strftime("%Y-%m-%d %H:%M"),
           "end": dt.datetime.utcfromtimestamp(int(grid[-1])).strftime("%Y-%m-%d %H:%M"),
           "n_obs": int(np.isfinite(price).sum()), "n_grid": len(price), "n_diffs": len(dc),
           "price_median": pmed, "price_min": float(np.nanmin(price)), "price_max": float(np.nanmax(price)),
           "bp_per_cent": cent_bp}
    # ---- distribution of 1-min cent changes
    res["zero_frac"] = float((dc == 0).mean())
    dcg = kdiff(cents, 1)
    m01 = np.isfinite(dcg[:-1]) & np.isfinite(dcg[1:]) & (dcg[:-1] == 0)
    res["zero_after_zero"] = float((dcg[1:][m01] == 0).mean())
    res["d_sd_cents"] = float(dc.std())
    res["d_sd_bp"] = float(np.nanstd(dy))
    res["d_max_abs"] = int(np.abs(dc).max())
    res["d_excess_kurt"] = float(stats.kurtosis(dc))
    for q in (50, 90, 99, 99.9):
        res[f"d_absq{q}"] = float(np.percentile(np.abs(dc), q))
    res["hist"] = dict(zip(*[a.tolist() for a in np.unique(dc, return_counts=True)]))
    fits = fit_distributions(dc)
    res.update({f"ll_{k}": v for k, v in fits.items()})
    # vol-normalised kurtosis (EWMA vol of past squared changes, 60-min halflife)
    s2 = pd.Series(dy ** 2).ewm(halflife=60, ignore_na=True, min_periods=30).mean().shift(1).to_numpy()
    zn = finite(dy / np.sqrt(s2))
    res["d_excess_kurt_volnorm"] = float(stats.kurtosis(zn))
    # ---- memory
    lags = list(range(1, 31))
    res["acf"] = acf_grid(dy, lags)
    res["acf_abs"] = acf_grid(np.abs(dy - np.nanmean(dy)), [1, 5, 30, 60, 240])
    sig = signature(y, SIG_KS)
    res["signature"] = {k: v / k for k, v in sig.items()}
    # fit Var(k) = a + b k on k = 1..30 (short horizons, before slow effects)
    kk = np.arange(1, 31)
    vk = np.array([np.var(finite(kdiff(y, int(k)))) for k in kk])
    b, a = np.polyfit(kk, vk, 1)
    res["sig_se2_bp2"] = a / 2
    res["sig_su2_bp2"] = b
    # AR(1) noise variant: Var(k) = k su2 + 2 se2 (1 - phi^k), fit on k = 1..60
    kk2 = np.arange(1, 61)
    vk2 = np.array([np.var(finite(kdiff(y, int(k)))) for k in kk2])

    def resid(p):
        su2_, se2_, ph = p
        return (kk2 * su2_ + 2 * se2_ * (1 - ph ** kk2) - vk2) / vk2
    fit = optimize.least_squares(resid, [b, max(a / 2, 1e-3), 0.2], bounds=([0, 0, 0], [np.inf, np.inf, 0.95]))
    res["ar_su2_bp2"], res["ar_se2_bp2"], res["ar_phi"] = [float(v) for v in fit.x]
    # MA(1) moment estimator
    d = dy
    m = np.isfinite(d[:-1]) & np.isfinite(d[1:])
    g1 = float(np.mean((d[:-1][m] - np.nanmean(d)) * (d[1:][m] - np.nanmean(d))))
    g0 = float(np.nanvar(d))
    res["ma1_se2_bp2"] = -g1
    res["ma1_su2_bp2"] = g0 + 2 * g1
    res["round_var_bp2"] = cent_bp ** 2 / 12
    # ---- Kalman MLE
    su2, se2 = kalman_mle(y, max(res["ma1_su2_bp2"], 1e-3), max(res["ma1_se2_bp2"], 1e-3))
    q, K, pbar = steady_state(su2, se2)
    res.update({"mle_su2_bp2": su2, "mle_se2_bp2": se2, "q": q, "K": K})
    res["se_excess_bp"] = math.sqrt(max(se2 - res["round_var_bp2"], 0))
    res["se_bp"] = math.sqrt(se2)
    res["su_bp"] = math.sqrt(su2)
    # ---- rolling-median residuals
    ys = pd.Series(y)
    for w in (5, 15, 31, 61):
        med = ys.rolling(w, center=True, min_periods=w).median()
        r = (ys - med).to_numpy()
        r = finite(r)
        res[f"rm{w}_sd_bp"] = float(r.std())
        res[f"rm{w}_q99_bp"] = float(np.percentile(np.abs(r), 99))
        res[f"rm{w}_max_bp"] = float(np.abs(r).max())
        res[f"rm{w}_kurt"] = float(stats.kurtosis(r))
    # ---- within-stock price scaling: daily sd of cent changes vs daily median price
    day = (grid[1:] - grid[0]) // 86400
    dcf = kdiff(cents, 1)
    df = pd.DataFrame({"day": day, "dc": dcf, "p": price[1:]}).dropna()
    gd = df.groupby("day").agg(sd=("dc", "std"), p=("p", "median"), n=("dc", "size"))
    gd = gd[gd.n > 600]
    if len(gd) > 5 and gd.p.max() / gd.p.min() > 1.2:
        sl, ic, rr, pv, se = stats.linregress(np.log(gd.p), np.log(gd.sd))
        res["scale_slope"] = float(sl)
        res["scale_slope_se"] = float(se)
    else:
        res["scale_slope"] = float("nan")
        res["scale_slope_se"] = float("nan")
    res["_y"] = y
    res["_grid"] = grid
    res["_price"] = price
    return res


def print_characterise(r):
    cb = r["bp_per_cent"]
    print(f"\n=== {r['ticker'].upper()}  {r['start']} .. {r['end']}  obs={r['n_obs']} grid={r['n_grid']} diffs={r['n_diffs']}")
    print(f"price median {r['price_median']:.2f} (range {r['price_min']:.2f}-{r['price_max']:.2f}); 1 cent = {cb:.3f} bp")
    print(f"1-min cent change: zero={r['zero_frac']:.3f} P(0|prev 0)={r['zero_after_zero']:.3f} sd={r['d_sd_cents']:.2f}c ({r['d_sd_bp']:.3f} bp) "
          f"max|d|={r['d_max_abs']} |d| q50/90/99/99.9={r['d_absq50']:.0f}/{r['d_absq90']:.0f}/{r['d_absq99']:.0f}/{r['d_absq99.9']:.0f} "
          f"exkurt={r['d_excess_kurt']:.2f} (vol-normalised {r['d_excess_kurt_volnorm']:.2f})")
    print(f"  mean loglik/obs: normal={r['ll_normal']:.4f} laplace={r['ll_laplace']:.4f} "
          f"t={r['ll_student_t']:.4f} (df={r['ll_t_df']:.1f}) triangular(max support)={r['ll_triangular_maxsupport']:.4f}")
    h = r["hist"]
    core = " ".join(f"{k}:{h.get(k, 0)}" for k in range(-8, 9))
    print(f"  hist -8..8: {core}")
    a = r["acf"]
    print("  ACF(d) lags1-5,10,20,30: " + " ".join(f"{a[i-1]:+.3f}" for i in (1, 2, 3, 4, 5, 10, 20, 30)))
    print("  ACF(|d|) lags 1,5,30,60,240: " + " ".join(f"{v:+.3f}" for v in r["acf_abs"]))
    print("  Var(k)/k bp^2: " + " ".join(f"{k}:{v:.3f}" for k, v in r["signature"].items()))
    print(f"  noise var se^2 (bp^2): signature={r['sig_se2_bp2']:.4f} MA1={r['ma1_se2_bp2']:.4f} MLE={r['mle_se2_bp2']:.4f} "
          f"| rounding-only={r['round_var_bp2']:.4f}")
    print(f"  AR(1)-noise signature fit: se^2={r['ar_se2_bp2']:.4f} bp^2 (se={math.sqrt(r['ar_se2_bp2']):.3f} bp = "
          f"{math.sqrt(r['ar_se2_bp2'])/cb:.2f} c) phi={r['ar_phi']:.2f} su^2={r['ar_su2_bp2']:.4f}")
    print(f"  diffusion su^2 (bp^2/min): signature={r['sig_su2_bp2']:.4f} MA1={r['ma1_su2_bp2']:.4f} MLE={r['mle_su2_bp2']:.4f}")
    print(f"  se={r['se_bp']:.3f} bp = {r['se_bp']/cb:.2f} c (excess over rounding {r['se_excess_bp']:.3f} bp = {r['se_excess_bp']/cb:.2f} c); "
          f"su={r['su_bp']:.3f} bp/min = {r['su_bp']/cb:.2f} c; q=su2/se2={r['q']:.2f}; steady-state K={r['K']:.3f}")
    print("  rolling-median residual sd/q99/max bp: " + "  ".join(
        f"w{w}:{r[f'rm{w}_sd_bp']:.2f}/{r[f'rm{w}_q99_bp']:.2f}/{r[f'rm{w}_max_bp']:.1f}(k{r[f'rm{w}_kurt']:.1f})" for w in (5, 15, 31, 61)))
    print(f"  daily sd(cents) vs price log-log slope: {r['scale_slope']:.2f} +/- {r['scale_slope_se']:.2f} (1 = proportional)")


def summary_row(r):
    keys = ["ticker", "start", "end", "price_median", "zero_frac", "zero_after_zero", "d_sd_cents", "d_sd_bp", "d_max_abs",
            "d_excess_kurt", "d_excess_kurt_volnorm", "ll_normal", "ll_laplace", "ll_student_t", "ll_t_df",
            "sig_se2_bp2", "ma1_se2_bp2", "ar_se2_bp2", "ar_phi", "ar_su2_bp2", "mle_se2_bp2", "round_var_bp2", "sig_su2_bp2", "mle_su2_bp2",
            "se_bp", "se_excess_bp", "su_bp", "q", "K", "rm15_sd_bp", "rm61_sd_bp", "scale_slope"]
    row = {k: r[k] for k in keys}
    row["acf1"] = r["acf"][0]
    row["acf2"] = r["acf"][1]
    row["acf_abs1"] = r["acf_abs"][0]
    row["acf_abs60"] = r["acf_abs"][3]
    row["se_cents"] = r["se_bp"] / r["bp_per_cent"]
    row["su_cents"] = r["su_bp"] / r["bp_per_cent"]
    return row


# --------------------------------------------------------------------------
# filter subcommand
# --------------------------------------------------------------------------
def run_filter(r, args):
    y, grid, price = r["_y"], r["_grid"], r["_price"]
    su2, se2 = r["mle_su2_bp2"], r["mle_se2_bp2"]
    L, P, V, S, _ = kalman(y, su2, se2)
    K = r["K"]
    ewma = pd.Series(y).ewm(alpha=K, ignore_na=True).mean().to_numpy()
    med = pd.Series(y).rolling(args.median_window, min_periods=1).median().to_numpy()  # trailing (causal)
    z = standardized_innov(V, S, adapt_hl=args.adapt_hl)
    cus = cusum_detect(z, kref=args.kref, h=args.h)
    band = args.band * math.sqrt(se2)
    lev = level_detect(L, band)
    jump = np.where(np.abs(V / np.sqrt(S)) > args.jump_z, np.sign(V), 0).astype(int)
    m = np.isfinite(price)
    out = pd.DataFrame({
        "date": grid[m],
        "utc": pd.to_datetime(grid[m], unit="s", utc=True),
        "price": price[m],
        "kalman": np.round(np.exp(L[m] / 1e4), 4),
        "kalman_sd_cents": np.sqrt(P[m]) / r["bp_per_cent"],
        "ewma": np.round(np.exp(ewma[m] / 1e4), 4),
        "median_trailing": np.round(np.exp(med[m] / 1e4), 4),
        "innov_z": z[m],
        "cusum_alarm": cus[m],
        "level_alarm": lev[m],
        "jump_flag": jump[m],
    })
    days = (grid[-1] - grid[0]) / 86400
    print(f"{r['ticker'].upper()}: su2={su2:.4f} se2={se2:.4f} bp^2 K={K:.3f}; "
          f"CUSUM(k={args.kref},h={args.h}) alarms/day={np.abs(cus).sum()/days:.1f}; "
          f"level(band={args.band} se = {band:.2f} bp = {band/r['bp_per_cent']:.1f} c) alarms/day={np.abs(lev).sum()/days:.1f}; "
          f"jumps(|z|>{args.jump_z})/day={np.abs(jump).sum()/days:.2f}")
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        fn = os.path.join(args.out, f"filter_{r['ticker']}.csv")
        out.to_csv(fn, index=False)
        print(f"  wrote {fn}")
    return out


# --------------------------------------------------------------------------
# evaluate subcommand
# --------------------------------------------------------------------------
def simulate(n, su2, se2, price_c, rng, drift=0.0):
    """Simulate observed log-price bp: RW(su2) + N(0,se2) noise, then round to cents."""
    x = np.cumsum(rng.normal(drift, math.sqrt(su2), n)) if su2 > 0 else np.zeros(n)
    yb = x + rng.normal(0, math.sqrt(se2), n)
    p = np.round(price_c * np.exp(yb / 1e4)) / 100
    return np.log(p) * 1e4


def detector_alarms(y, su2, se2, kref, h, band_se, adapt_hl=None):
    L, P, V, S, _ = kalman(y, su2, se2)
    z = standardized_innov(V, S, adapt_hl)
    return cusum_detect(z, kref, h), level_detect(L, band_se * math.sqrt(se2)), L


def run_evaluate(r, args):
    rng = np.random.default_rng(args.seed)
    y = r["_y"]
    su2, se2 = r["mle_su2_bp2"], r["mle_se2_bp2"]
    se_round_free2 = max(se2 - r["round_var_bp2"], 1e-6)  # simulate jitter excluding rounding (rounding added by sim)
    pc = r["price_median"] * 100
    n_sim = int(args.sim_days * 1440)
    tk = r["ticker"].upper()
    print(f"\n=== EVALUATE {tk}: su={math.sqrt(su2):.3f} bp/min se={math.sqrt(se2):.3f} bp K={r['K']:.3f} price {pc/100:.2f}")
    hs = [float(x) for x in args.h_grid.split(",")]
    bands = [float(x) for x in args.band_grid.split(",")]

    # 1) pure-noise null: constant hidden price
    y0 = simulate(n_sim, 0.0, se_round_free2, pc, rng)
    print(f"[pure-noise sim, {args.sim_days} d] false alarms/day")
    for h in hs:
        c, _, _ = detector_alarms(y0, su2, se2, args.kref, h, 1e9)
        print(f"  CUSUM k={args.kref} h={h:g}: {np.abs(c).sum()/args.sim_days:.3f}")
    for b in bands:
        _, l, _ = detector_alarms(y0, su2, se2, args.kref, 1e9, b)
        print(f"  level band={b:g} se ({b*math.sqrt(se2):.2f} bp, {b*math.sqrt(se2)/r['bp_per_cent']:.1f} c): {np.abs(l).sum()/args.sim_days:.3f}")
    # also: max |Kalman level - truth| under pure noise
    L0 = kalman(y0, su2, se2)[0]
    print(f"  pure-noise filtered-level deviation sd={np.nanstd(L0 - np.nanmean(L0)):.3f} bp, "
          f"max={np.nanmax(np.abs(L0 - np.nanmean(L0))):.3f} bp ({np.nanmax(np.abs(L0 - np.nanmean(L0)))/math.sqrt(se2):.2f} se)")

    # 2) zero-drift random walk + noise null (fitted model): CUSUM average run length
    y1 = simulate(n_sim, su2, se_round_free2, pc, rng)
    print(f"[RW+noise sim, zero drift] CUSUM alarms/day (the model's own diffusion):")
    for h in hs:
        c, _, _ = detector_alarms(y1, su2, se2, args.kref, h, 1e9)
        print(f"  h={h:g}: {np.abs(c).sum()/args.sim_days:.2f}/day")
    # real data alarm rate
    days = np.isfinite(y).sum() / 1440
    print(f"[real data, {days:.1f} d] alarms/day (plain / vol-adaptive hl={args.adapt_hl}):")
    for h in hs:
        c, _, _ = detector_alarms(y, su2, se2, args.kref, h, 1e9)
        ca, _, _ = detector_alarms(y, su2, se2, args.kref, h, 1e9, adapt_hl=args.adapt_hl)
        print(f"  CUSUM h={h:g}: {np.abs(c).sum()/days:.2f} / {np.abs(ca).sum()/days:.2f}")
    for b in bands:
        _, l, _ = detector_alarms(y, su2, se2, args.kref, 1e9, b)
        print(f"  level band={b:g} se: {np.abs(l).sum()/days:.2f}/day")
    # single-minute jump flag |innovation z| > jz
    zs = []
    for yy in (y1, y):
        _, _, V_, S_, _ = kalman(yy, su2, se2)
        zs.append(np.abs(finite(V_ / np.sqrt(S_))))
    print("[jump flag |z|>jz] events/day  Gaussian RW+noise sim | real data:")
    for jz in (4, 5, 6, 8, 10):
        print(f"  jz={jz}: {np.sum(zs[0] > jz)/args.sim_days:.3f} | {np.sum(zs[1] > jz)/days:.2f}")
    # follow-through: after a CUSUM alarm, is price 60 min later further in alarm direction?
    c, l, L = detector_alarms(y, su2, se2, args.kref, args.h, 1e9)
    for name, al in (("CUSUM h=%g" % args.h, c),):
        idx = np.nonzero(al)[0]
        idx = idx[idx + 60 < len(y)]
        fwd = (L[idx + 60] - L[idx]) * al[idx]
        fwd = finite(fwd)
        if len(fwd):
            print(f"  {name}: next-60-min move in alarm direction: mean={fwd.mean():+.2f} bp, P(>0)={np.mean(fwd > 0):.2f} "
                  f"(n={len(fwd)}; RW null expectation 0 / 0.5)")

    # 3) injected steps and trends into real data
    n = len(y)
    valid = np.nonzero(np.isfinite(y))[0]
    W0, H = 240, args.horizon
    starts = valid[(valid > W0) & (valid < n - H)]
    starts = rng.choice(starts, size=min(args.n_inject, len(starts)), replace=False)
    se = math.sqrt(se2)
    su = math.sqrt(su2)

    def delay_stats(inj_fn, det, sign_):
        delays, base = [], []
        for t0 in starts:
            seg = y[t0 - W0:t0 + H].copy()
            seg_b = seg.copy()
            seg[W0:] += inj_fn(np.arange(H)) * sign_
            for s_, store in ((seg, delays), (seg_b, base)):
                if det == "cusum":
                    a, _, _ = detector_alarms(s_, su2, se2, args.kref, args.h, 1e9)
                elif det == "jump":
                    _, _, V_, S_, _ = kalman(s_, su2, se2)
                    zz = V_ / np.sqrt(S_)
                    a = np.where(np.abs(zz) > args.jump_z, np.sign(zz), 0)
                else:
                    _, a, _ = detector_alarms(s_, su2, se2, args.kref, 1e9, args.band)
                hit = np.nonzero(a[W0:] == sign_)[0]
                store.append(hit[0] if len(hit) else np.inf)
        delays, base = np.array(delays), np.array(base)
        return delays, base

    print(f"[injected into real data, n={len(starts)}, horizon {H} min] detection delay in minutes "
          f"(median, P(detected<=H)), baseline = same-direction alarm without injection")
    for mult in [float(x) for x in args.step_grid.split(",")]:
        step = mult * se
        for det in ("level", "jump", "cusum"):
            dl, bs = delay_stats(lambda t, s=step: np.full_like(t, s, dtype=float), det, 1)
            print(f"  step {mult:g} se = {step:.2f} bp ({step/r['bp_per_cent']:.1f} c, {step/su:.1f} su) [{det}]: "
                  f"median {np.median(dl):.0f}, P={np.mean(np.isfinite(dl)):.2f} | baseline median {np.median(bs):.0f}, P={np.mean(np.isfinite(bs)):.2f}")
    for mult in [float(x) for x in args.trend_grid.split(",")]:
        mu = mult * su
        dl, bs = delay_stats(lambda t, m=mu: m * (t + 1.0), "cusum", 1)
        print(f"  trend {mult:g} su/min = {mu:.3f} bp/min ({mu*60/100:.3f} %/h) [cusum]: "
              f"median {np.median(dl):.0f}, P={np.mean(np.isfinite(dl)):.2f} | baseline median {np.median(bs):.0f}, P={np.mean(np.isfinite(bs)):.2f}")


# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["characterise", "filter", "evaluate"])
    ap.add_argument("--db-dir", default=DEFAULT_DB_DIR)
    ap.add_argument("--tickers", "--ticker", nargs="+", default=["ass"], help="tickers, or 'all'")
    ap.add_argument("--days", type=float, default=30)
    ap.add_argument("--end", default=None, help="window end (ISO date or unix ts); default last row")
    ap.add_argument("--out", default=None, help="output directory for CSVs")
    # detector params
    ap.add_argument("--kref", type=float, default=0.125, help="CUSUM reference value (sd units)")
    ap.add_argument("--h", type=float, default=25.0, help="CUSUM threshold (sd units)")
    ap.add_argument("--band", type=float, default=5.0, help="level-detector band in noise sds (se)")
    ap.add_argument("--jump-z", type=float, default=6.0, help="single-minute jump flag |innovation z|")
    ap.add_argument("--adapt-hl", type=float, default=None, help="vol-adaptive CUSUM EWMA halflife (min)")
    ap.add_argument("--median-window", type=int, default=15)
    # evaluate params
    ap.add_argument("--sim-days", type=float, default=30)
    ap.add_argument("--h-grid", default="10,15,20,25,30,40")
    ap.add_argument("--band-grid", default="3,4,5,6,8")
    ap.add_argument("--step-grid", default="3,10,20,30")
    ap.add_argument("--trend-grid", default="0.1,0.25,0.5,1")
    ap.add_argument("--n-inject", type=int, default=200)
    ap.add_argument("--horizon", type=int, default=240)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args(argv)

    tickers = list_db_tickers(args.db_dir) if args.tickers == ["all"] else [t.lower() for t in args.tickers]
    end_ts = _parse_ts(args.end)
    if args.command == "evaluate" and args.adapt_hl is None:
        args.adapt_hl = 120.0
    rows = []
    for t in tickers:
        try:
            r = analyse(args.db_dir, t, args.days, end_ts)
        except (SystemExit, sqlite3.Error, ValueError) as e:
            print(f"skipping {t}: {e}", file=sys.stderr)
            continue
        if args.command == "characterise":
            print_characterise(r)
            rows.append(summary_row(r))
        elif args.command == "filter":
            run_filter(r, args)
        else:
            run_evaluate(r, args)
        sys.stdout.flush()
    if rows:
        df = pd.DataFrame(rows)
        print("\nSUMMARY")
        with pd.option_context("display.width", 250, "display.max_columns", 50, "display.float_format", "{:.4g}".format):
            print(df[["ticker", "price_median", "zero_frac", "zero_after_zero", "d_sd_cents", "d_sd_bp", "d_excess_kurt", "d_excess_kurt_volnorm",
                      "acf1", "acf_abs1", "ar_se2_bp2", "ar_phi", "se_bp", "se_cents", "se_excess_bp", "su_bp", "su_cents", "q", "K", "scale_slope"]].to_string(index=False))
        if args.out:
            os.makedirs(args.out, exist_ok=True)
            fn = os.path.join(args.out, "characterise_summary.csv")
            df.to_csv(fn, index=False)
            print(f"wrote {fn}")


if __name__ == "__main__":
    main()
