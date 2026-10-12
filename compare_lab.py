"""
比べて確かめる ─ 「測る・比べる・グラフにする・自分で判断する」の計算部品

pages/3_⚖️_比べて確かめる探究.py から呼び出します。画面を持たない純粋な関数だけを置き、
`python compare_lab.py` で自己チェック（assert）が走ります。

考え方（生徒向けの言い方 ↔ 研究での言い方）
  - くじで区を分ける            ↔ ランダム割り付け（RCT）
  - くじを引いた単位で数える    ↔ 割り付け単位（列）での集計。株は同じ列の中で似るので、株を独立に数えない
  - くじを引き直しても出る差か  ↔ 並べ替え検定（permutation test）
  - 差の幅                      ↔ ブートストラップ信頼区間
  - すでにあるデータでの比較    ↔ 差の差（DiD）。くじで配られていないので、選ばれ方の偏りが残る
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TREAT = "寒さに当てる区"
CONTROL = "覆いをかける区"
GROUPS = (TREAT, CONTROL)

BRIX_COLS = ["測定日", "列", "区", "株", "糖度"]
DID_COLS = ["集落", "年", "交付金", "経営耕地_ha"]


# ─────────────────────────────────────────────
# ① 測る：くじで列を区に割り振る
# ─────────────────────────────────────────────
def assign_rows(n_rows: int, seed: int, groups: tuple[str, str] = GROUPS) -> pd.DataFrame:
    """列 1..n_rows を、半分ずつ2区にくじで割り振る（同じ seed なら同じ結果）。

    n_rows が奇数のときは、余りの1列を処置側に入れる。
    """
    if n_rows < 2:
        raise ValueError("列は2本以上必要です")
    rng = np.random.default_rng(seed)
    n_treat = (n_rows + 1) // 2
    labels = np.array([groups[0]] * n_treat + [groups[1]] * (n_rows - n_treat))
    rng.shuffle(labels)
    return pd.DataFrame({"列": np.arange(1, n_rows + 1), "区": labels})


def sample_brix(seed: int = 2026) -> pd.DataFrame:
    """架空の糖度データ（実測ではありません）。8列×各列3株×3回（寒さに当てて0・7・14日）。"""
    rng = np.random.default_rng(seed)
    plan = assign_rows(8, seed)
    row_effect = rng.normal(0, 0.5, size=8)          # 列ごとの土・日当たりの違い
    days = {"2027-01-08": 0, "2027-01-15": 7, "2027-01-22": 14}
    rows = []
    for date, d in days.items():
        for _, r in plan.iterrows():
            gain = 0.22 * d if r["区"] == TREAT else 0.04 * d
            for k in range(1, 4):
                brix = 7.0 + gain + row_effect[r["列"] - 1] + rng.normal(0, 0.6)
                rows.append((date, int(r["列"]), r["区"], k, round(float(brix), 1)))
    return pd.DataFrame(rows, columns=BRIX_COLS)


def normalize_brix(df: pd.DataFrame) -> pd.DataFrame:
    out = df.reindex(columns=BRIX_COLS).copy()
    out["測定日"] = pd.to_datetime(out["測定日"], errors="coerce").dt.date
    out["列"] = pd.to_numeric(out["列"], errors="coerce").astype("Int64")
    out["株"] = pd.to_numeric(out["株"], errors="coerce").astype("Int64")
    out["糖度"] = pd.to_numeric(out["糖度"], errors="coerce")
    out["区"] = out["区"].astype("string").str.strip()
    return out


def problems_brix(df: pd.DataFrame, lo: float = 0.0, hi: float = 30.0) -> pd.DataFrame:
    """記入漏れ・ありえない値・区の取り違え（同じ列が2つの区に出る）を一覧にする。"""
    issues = []
    for i, r in df.iterrows():
        if pd.isna(r["測定日"]) or pd.isna(r["列"]) or pd.isna(r["糖度"]):
            issues.append((i, "記入漏れ"))
        elif not lo <= r["糖度"] <= hi:
            issues.append((i, f"糖度が {lo}〜{hi} の外"))
        if pd.notna(r["区"]) and r["区"] not in GROUPS:
            issues.append((i, f"区の名前が「{TREAT}／{CONTROL}」でない"))
    mixed = df.dropna(subset=["列", "区"]).groupby("列")["区"].nunique()
    for col in mixed[mixed > 1].index:
        for i in df.index[df["列"] == col]:
            issues.append((i, "同じ列が2つの区に入っている（くじの記録と照合）"))
    return pd.DataFrame(issues, columns=["行", "内容"]).drop_duplicates()


# ─────────────────────────────────────────────
# ② 比べる：列ごとにまとめてから比べる
# ─────────────────────────────────────────────
def row_means(df: pd.DataFrame) -> pd.DataFrame:
    """株 → 列の平均にまとめる（くじを引いた単位で数える）。"""
    d = df.dropna(subset=["列", "区", "糖度"])
    return (d.groupby(["測定日", "列", "区"], as_index=False)
              .agg(糖度=("糖度", "mean"), 株数=("糖度", "size")))


@dataclass(frozen=True)
class Comparison:
    n_treat: int            # 列の数
    n_control: int
    mean_treat: float
    mean_control: float
    diff: float             # 処置 − 対照
    ci_low: float
    ci_high: float
    p_value: float          # 両側、並べ替え検定
    n_perm: int


def compare(rm: pd.DataFrame, n_perm: int = 5000, n_boot: int = 5000, seed: int = 0) -> Comparison:
    """1回の測定日分の列平均（row_means の1日分）で、2区を比べる。"""
    a = rm.loc[rm["区"] == TREAT, "糖度"].to_numpy(float)
    b = rm.loc[rm["区"] == CONTROL, "糖度"].to_numpy(float)
    if len(a) < 2 or len(b) < 2:
        raise ValueError("各区に2列以上のデータが必要です")
    rng = np.random.default_rng(seed)
    obs = a.mean() - b.mean()

    pooled = np.concatenate([a, b])
    na = len(a)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        if abs(pooled[:na].mean() - pooled[na:].mean()) >= abs(obs) - 1e-12:
            hits += 1
    p = (hits + 1) / (n_perm + 1)

    boots = (rng.choice(a, (n_boot, len(a))).mean(axis=1)
             - rng.choice(b, (n_boot, len(b))).mean(axis=1))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return Comparison(len(a), len(b), float(a.mean()), float(b.mean()), float(obs),
                      float(lo), float(hi), float(p), n_perm)


def compare_by_date(df: pd.DataFrame, **kw) -> pd.DataFrame:
    """測定日ごとに compare() を回した表。"""
    rm = row_means(df)
    out = []
    for date, g in rm.groupby("測定日"):
        try:
            c = compare(g, **kw)
        except ValueError:
            continue
        out.append({"測定日": date, f"{TREAT}_平均": c.mean_treat, f"{CONTROL}_平均": c.mean_control,
                    "差": c.diff, "差_下限95": c.ci_low, "差_上限95": c.ci_high,
                    "p値": c.p_value, "列数": f"{c.n_treat}＋{c.n_control}"})
    return pd.DataFrame(out)


def naive_plant_count(df: pd.DataFrame, date) -> int:
    """株を独立に数えた場合の n（列でまとめないと、データが多く見えてしまうことを示す用）。"""
    return int(df[(df["測定日"] == date) & df["糖度"].notna()].shape[0])


# ─────────────────────────────────────────────
# ④ 判断する：目標糖度に届く最初の日
# ─────────────────────────────────────────────
def first_date_reaching(rm: pd.DataFrame, group: str, target: float, strict: bool) -> object:
    """区の列平均が目標に届いた最初の測定日。strict=True なら「いちばん低い列でも届いた日」。"""
    g = rm[rm["区"] == group].groupby("測定日")["糖度"]
    stat = g.min() if strict else g.mean()
    ok = stat[stat >= target]
    return ok.index.min() if not ok.empty else None


# ─────────────────────────────────────────────
# 発展：すでにあるデータで比べる（差の差 DiD）
# ─────────────────────────────────────────────
def sample_did(seed: int = 7) -> pd.DataFrame:
    """架空の集落データ（実在の集落・数値ではありません）。

    交付金を受けた集落ほど条件が厳しく、もともと耕地が減りやすい、という選ばれ方の偏りを入れてある。
    """
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(1, 25):
        steep = rng.uniform(0, 1)                       # 傾斜のきつさ（見えない条件）
        treated = int(steep + rng.normal(0, 0.2) > 0.55)
        base = rng.uniform(8, 30)
        trend = -0.10 * steep - 0.02                    # 5年での減り方（傾斜で大きい）
        effect = 0.04 if treated else 0.0               # 交付金の効果（架空の真値：+4ポイント）
        y2025 = base * (1 + trend + effect + rng.normal(0, 0.02))
        rows.append((f"集落{i:02d}", 2020, treated, round(base, 1)))
        rows.append((f"集落{i:02d}", 2025, treated, round(y2025, 1)))
    return pd.DataFrame(rows, columns=DID_COLS)


def normalize_did(df: pd.DataFrame) -> pd.DataFrame:
    out = df.reindex(columns=DID_COLS).copy()
    out["集落"] = out["集落"].astype("string").str.strip()
    out["年"] = pd.to_numeric(out["年"], errors="coerce").astype("Int64")
    out["交付金"] = pd.to_numeric(out["交付金"], errors="coerce").astype("Int64")
    out["経営耕地_ha"] = pd.to_numeric(out["経営耕地_ha"], errors="coerce")
    return out.dropna()


def did(df: pd.DataFrame, pre: int, post: int) -> dict:
    """集落ごとの変化率（post/pre − 1）を、交付金あり／なしで比べる。

    面積の大きさが集落で大きく違うため、差ではなく変化率で比べる。
    """
    wide = df.pivot_table(index=["集落", "交付金"], columns="年", values="経営耕地_ha").dropna()
    if pre not in wide.columns or post not in wide.columns:
        raise ValueError(f"{pre}年と{post}年の両方がある集落が必要です")
    wide = wide[wide[pre] > 0].reset_index()
    wide["変化率"] = wide[post] / wide[pre] - 1
    g = wide.groupby("交付金")["変化率"]
    if not {0, 1} <= set(g.groups):
        raise ValueError("交付金あり（1）となし（0）の両方の集落が必要です")
    m = g.mean()
    return {
        "table": wide,
        "change_treated": float(m[1]),
        "change_control": float(m[0]),
        "did": float(m[1] - m[0]),
        "pre_treated": float(wide.loc[wide["交付金"] == 1, pre].mean()),
        "pre_control": float(wide.loc[wide["交付金"] == 0, pre].mean()),
        "n_treated": int((wide["交付金"] == 1).sum()),
        "n_control": int((wide["交付金"] == 0).sum()),
    }


# ─────────────────────────────────────────────
# 自己チェック
# ─────────────────────────────────────────────
if __name__ == "__main__":
    a1, a2 = assign_rows(8, 42), assign_rows(8, 42)
    assert a1.equals(a2), "同じ seed なら同じくじ"
    assert (a1["区"] == TREAT).sum() == 4 and (a1["区"] == CONTROL).sum() == 4
    assert (assign_rows(7, 1)["区"] == TREAT).sum() == 4

    s = normalize_brix(sample_brix())
    assert len(s) == 8 * 3 * 3 and problems_brix(s).empty
    rm = row_means(s)
    assert (rm["株数"] == 3).all() and len(rm) == 8 * 3

    tab = compare_by_date(s, n_perm=2000, n_boot=2000)
    first, last = tab.iloc[0], tab.iloc[-1]
    assert last["差"] > first["差"], "寒さに当てる日数が長いほど差が開く（架空データの設計）"
    assert last["差_下限95"] > 0 and last["p値"] < 0.05
    assert first["差_下限95"] < 0 < first["差_上限95"], "0日目は差がないはず"

    bad = s.copy()
    bad.loc[0, "糖度"] = 99
    bad.loc[1, "区"] = CONTROL if bad.loc[1, "区"] == TREAT else TREAT
    msgs = " ".join(problems_brix(bad)["内容"])
    assert "外" in msgs and "2つの区" in msgs

    d = did(normalize_did(sample_did()), 2020, 2025)
    assert d["n_treated"] > 0 and d["n_control"] > 0
    assert d["pre_treated"] != d["pre_control"]
    # 選ばれ方の偏りがあるので、DiD は架空の真値（+0.04）からずれる
    assert abs(d["did"] - 0.04) > 0.005, d["did"]
    print("compare_lab: all checks passed")
    print(tab.round(2).to_string(index=False))
    print(f"DiD = {d['did']:+.3f}（架空の真値 +0.040）")
