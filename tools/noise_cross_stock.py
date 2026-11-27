#!/usr/bin/env python3
"""Cross-stock structure of Torn City 1-minute price noise.

Answers: is the per-minute "fuzz" shared across all stocks or independent per
stock?  Reads the TornStonks Live per-ticker SQLite files (table ``m1``)
strictly read-only and reports:

  * gap / coverage statistics (returns are only formed between consecutive
    minutes, so gaps never create fake multi-minute returns)
  * cross-stock correlation of returns at lag 0 (and lags +-1) for 1, 5, 15
    and 60 minute horizons, plus PCA first-component variance share
  * whether stocks change price on the same minutes (zero-change fractions,
    co-occurrence vs. an independence baseline, synchronised minutes, by
    minute-of-hour / hour-of-day)
  * absolute-cent vs proportional noise scaling across price levels
  * lag-1 autocorrelation and Roll noise estimate per stock
  * common time-of-day / day-of-week volatility profile
  * optional stability check over several windows spread across history

Standalone: depends only on numpy, pandas, scipy (scipy optional).

Examples
--------
    python tools/noise_cross_stock.py --days 30
    python tools/noise_cross_stock.py --days 90 --out noise_report.md
    python tools/noise_cross_stock.py --days 30 --stability 8 --tickers ass,tcp,fhg
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_CANDIDATES = [
    REPO_ROOT / "db",
    # worktrees live at <repo>/.claude/worktrees/<name>; fall back to main checkout db
    REPO_ROOT.parent.parent.parent / "db",
]


# --------------------------------------------------------------------------- #
# Data loading (read-only)
# --------------------------------------------------------------------------- #
def default_db_dir() -> Path:
    for cand in DEFAULT_DB_CANDIDATES:
        if cand.is_dir() and any(cand.glob("db_*.db")):
            return cand
    return DEFAULT_DB_CANDIDATES[0]


def list_tickers(db_dir) -> list[str]:
    """Tickers that have a db_<ticker>.db file containing an m1 table."""
    out = []
    for p in sorted(Path(db_dir).glob("db_*.db")):
        t = p.stem[3:]
        try:
            con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
            ok = con.execute(
                "select 1 from sqlite_master where type='table' and name='m1'"
            ).fetchone()
            con.close()
        except sqlite3.Error:
            ok = None
        if ok:
            out.append(t)
    return out


def load_m1(db_dir, ticker, start_ts=None, end_ts=None) -> pd.Series:
    """Load m1 close prices for ``ticker`` as a Series indexed by UTC datetime.

    start_ts / end_ts are unix seconds (inclusive / exclusive). Read-only.
    """
    path = Path(db_dir) / f"db_{ticker.lower()}.db"
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        q = "select date, close from m1"
        cond, args = [], []
        if start_ts is not None:
            cond.append("date >= ?")
            args.append(int(start_ts))
        if end_ts is not None:
            cond.append("date < ?")
            args.append(int(end_ts))
        if cond:
            q += " where " + " and ".join(cond)
        q += " order by date"
        rows = con.execute(q, args).fetchall()
    finally:
        con.close()
    if not rows:
        return pd.Series(dtype=float, name=ticker)
    arr = np.asarray(rows, dtype=float)
    idx = pd.to_datetime(arr[:, 0].astype(np.int64), unit="s", utc=True)
    return pd.Series(arr[:, 1], index=idx, name=ticker.lower())


def max_ts(db_dir, tickers) -> int:
    best = 0
    for t in tickers:
        con = sqlite3.connect(f"file:{(Path(db_dir) / f'db_{t}.db').as_posix()}?mode=ro", uri=True)
        v = con.execute("select max(date) from m1").fetchone()[0]
        con.close()
        best = max(best, v or 0)
    return best


def load_panel(db_dir, tickers, start_ts, end_ts) -> pd.DataFrame:
    """Wide frame of closes on a complete 1-minute UTC grid (NaN = missing)."""
    cols = {t: load_m1(db_dir, t, start_ts, end_ts) for t in tickers}
    grid = pd.date_range(
        pd.to_datetime(start_ts // 60 * 60, unit="s", utc=True),
        pd.to_datetime((end_ts - 1) // 60 * 60, unit="s", utc=True),
        freq="1min",
    )
    df = pd.DataFrame({t: s.reindex(grid) for t, s in cols.items()}, index=grid)
    return df


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def offdiag(m: np.ndarray) -> np.ndarray:
    n = m.shape[0]
    return m[~np.eye(n, dtype=bool)]


def corr_summary(ret: pd.DataFrame, min_rows: int = 30) -> dict:
    """Correlation summary on rows where every stock has a return."""
    full = ret.dropna(how="any")
    if len(full) < min_rows:
        full = ret  # fall back to pairwise
        c = ret.corr(min_periods=min_rows).values
    else:
        c = np.corrcoef(full.values, rowvar=False)
    od = offdiag(c)
    od = od[np.isfinite(od)]
    if od.size == 0:
        return dict(rows=len(full))
    cc = np.nan_to_num(c, nan=0.0)
    np.fill_diagonal(cc, 1.0)
    ev = np.linalg.eigvalsh(cc)[::-1]
    n = c.shape[0]
    return dict(
        rows=len(full),
        mean=float(od.mean()),
        median=float(np.median(od)),
        p5=float(np.percentile(od, 5)),
        p95=float(np.percentile(od, 95)),
        min=float(od.min()),
        max=float(od.max()),
        frac_pos=float((od > 0).mean()),
        pc1_share=float(ev[0] / ev.sum()),
        pc1_null=1.0 / n,
        pc1_mp_null=float((1 + np.sqrt(n / max(len(full), 1))) ** 2 / n),
        pc2_share=float(ev[1] / ev.sum()),
        se_null=1.0 / np.sqrt(max(len(full), 1)),
    )


def lagged_mean_corr(ret: pd.DataFrame, lag: int) -> float:
    """Mean over ordered pairs i!=j of corr(r_i(t), r_j(t-lag))."""
    a = ret
    b = ret.shift(lag)
    z = lambda x: (x - x.mean()) / x.std()
    A, B = z(a), z(b)
    vals = []
    cols = list(ret.columns)
    for i in cols:
        for j in cols:
            if i == j:
                continue
            m = A[i].notna() & B[j].notna()
            if m.sum() > 100:
                vals.append(float(np.corrcoef(A[i][m], B[j][m])[0, 1]))
    return float(np.mean(vals)) if vals else float("nan")


def horizon_returns(px: pd.DataFrame, k: int, log: bool = True) -> pd.DataFrame:
    """Non-overlapping k-minute returns on the minute grid.

    Return over block [t, t+k] is only kept when both endpoints exist; for k=1
    this means only consecutive minutes are used.
    """
    sub = px.iloc[::k]
    if log:
        return np.log(sub).diff()
    return sub.diff()


def fmt_table(df: pd.DataFrame, floatfmt: str = "{:.4f}") -> str:
    """Render a DataFrame as a GitHub markdown table (no tabulate dependency)."""
    cols = [str(df.index.name or "")] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for idx, row in df.iterrows():
        cells = [str(idx)]
        for v in row.values:
            if isinstance(v, (float, np.floating)):
                cells.append(floatfmt.format(v) if np.isfinite(v) else "nan")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Analyses
# --------------------------------------------------------------------------- #
def analyse_gaps(px: pd.DataFrame) -> pd.DataFrame:
    n = len(px)
    present = px.notna()
    r_ok = present & present.shift(1, fill_value=False)
    rows = {}
    for t in px.columns:
        p = present[t].values
        # longest gap
        miss = ~p
        longest = 0
        if miss.any():
            d = np.diff(np.r_[0, miss.astype(int), 0])
            starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
            longest = int((ends - starts).max())
        rows[t] = dict(
            present=int(p.sum()),
            missing=int(miss.sum()),
            pct_missing=100.0 * miss.mean(),
            consecutive_returns=int(r_ok[t].sum()),
            longest_gap_min=longest,
        )
    out = pd.DataFrame(rows).T
    out.index.name = "ticker"
    return out


def analyse_correlation(px: pd.DataFrame, horizons=(1, 5, 15, 60)) -> pd.DataFrame:
    rows = {}
    for k in horizons:
        for kind, log in (("log", True), ("cents", False)):
            r = horizon_returns(px, k, log=log)
            s = corr_summary(r)
            rows[f"{k}m {kind}"] = s
    out = pd.DataFrame(rows).T
    out.index.name = "horizon"
    return out


def analyse_lead_lag(px: pd.DataFrame) -> dict:
    r = np.log(px).diff()
    return {f"lag{l:+d}": lagged_mean_corr(r, l) for l in (-1, 1, 2)}


def analyse_change_cooccurrence(px: pd.DataFrame):
    d = px.diff()
    valid = d.notna()
    ch = (d != 0) & valid
    allv = valid.all(axis=1)
    chv = ch[allv]
    n_stocks = px.shape[1]
    p_change = chv.mean()  # per-stock prob of change on a fully-observed minute
    count = chv.sum(axis=1)
    # independence baseline: Poisson-binomial
    mu0 = p_change.sum()
    var0 = (p_change * (1 - p_change)).sum()
    phi = np.corrcoef(chv.values.astype(float), rowvar=False)
    od = offdiag(phi)
    od = od[np.isfinite(od)]
    # sign agreement among changing pairs
    sgn = np.sign(d[allv]).values
    pos = (sgn > 0).sum(axis=1)
    neg = (sgn < 0).sum(axis=1)
    tot = pos + neg
    m = tot >= 10
    frac_up = pos[m] / tot[m]
    # simulated independent baseline for fraction-up dispersion
    rng = np.random.default_rng(0)
    sim = rng.binomial(tot[m], 0.5) / tot[m]

    # distribution of number of stocks changing
    hist = count.value_counts().sort_index()
    rng2 = np.random.default_rng(1)
    sim_counts = (rng2.random((min(len(chv), 200000), n_stocks)) < p_change.values).sum(axis=1)
    sim_hist = pd.Series(sim_counts).value_counts().sort_index() / len(sim_counts)

    idx = chv.index
    by_moh = count.groupby(idx.minute).mean()
    by_hod = count.groupby(idx.hour).mean()

    summary = dict(
        fully_observed_minutes=int(allv.sum()),
        mean_stocks_changing=float(count.mean()),
        indep_mean=float(mu0),
        var_stocks_changing=float(count.var()),
        indep_var=float(var0),
        var_ratio=float(count.var() / var0),
        frac_all_change=float((count == n_stocks).mean()),
        frac_none_change=float((count == 0).mean()),
        indep_frac_all=float(np.prod(p_change)),
        indep_frac_none=float(np.prod(1 - p_change)),
        phi_mean=float(od.mean()),
        phi_median=float(np.median(od)),
        phi_max=float(od.max()),
        frac_up_std=float(frac_up.std()),
        frac_up_std_indep=float(sim.std()),
        moh_range=(float(by_moh.min()), float(by_moh.max())),
        hod_range=(float(by_hod.min()), float(by_hod.max())),
    )
    zero_frac = 1 - (ch.sum() / valid.sum())
    dist = pd.DataFrame({"observed": hist / hist.sum(), "independent_sim": sim_hist}).fillna(0)
    dist.index.name = "n_changing"
    return summary, zero_frac, dist, by_moh, by_hod


def analyse_jumps(px: pd.DataFrame, z: float = 6.0):
    """Count minutes where many stocks simultaneously have |r| > z * robust sd."""
    r = np.log(px).diff()
    mad = (r - r.median()).abs().median() * 1.4826
    sd = r.std()
    scale = mad.where(mad > 0, sd)
    big = (r.abs() > z * scale) & r.notna()
    n = big.sum(axis=1)
    top = n[n > 0].sort_values(ascending=False).head(10)
    per_stock = big.sum()
    thresholds = {f">={k}": int((n >= k).sum()) for k in (1, 2, 3, 5, 10, 18, 30)}
    return per_stock, thresholds, top


def analyse_scaling(px: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = px.diff()
    r = np.log(px).diff()
    rows = {}
    for t in px.columns:
        dc = (d[t].dropna() * 100.0).round(6)  # cents (round away float noise)
        rr = r[t].dropna() * 100.0  # percent
        nz = dc[dc.round(6) != 0]
        rows[t] = dict(
            mean_price=float(px[t].mean()),
            sd_cents=float(dc.std()),
            mad_cents=float(dc.abs().mean()),
            sd_pct=float(rr.std()),
            zero_frac=float((dc.round(6) == 0).mean()),
            frac_1c_of_moves=float((nz.abs().round(6) == 1).mean()) if len(nz) else np.nan,
            median_abs_move_c=float(nz.abs().median()) if len(nz) else np.nan,
        )
    tab = pd.DataFrame(rows).T.sort_values("mean_price")
    tab.index.name = "ticker"
    lp = np.log(tab["mean_price"])
    out = {}
    for col in ("sd_cents", "sd_pct", "mad_cents"):
        ly = np.log(tab[col])
        slope, icpt = np.polyfit(lp, ly, 1)
        out[f"loglog_slope_{col}_vs_price"] = float(slope)
        out[f"spearman_{col}_vs_price"] = float(
            pd.Series(tab[col].values).corr(pd.Series(tab["mean_price"].values), method="spearman")
        )
    out["cv_sd_cents"] = float(tab["sd_cents"].std() / tab["sd_cents"].mean())
    out["cv_sd_pct"] = float(tab["sd_pct"].std() / tab["sd_pct"].mean())
    return tab, out


def analyse_autocorr(px: pd.DataFrame) -> pd.DataFrame:
    d = px.diff() * 100.0  # cents, consecutive minutes only
    r = np.log(px).diff() * 100.0
    rows = {}
    for t in px.columns:
        x, xl = d[t], d[t].shift(1)
        m = x.notna() & xl.notna()
        cov_c = float(np.cov(x[m], xl[m])[0, 1])
        rho1 = float(np.corrcoef(x[m], xl[m])[0, 1])
        y, yl = r[t], r[t].shift(1)
        my = y.notna() & yl.notna()
        cov_p = float(np.cov(y[my], yl[my])[0, 1])
        rho2 = float(r[t].autocorr(2))
        rows[t] = dict(
            mean_price=float(px[t].mean()),
            rho1=rho1,
            rho2=rho2,
            roll_sigma_e_cents=np.sqrt(-cov_c) if cov_c < 0 else np.nan,
            roll_sigma_e_pct=np.sqrt(-cov_p) if cov_p < 0 else np.nan,
            sd_cents=float(x[m].std()),
        )
    tab = pd.DataFrame(rows).T.sort_values("mean_price")
    tab.index.name = "ticker"
    # share of m1 variance attributable to noise under Roll model: 2 sigma_e^2 / var
    tab["noise_var_share"] = 2 * tab["roll_sigma_e_cents"] ** 2 / tab["sd_cents"] ** 2
    return tab


def analyse_seasonality(px: pd.DataFrame):
    r = np.log(px).diff().abs()
    norm = r / r.mean()  # each stock normalised to its own mean |r|
    hod = norm.groupby(norm.index.hour).mean()
    dow = norm.groupby(norm.index.dayofweek).mean()
    moh = norm.groupby(norm.index.minute).mean()

    def profile_stats(prof: pd.DataFrame) -> dict:
        c = np.corrcoef(prof.values, rowvar=False)
        od = offdiag(c)
        avg = prof.mean(axis=1)
        return dict(
            mean_cross_profile_corr=float(np.nanmean(od)),
            avg_profile_min=float(avg.min()),
            avg_profile_max=float(avg.max()),
            argmin=int(avg.idxmin()),
            argmax=int(avg.idxmax()),
        )

    return (
        {"hour_of_day": profile_stats(hod), "day_of_week": profile_stats(dow), "minute_of_hour": profile_stats(moh)},
        hod.mean(axis=1),
        dow.mean(axis=1),
        moh.mean(axis=1),
    )


def headline(px: pd.DataFrame) -> dict:
    """Small set of metrics for the stability check."""
    r1 = np.log(px).diff()
    c1 = corr_summary(r1)
    c60 = corr_summary(horizon_returns(px, 60))
    d = px.diff()
    allv = d.notna().all(axis=1)
    ch = (d[allv] != 0)
    cnt = ch.sum(axis=1)
    p = ch.mean()
    var0 = (p * (1 - p)).sum()
    ac = [r1[t].autocorr(1) for t in px.columns]
    sdc = (d * 100).std()
    sdp = (r1 * 100).std()
    mp = px.mean()
    slope_c = np.polyfit(np.log(mp), np.log(sdc), 1)[0]
    return dict(
        m1_corr_mean=c1["mean"],
        m1_pc1=c1["pc1_share"],
        h1_corr_mean=c60["mean"],
        h1_pc1=c60["pc1_share"],
        zero_frac_mean=float(1 - p.mean()),
        change_count_var_ratio=float(cnt.var() / var0) if var0 > 0 else np.nan,
        rho1_median=float(np.nanmedian(ac)),
        sd_cents_median=float(sdc.median()),
        sd_pct_median=float(sdp.median()),
        slope_sdcents_vs_price=float(slope_c),
        missing_pct=float(100 * px.isna().values.mean()),
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db-dir", default=None, help="directory with db_<ticker>.db files")
    ap.add_argument("--days", type=float, default=30, help="window length in days (default 30)")
    ap.add_argument("--end", default=None, help="window end (UTC, e.g. 2025-06-01); default = latest data")
    ap.add_argument("--tickers", default=None, help="comma-separated tickers (default: all)")
    ap.add_argument("--stability", type=int, default=0,
                    help="also compute headline metrics in N windows of --days spread across history")
    ap.add_argument("--horizons", default="1,5,15,60",
                    help="comma-separated return horizons in minutes for the correlation table")
    ap.add_argument("--jump-z", type=float, default=6.0, help="robust z threshold for jump detection")
    ap.add_argument("--out", default=None,
                    help="write report to this path (.md = markdown report; .csv = per-stock table)")
    args = ap.parse_args(argv)

    db_dir = Path(args.db_dir) if args.db_dir else default_db_dir()
    tickers = [t.strip().lower() for t in args.tickers.split(",")] if args.tickers else list_tickers(db_dir)
    tickers = [t for t in tickers if (db_dir / f"db_{t}.db").exists()]
    if len(tickers) < 2:
        print(f"need >=2 tickers, found {tickers} in {db_dir}", file=sys.stderr)
        return 2

    end_ts = int(pd.Timestamp(args.end, tz="UTC").timestamp()) if args.end else max_ts(db_dir, tickers) + 60
    start_ts = int(end_ts - args.days * 86400)

    t0 = time.time()
    px = load_panel(db_dir, tickers, start_ts, end_ts)
    out = []
    P = lambda s="": out.append(s)

    P(f"# Cross-stock m1 noise report")
    P()
    P(f"- db dir: `{db_dir}`")
    P(f"- tickers ({len(tickers)}): {', '.join(tickers)}")
    P(f"- window: {px.index[0]} -> {px.index[-1]} ({args.days:g} days, {len(px)} grid minutes)")
    P(f"- load time: {time.time() - t0:.1f}s")
    P()

    gaps = analyse_gaps(px)
    P("## Gaps / coverage")
    P(f"Rows on full minute grid: {len(px)}. Minutes where all stocks present: "
      f"{int(px.notna().all(axis=1).sum())}. Mean % missing: {gaps['pct_missing'].mean():.3f}%. "
      f"Max longest gap: {int(gaps['longest_gap_min'].max())} min.")
    P("Returns are formed only between consecutive grid minutes (both present); a gap yields NaN, not a multi-minute return.")
    P()
    P(fmt_table(gaps.astype(float).describe().T, "{:.2f}"))
    P()

    P("## Cross-stock correlation of returns (lag 0)")
    cs = analyse_correlation(px, tuple(int(h) for h in args.horizons.split(",")))
    P(fmt_table(cs, "{:.4f}"))
    P()
    P("`se_null` = 1/sqrt(rows): approximate std of a single pairwise correlation under independence. "
      "`pc1_null` = 1/N: PC1 share for an infinite sample of uncorrelated stocks; "
      "`pc1_mp_null` = (1+sqrt(N/T))^2/N: Marchenko-Pastur upper edge, i.e. the PC1 share expected "
      "from pure sampling noise with T rows and N independent stocks.")
    P()
    ll = analyse_lead_lag(px)
    P("Mean cross-stock correlation corr(r_i(t), r_j(t-lag)) on m1 log returns: "
      + ", ".join(f"{k}={v:.4f}" for k, v in ll.items()))
    P()

    P("## Do stocks change on the same minutes?")
    summ, zero_frac, dist, by_moh, by_hod = analyse_change_cooccurrence(px)
    for k, v in summ.items():
        P(f"- {k}: {v if not isinstance(v, float) else round(v, 5)}")
    P()
    P("Per-stock fraction of consecutive-minute pairs with zero price change: "
      f"mean={zero_frac.mean():.4f}, min={zero_frac.min():.4f} ({zero_frac.idxmin()}), "
      f"max={zero_frac.max():.4f} ({zero_frac.idxmax()})")
    P()
    P("Distribution of number of stocks changing per fully-observed minute (observed vs independent simulation):")
    P()
    P(fmt_table(dist, "{:.5f}"))
    P()
    P("Mean # stocks changing by minute-of-hour (UTC) - min/max listed above; full by hour-of-day:")
    P()
    P(fmt_table(by_hod.to_frame("mean_n_changing").rename_axis("hour_utc"), "{:.3f}"))
    P()

    P("## Simultaneous jumps")
    per_stock, thr, top = analyse_jumps(px, args.jump_z)
    P(f"Jump = |log return| > {args.jump_z} x robust (MAD) sd. Total jumps per stock: "
      f"median={int(per_stock.median())}, max={int(per_stock.max())} ({per_stock.idxmax()}).")
    P("Minutes with at least k stocks jumping simultaneously: " + ", ".join(f"{k}: {v}" for k, v in thr.items()))
    P()
    if len(top):
        P("Top minutes by number of simultaneous jumps:")
        P()
        P(fmt_table(top.to_frame("n_jumping").rename_axis("minute_utc"), "{:.0f}"))
    P()

    P("## Absolute cents vs proportional noise")
    sc_tab, sc = analyse_scaling(px)
    for k, v in sc.items():
        P(f"- {k}: {v:.4f}")
    P()
    P("(log-log slope of sd vs price: 0 => constant in cents, 1 => proportional to price)")
    P()
    P(fmt_table(sc_tab, "{:.4f}"))
    P()

    P("## Lag-1 autocorrelation and Roll noise estimate")
    ac = analyse_autocorr(px)
    P(f"rho1: median={ac['rho1'].median():.4f}, min={ac['rho1'].min():.4f}, max={ac['rho1'].max():.4f}, "
      f"all negative={bool((ac['rho1'] < 0).all())}")
    P(f"Roll sigma_e (cents): median={ac['roll_sigma_e_cents'].median():.4f}, "
      f"IQR=[{ac['roll_sigma_e_cents'].quantile(.25):.4f}, {ac['roll_sigma_e_cents'].quantile(.75):.4f}]; "
      f"(%): median={ac['roll_sigma_e_pct'].median():.5f}")
    P()
    P(fmt_table(ac, "{:.4f}"))
    P()

    P("## Common time-of-day / day-of-week volatility pattern")
    seas, hod, dow, moh = analyse_seasonality(px)
    for k, v in seas.items():
        P(f"- {k}: " + ", ".join(f"{a}={b:.4f}" if isinstance(b, float) else f"{a}={b}" for a, b in v.items()))
    P()
    P("Average normalised |r| by hour (UTC):")
    P()
    P(fmt_table(hod.to_frame("rel_abs_ret").rename_axis("hour_utc"), "{:.4f}"))
    P()
    P("Average normalised |r| by day of week (0=Mon):")
    P()
    P(fmt_table(dow.to_frame("rel_abs_ret").rename_axis("dow"), "{:.4f}"))
    P()

    if args.stability > 0:
        P("## Stability across history")
        # earliest date common to all tickers
        earliest = 0
        for t in tickers:
            con = sqlite3.connect(f"file:{(db_dir / f'db_{t}.db').as_posix()}?mode=ro", uri=True)
            earliest = max(earliest, con.execute("select min(date) from m1").fetchone()[0])
            con.close()
        ends = np.linspace(earliest + args.days * 86400, end_ts, args.stability).astype(int)
        rows = {}
        for e in ends:
            s = int(e - args.days * 86400)
            p2 = load_panel(db_dir, tickers, s, int(e))
            # drop tickers with almost no data in window
            p2 = p2.loc[:, p2.notna().mean() > 0.5]
            key = pd.to_datetime(s, unit="s").strftime("%Y-%m-%d")
            try:
                rows[key] = headline(p2)
                rows[key]["n_tickers"] = p2.shape[1]
            except Exception as exc:  # pragma: no cover
                print(f"window {key} failed: {exc}", file=sys.stderr)
        st = pd.DataFrame(rows).T
        st.index.name = "window_start"
        P(fmt_table(st, "{:.4f}"))
        P()

    report = "\n".join(out)
    print(report)
    if args.out:
        o = Path(args.out)
        if o.suffix.lower() == ".csv":
            merged = sc_tab.join(ac.drop(columns=["mean_price", "sd_cents"]), how="outer").join(gaps)
            merged.to_csv(o)
        else:
            o.write_text(report, encoding="utf-8")
        print(f"\nwrote {o}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
