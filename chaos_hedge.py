"""
chaos_hedge.py ─ カオスヘッジ（悪性インフレ・供給ショックへの家計の備え）の計算部品

行動原則（3段）:
  ① 作る   … 自給で「市場に依存しない部分」を増やす（支出回避）
  ② 売る   … 余った分だけを売って流動性（現金）を得る
  ③ 換える … 得た現金は持ち続けず、早めに実物（種・資材・道具・土地・技能・信頼）に換える

根拠にしている考え方（教材・研究に書くときの用語）:
  - 実質価値 = 名目 ÷ 物価指数（インフレ下で現金の実質価値は下がる）
  - 実物資産の分散度 = 1 − HHI（ハーフィンダール指数。調達先集中度と同じ式）
  - 先行事例: 1990年代ロシアの家庭菜園（ダーチャ）、戦後日本 1945〜49年
    （Seeth et al. 1998 World Development 26(9); Pallot & Nefedova 2007）
    → ダーチャの主な価値は「売上」ではなく「買わずに済んだこと（支出回避）」だった

⚠️ 教育用の単純化モデルです。投資・資産運用の助言ではありません。
   生の野菜の直売は原則許可不要ですが、加工品（パン等）は営業許可、路上販売は道路使用許可が要ります。
   硬貨の鋳つぶしは貨幣損傷等取締法で禁止されています。

Streamlit に依存しない純粋関数だけを置く（pages/4_自給家計簿.py・pages/income_structure_tab.py から使う）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ───────────────────────── 定数 ─────────────────────────
# インフレのシナリオ（年率）。数値は授業・判断用の仮置き
SCENARIOS: dict[str, float] = {
    "平時（年2%）": 0.02,
    "高インフレ（年10%）": 0.10,
    "悪性インフレ（年50%）": 0.50,
    "ハイパー（年300%）": 3.00,
}

# 実物資産の種類と年あたりの減耗率（使う・傷む・忘れる・疎遠になる分）。仮置き
ASSET_KINDS: dict[str, float] = {
    "種": 0.50,        # 次の作で使えば収穫に化けるが、保存すると発芽率が落ちる
    "資材": 0.30,      # 肥料・資材・燃料・保存容器など（消耗する）
    "道具": 0.12,      # 農具・機械・調理器具（8年程度で更新）
    "土地": 0.00,      # 農地・果樹（手入れを続ける前提）
    "技能": 0.05,      # 講習・資格・技術（使い続ければほぼ減らない）
    "信頼": 0.10,      # 取引先・仲間・地域との関係（手入れを怠ると目減り）
}

SALES_COLS = ["日付", "品目", "数量", "単位", "売上(円)", "販路"]
CONVERT_COLS = ["日付", "種類", "内容", "金額(円)"]
CHANNELS = ["直売所", "知人", "契約先", "物々交換", "その他"]


# ───────────────────────── 計算 ─────────────────────────
def cash_real_value(nominal: float, pi: float, years: np.ndarray | float) -> np.ndarray:
    """現金で持ち続けた場合の実質価値（物価で割り戻す）。"""
    return nominal / (1.0 + pi) ** np.asarray(years, dtype=float)


def asset_real_value(amount: float, decay: float, years: np.ndarray | float) -> np.ndarray:
    """実物に換えた場合の実質価値（物価には連動し、減耗だけ目減りする）。"""
    return amount * (1.0 - decay) ** np.asarray(years, dtype=float)


def hold_vs_convert(amount: float, pi: float, kind: str = "道具", months: int = 24) -> pd.DataFrame:
    """同じ売上を「現金で持つ」か「実物に換える」かで、実質価値の推移を比べる。"""
    t = np.arange(months + 1) / 12.0
    return pd.DataFrame({
        "月": np.arange(months + 1),
        "現金で持つ": cash_real_value(amount, pi, t),
        f"{kind}に換える": asset_real_value(amount, ASSET_KINDS[kind], t),
    }).set_index("月")


def idle_cash_loss(sales: pd.DataFrame, conv: pd.DataFrame, pi: float) -> dict:
    """
    売上を実物に換えるまでの「現金の滞留」と、その間にインフレで失う実質額を日次で見積もる。
    滞留残高 = 累計売上 − 累計実物化（負なら0）。日次の目減り率 = (1+pi)^(1/365) − 1。
    """
    s = _daily(sales, "売上(円)")
    c = _daily(conv, "金額(円)")
    if s.empty:
        return {"days": 0, "avg_idle": 0.0, "loss": 0.0, "ratio": 0.0, "lag_days": None}
    start = min(s.index.min(), c.index.min()) if not c.empty else s.index.min()
    end = max(s.index.max(), c.index.max()) if not c.empty else s.index.max()
    idx = pd.date_range(start, end, freq="D")
    cum_s = s.reindex(idx, fill_value=0).cumsum()
    cum_c = c.reindex(idx, fill_value=0).cumsum() if not c.empty else pd.Series(0.0, index=idx)
    idle = (cum_s - cum_c).clip(lower=0)
    daily = (1.0 + pi) ** (1 / 365) - 1
    total_sales = float(s.sum())
    return {
        "days": len(idx),
        "avg_idle": float(idle.mean()),
        "loss": float((idle * daily).sum()),
        "ratio": float(min(cum_c.iloc[-1], total_sales) / total_sales) if total_sales else 0.0,
        "lag_days": conversion_lag_days(sales, conv),
    }


def conversion_lag_days(sales: pd.DataFrame, conv: pd.DataFrame) -> float | None:
    """売上が実物化されるまでの平均日数（先入れ先出しで売上と実物化を突き合わせる）。"""
    s = _events(sales, "売上(円)")
    c = _events(conv, "金額(円)")
    if not s or not c:
        return None
    s, c = [list(x) for x in s], [list(x) for x in c]
    i = j = 0
    weighted = matched = 0.0
    while i < len(s) and j < len(c):
        if c[j][0] < s[i][0]:          # 売上より前の実物化は手元資金からの支出なので数えない
            j += 1
            continue
        m = min(s[i][1], c[j][1])
        weighted += m * (c[j][0] - s[i][0]).days
        matched += m
        s[i][1] -= m
        c[j][1] -= m
        if s[i][1] <= 1e-9:
            i += 1
        if c[j][1] <= 1e-9:
            j += 1
    return weighted / matched if matched else None


def asset_ledger(conv: pd.DataFrame, pi: float, asof: pd.Timestamp | None = None) -> pd.DataFrame:
    """実物資産の台帳。種類ごとに、取得額・現在の実質価値（減耗後）・同額を現金で持った場合を並べる。"""
    d = _clean(conv, "金額(円)")
    if d.empty:
        return pd.DataFrame(columns=["取得額", "実質価値", "現金なら", "差"])
    asof = pd.Timestamp(asof) if asof is not None else d["日付"].max()
    years = ((asof - d["日付"]).dt.days.clip(lower=0) / 365.0).to_numpy()
    decay = d["種類"].map(ASSET_KINDS).fillna(0.3).to_numpy()
    d = d.assign(実質価値=asset_real_value(1.0, decay, years) * d["金額(円)"],
                 現金なら=cash_real_value(1.0, pi, years) * d["金額(円)"])
    out = d.groupby("種類")[["金額(円)", "実質価値", "現金なら"]].sum().rename(columns={"金額(円)": "取得額"})
    out["差"] = out["実質価値"] - out["現金なら"]
    return out


def diversity(conv: pd.DataFrame) -> float:
    """実物資産の分散度 = 1 − HHI（0＝1種類に集中、最大 1−1/種類数）。"""
    d = _clean(conv, "金額(円)")
    total = d["金額(円)"].sum() if not d.empty else 0
    if total <= 0:
        return 0.0
    share = d.groupby("種類")["金額(円)"].sum() / total
    return float(1.0 - (share ** 2).sum())


def three_stage(self_value: float, cash_cost: float, sales_total: float, conv_total: float,
                lag_days: float | None, target_month: float) -> pd.DataFrame:
    """
    3段（作る・売る・換える）の到達度を 0〜1 で返す。
      作る  … 自給の差し引き（月）÷ 置き換えたい食費（月）
      売る  … 売上 ÷ 自給の金額換算（余剰をどれだけ流動性にできたか。上限0.5で満点＝半分以上は自分で食べる）
      換える … 実物化の割合 × 速さ（30日以内で満点、180日で0）
    """
    make = ((self_value - cash_cost) / 12) / target_month if target_month else 0.0
    sell = (sales_total / self_value) / 0.5 if self_value > 0 else 0.0
    ratio = conv_total / sales_total if sales_total > 0 else 0.0
    speed = 1.0 if lag_days is None else float(np.clip((180 - lag_days) / 150, 0, 1))
    if lag_days is None and conv_total == 0:
        speed = 0.0
    conv = min(ratio, 1.0) * speed
    return pd.DataFrame({
        "段": ["① 作る", "② 売る", "③ 換える"],
        "到達度": [float(np.clip(x, 0, 1)) for x in (make, sell, conv)],
        "見ている数字": ["自給の差し引き ÷ 置き換えたい食費",
                     "余剰の売上 ÷ 自給の金額換算（半分売れば満点）",
                     "実物化の割合 × 速さ（30日以内で満点）"],
    })


def real_income(df: pd.DataFrame, pi: float, wage_index: float, fee_index: float,
                food_mult: float) -> pd.DataFrame:
    """
    収入構造（A 時間売り・B 型化・C 自給）を、インフレ下の実質値に直す。
      wage_index … 時給が物価にどれだけ追いつくか（0＝据え置き、1＝完全連動）
      fee_index  … 契約単価の改定がどれだけ追いつくか
      food_mult  … 食料価格の上昇が全体の何倍か（危機時は食料が先に上がりやすい）
    C は「買わずに済んだ食料の額」なので、食料価格に連動して名目で増える。
    """
    y = df["年"].to_numpy(dtype=float)
    cpi = (1 + pi) ** y
    out = pd.DataFrame({"年": df["年"]})
    out["A 時間売り（実質）"] = df["A 時間売り"] * (1 + pi * wage_index) ** y / cpi
    out["B 型化（実質）"] = df["B 型化"] * (1 + pi * fee_index) ** y / cpi
    out["C 自給（実質）"] = df["C 自給（削減額）"] * (1 + pi * food_mult) ** y / cpi
    out["合計（実質）"] = out[["A 時間売り（実質）", "B 型化（実質）", "C 自給（実質）"]].sum(axis=1)
    nominal = df[["A 時間売り", "B 型化", "C 自給（削減額）"]].sum(axis=1)
    out["C の比重"] = (out["C 自給（実質）"] / out["合計（実質）"].where(out["合計（実質）"] > 0)).fillna(0)
    out["合計（名目）"] = nominal
    return out


# ───────────────────────── 内部 ─────────────────────────
def _clean(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if df is None or len(df) == 0 or col not in df:
        return pd.DataFrame(columns=["日付", "種類", col])
    d = df.copy()
    d["日付"] = pd.to_datetime(d["日付"], errors="coerce")
    d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0)
    return d.dropna(subset=["日付"])


def _daily(df: pd.DataFrame, col: str) -> pd.Series:
    d = _clean(df, col)
    return d.groupby(d["日付"].dt.normalize())[col].sum() if not d.empty else pd.Series(dtype=float)


def _events(df: pd.DataFrame, col: str):
    s = _daily(df, col)
    return [(t, float(v)) for t, v in s.items() if v > 0]


# ───────────────────────── 自己チェック ─────────────────────────
if __name__ == "__main__":
    # 現金はインフレで目減りし、実物は減耗分だけ目減りする
    hv = hold_vs_convert(10_000, SCENARIOS["悪性インフレ（年50%）"], "道具", 12)
    assert hv.iloc[-1, 0] < hv.iloc[-1, 1], "悪性インフレでは道具に換えた方が実質価値が残る"
    hv2 = hold_vs_convert(10_000, SCENARIOS["平時（年2%）"], "種", 12)
    assert hv2.iloc[-1, 0] > hv2.iloc[-1, 1], "平時に種を貯め込むのは損（使う分だけ買う）"

    sales = pd.DataFrame([["2027-06-01", "野菜", 10, "kg", 5000, "直売所"],
                          ["2027-07-01", "野菜", 10, "kg", 5000, "直売所"]], columns=SALES_COLS)
    conv_fast = pd.DataFrame([["2027-06-08", "種", "小麦の種", 5000],
                              ["2027-07-08", "道具", "鍬", 5000]], columns=CONVERT_COLS)
    conv_slow = pd.DataFrame([["2027-12-01", "道具", "鍬", 10000]], columns=CONVERT_COLS)
    assert abs(conversion_lag_days(sales, conv_fast) - 7) < 1e-9
    assert conversion_lag_days(sales, conv_slow) > 100
    lf = idle_cash_loss(sales, conv_fast, 0.5)
    ls = idle_cash_loss(sales, conv_slow, 0.5)
    assert lf["loss"] < ls["loss"] and abs(lf["ratio"] - 1) < 1e-9
    assert idle_cash_loss(sales, pd.DataFrame(columns=CONVERT_COLS), 0.5)["ratio"] == 0

    assert diversity(conv_slow) == 0.0
    assert abs(diversity(conv_fast) - 0.5) < 1e-9
    led = asset_ledger(conv_fast, 0.5, pd.Timestamp("2028-07-08"))
    assert set(led.index) == {"種", "道具"} and led.loc["道具", "差"] > 0

    st3 = three_stage(100_000, 20_000, 30_000, 30_000, 7, 10_000)
    assert st3["到達度"].between(0, 1).all() and st3["到達度"].iloc[2] == 1.0
    assert three_stage(100_000, 0, 30_000, 0, None, 10_000)["到達度"].iloc[2] == 0.0

    base = pd.DataFrame({"年": [0, 1, 2], "A 時間売り": [100.0] * 3, "B 型化": [0.0] * 3,
                         "C 自給（削減額）": [50.0] * 3})
    r = real_income(base, 0.5, 0.0, 0.0, 1.5)
    assert r["A 時間売り（実質）"].iloc[-1] < 100 and r["C 自給（実質）"].iloc[-1] > 50
    assert r["C の比重"].iloc[-1] > r["C の比重"].iloc[0], "インフレが進むほど自給の比重が上がる"
    print("OK: chaos_hedge の自己チェックを通過しました")
