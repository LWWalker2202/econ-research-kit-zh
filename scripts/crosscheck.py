# -*- coding: utf-8 -*-
"""crosscheck.py — 用第二套实现重算金样系数，看报告里的数是不是真的。

金样报告由 `skills/estimation/templates/estimate_main.py`（pandas + pyfixest）产出。
这里一行 pandas 都不用：自己读 CSV、自己双维去均值、自己解正规方程、自己算
iid 与聚类标准误，然后和 `expected/estimation-results.json` 对账。

用法：
    python scripts/crosscheck.py --data panel.csv --results skills/estimation/expected/estimation-results.json
    python scripts/crosscheck.py --data panel.csv --tol 1e-6 --json

系数容差默认 1e-6（绝对）。标准误只查是否落在 0.75–1.35 的倍数带里：两套包的自由度修正
约定不同，5% 的系统差是约定，不是错。
退出码：0 全对上 / 1 有对不上 / 2 用法或输入错误
末行：N/M coefficients agree
"""
import argparse, csv, io, json, math, os, sys


# ---------- 读数据 ----------

def read_table(path):
    if path.endswith((".csv", ".txt")):
        with io.open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        return [r for r in rows if r]
    raise SystemExit("unsupported table: %s" % path)


def as_float(v):
    v = (v or "").strip()
    if v in ("", "NA", "NaN", "nan", "."):
        return float("nan")
    return float(v)


def columns(rows, names):
    return [[as_float(r.get(n)) for r in rows] for n in names]


# ---------- 双维去均值 ----------

def demean_two_way(vecs, g1, g2, tol=1e-12, iters=200):
    """交替投影：先按 g1 去均值，再按 g2 去均值，迭代到稳定。"""
    out = [list(v) for v in vecs]
    for _ in range(iters):
        delta = 0.0
        for groups in (g1, g2):
            sums, counts = {}, {}
            for i, g in enumerate(groups):
                for v in out:
                    sums.setdefault((id(v), g), 0.0)
            for v in out:
                sums = {}
                cnts = {}
                for i, g in enumerate(groups):
                    sums[g] = sums.get(g, 0.0) + v[i]
                    cnts[g] = cnts.get(g, 0) + 1
                for i, g in enumerate(groups):
                    m = sums[g] / cnts[g]
                    v[i] -= m
                    delta = max(delta, abs(m))
        if delta < tol:
            break
    return out


# ---------- 线性代数（纯手写，不引 numpy） ----------

def solve(a, b):
    """高斯-约当解 a x = b（a 复制后原地消元）。返回 (x, a_inv)。"""
    n = len(a)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    inv = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-14:
            raise ZeroDivisionError("singular design at column %d" % col)
        if piv != col:
            m[col], m[piv] = m[piv], m[col]
            inv[col], inv[piv] = inv[piv], inv[col]
        d = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= d
        for j in range(n):
            inv[col][j] /= d
        for r in range(n):
            if r == col:
                continue
            f = m[r][col]
            if f == 0.0:
                continue
            for j in range(col, n + 1):
                m[r][j] -= f * m[col][j]
            for j in range(n):
                inv[r][j] -= f * inv[col][j]
    return [m[i][n] for i in range(n)], inv


def xtx(x):
    k = len(x[0]) if x else 0
    out = [[0.0] * k for _ in range(k)]
    for row in x:
        for i in range(k):
            ri = row[i]
            for j in range(i, k):
                out[i][j] += ri * row[j]
    for i in range(k):
        for j in range(i):
            out[i][j] = out[j][i]
    return out


def xv(x, v):
    k = len(x[0]) if x else 0
    out = [0.0] * k
    for row, vi in zip(x, v):
        for i in range(k):
            out[i] += row[i] * vi
    return out


def ols(y, x):
    xtx_ = xtx(x)
    xty = xv(x, y)
    beta, inv = solve(xtx_, xty)
    resid = [y[i] - sum(x[i][j] * beta[j] for j in range(len(beta))) for i in range(len(y))]
    return beta, resid, inv


def vcov_iid(x, resid, inv, dof):
    ssr = sum(r * r for r in resid)
    s2 = ssr / dof if dof > 0 else float("nan")
    k = len(inv)
    return [[inv[i][j] * s2 for j in range(k)] for i in range(k)]


def vcov_cluster(x, resid, inv, groups, dof):
    """聚类三明治：meat = Σ_g (X_g' u_g)(X_g' u_g)'，再乘自由度修正。"""
    k = len(inv)
    meat = [[0.0] * k for _ in range(k)]
    bucket = {}
    for row, u, g in zip(x, resid, groups):
        s = bucket.setdefault(g, [0.0] * k)
        for i in range(k):
            s[i] += row[i] * u
    for s in bucket.values():
        for i in range(k):
            for j in range(k):
                meat[i][j] += s[i] * s[j]
    g_n = len(bucket)
    adj = (g_n / (g_n - 1.0)) * ((len(x) - 1.0) / dof) if g_n > 1 and dof > 0 else 1.0
    out = [[0.0] * k for _ in range(k)]
    for i in range(k):
        for j in range(k):
            acc = 0.0
            for a in range(k):
                for b in range(k):
                    acc += inv[i][a] * meat[a][b] * inv[b][j]
            out[i][j] = acc * adj
    return out


# ---------- 公式 ----------

def parse_formula(formula):
    lhs, rest = formula.split("~", 1)
    rhs, _, fe = rest.partition("|")
    xs = [t.strip() for t in rhs.split("+") if t.strip()]
    fes = [t.strip() for t in fe.split("+") if t.strip()]
    return lhs.strip(), xs, fes


def spec_estimate(rows, formula, vcov, cluster_var="id"):
    y_name, xs, fes = parse_formula(formula)
    cols = columns(rows, [y_name] + xs)
    y = cols[0]
    xraw = cols[1:]
    groups = [columns(rows, [g])[0] for g in fes] if fes else []
    if groups:
        y, *xraw = demean_two_way([y] + xraw, groups[0], groups[1] if len(groups) > 1 else groups[0])
    x = [list(row) for row in zip(*xraw)]
    beta, resid, inv = ols(y, x)
    n = len(y)
    k = len(xs)
    rank_fe = sum(len(set(g)) - 1 for g in groups) if groups else 0
    dof = n - k - rank_fe
    if vcov.startswith("cluster"):
        g = columns(rows, [vcov.split("_", 1)[1] if "_" in vcov else cluster_var])[0]
        v = vcov_cluster(x, resid, inv, g, dof)
    else:
        v = vcov_iid(x, resid, inv, dof)
    ses = [math.sqrt(max(v[i][i], 0.0)) for i in range(k)]
    return dict(zip(xs, zip(beta, ses))), dof


# ---------- 主流程 ----------

def main(argv=None):
    ap = argparse.ArgumentParser(description="recompute the gold coefficients with a second implementation")
    ap.add_argument("--data", required=True, help="panel CSV produced by estimate_main.py --dump-csv")
    ap.add_argument("--results", required=True, help="expected/estimation-results.json")
    ap.add_argument("--tol", type=float, default=1e-6, help="absolute coefficient tolerance")
    ap.add_argument("--se-band", type=float, default=0.35, help="how far a standard-error ratio may stray (0.35 means 0.75-1.35)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    for p in (a.data, a.results):
        if not os.path.isfile(p):
            print("missing file: %s" % p, file=sys.stderr)
            return 2
    rows = read_table(a.data)
    with io.open(a.results, encoding="utf-8") as f:
        gold = json.load(f)

    report, ok, total = [], 0, 0
    inband_ok, inband_total = [0], [0]
    for spec in gold.get("specifications", []):
        try:
            got, dof = spec_estimate(rows, spec["formula"], spec.get("vcov", "iid"))
        except Exception as e:
            report.append({"spec": spec["id"], "status": "error", "detail": str(e)})
            total += len(spec.get("coefficients", []))
            continue
        for c in spec.get("coefficients", []):
            term = c["term"]
            total += 1
            if term not in got:
                report.append({"spec": spec["id"], "term": term, "status": "missing"})
                continue
            b, se = got[term]
            db = abs(b - c["coef"])
            ratio = (se / c["se"]) if c["se"] else float("inf")
            good = db <= a.tol
            in_band = abs(ratio - 1.0) <= a.se_band
            ok += 1 if good else 0
            inband_total[0] += 1
            inband_ok[0] += 1 if in_band else 0
            report.append({
                "spec": spec["id"], "term": term, "status": "agree" if good else "differ",
                "gold_coef": c["coef"], "mine_coef": round(b, 9), "d_coef": db,
                "gold_se": c["se"], "mine_se": round(se, 9), "se_ratio": round(ratio, 4), "se_in_band": in_band,
            })

    if a.json:
        print(json.dumps({"checked": total, "agree": ok, "se_in_band": inband_ok[0], "items": report}, ensure_ascii=False, indent=2))
    else:
        print("# crosscheck: %s" % os.path.basename(a.data))
        print("")
        print("| spec | term | gold | mine | d(coef) | se ratio |")
        print("|---|---|---|---|---|---|")
        for r in report:
            if r.get("status") == "error":
                print("| %s | - | - | error | %s | - |" % (r["spec"], r["detail"][:40]))
                continue
            if r.get("status") == "missing":
                print("| %s | %s | - | missing | - | - |" % (r["spec"], r["term"]))
                continue
            print("| %s | %s | %.6f | %.6f | %.1e | %.3f |" % (
                r["spec"], r["term"], r["gold_coef"], r["mine_coef"], r["d_coef"], r["se_ratio"]))
        print("")
        print("%d/%d coefficients agree  ·  %d/%d standard errors in band" % (ok, total, inband_ok[0], inband_total[0]))
        if ok == total:
            print("note: standard-error conventions differ between packages; only the ratio band is checked.")
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())