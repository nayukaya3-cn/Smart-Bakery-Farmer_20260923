"""
収入構造シミュレーター（計算 → 可視化 → 判断）
-------------------------------------------------
既存アプリへの組み込み:
    from income_structure_tab import render_income_structure_tab
    tabs = st.tabs([..., "収入構造"])
    with tabs[-1]:
        render_income_structure_tab()

単体実行（手元のPCだけで使う場合）:
    streamlit run income_structure_tab.py

公開アプリでは pages/11_収入構造.py から呼ばれ、所有者のGoogleログイン後だけ表示される。
実際のコマ給・提示価格はコードに書かず、Secrets の [income] に入れる（リポジトリに残さないため）。
"""
import numpy as np
import pandas as pd
import streamlit as st


# ───────────────────────── 計算 ─────────────────────────
def simulate(p: dict, horizon: int = 10) -> pd.DataFrame:
    y = np.arange(horizon + 1)

    # A: 時間売り（非常勤） — 単価が年 r% 下落
    koma_per_year = p["koma_per_week"] * p["weeks_per_year"]
    unit = p["koma_rate"] * (1 - p["decline"] / 100) ** y
    a = koma_per_year * unit

    # B: 型化（探究プログラムのB2B提供）
    schools = np.minimum(np.floor(y * p["schools_per_year"]), p["max_schools"])
    cost = np.where(y == 0, p["dev_cost"], p["revise_cost"])
    b = schools * p["fee_per_school"] - cost

    # C: 支出削減（自給） — 稼がずに必要額を下げる
    c = np.minimum(y * p["saving_step"], p["saving_cap"])

    df = pd.DataFrame({
        "年": y,
        "A 時間売り": a,
        "B 型化": b,
        "C 自給（削減額）": c,
        "導入校数": schools,
        "コマ単価": unit,
    })
    for col in ["A 時間売り", "B 型化", "C 自給（削減額）"]:
        df[f"{col} 累計"] = df[col].cumsum()
    return df


def breakeven_year(series: pd.Series):
    """累計が初めて正になる年（なければ None）"""
    hit = series[series > 0]
    return int(hit.index[0]) if len(hit) else None


# ──────────────────────── UI ───────────────────────────
# コードに残す既定値は仮置き。実額は Secrets の [income] で上書きする
PLACEHOLDER = dict(koma_rate=2800, koma_per_week=6, weeks_per_year=35, decline=2.0,
                   fee_per_school=150_000, schools_per_year=1.0, max_schools=5,
                   dev_cost=400_000, revise_cost=30_000,
                   saving_step=40_000, saving_cap=240_000)


def _defaults() -> dict:
    d = dict(PLACEHOLDER)
    try:
        d.update({k: type(PLACEHOLDER[k])(v) for k, v in st.secrets.get("income", {}).items()
                  if k in PLACEHOLDER})
    except Exception:  # noqa: BLE001  secrets.toml が無い環境
        pass
    # 自給シミュレーター（pages/15）を同じセッションで開いていれば、その計算結果を「C 自給」の初期値にする
    link = st.session_state.get("jikyu_link")
    if link:
        d.update({k: int(link[k]) for k in ("saving_step", "saving_cap") if k in link})
    return d


def render_income_structure_tab():
    d = _defaults()
    st.header("収入構造シミュレーター")
    st.caption("計算 → 可視化 → 自分の条件で判断。既定値は Secrets の [income]（未登録なら仮置き）です。")
    if st.session_state.get("jikyu_link"):
        st.info("「C 自給」の初期値は、自給と防災の畑シミュレーターの計算結果（全部買う場合との差）を使っています。")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("A 時間売り")
        koma_rate = st.number_input("コマ給（円/コマ）", 0, 20000, d["koma_rate"], 100)
        koma_per_week = st.number_input("週あたりコマ数", 0, 30, d["koma_per_week"])
        weeks_per_year = st.number_input("年間授業週数", 0, 52, d["weeks_per_year"])
        decline = st.slider("単価の年間下落率（%）", 0.0, 10.0, d["decline"], 0.5,
                            help="AI・競争による単価圧力の仮定。0%でも試す")
    with c2:
        st.subheader("B 型化")
        fee_per_school = st.number_input("提示価格（円/校・年）", 0, 3_000_000, d["fee_per_school"], 10_000)
        schools_per_year = st.slider("導入ペース（校/年）", 0.0, 3.0, d["schools_per_year"], 0.5)
        max_schools = st.number_input("上限校数（キャパ制約）", 0, 20, d["max_schools"])
        dev_cost = st.number_input("初期開発費（円）", 0, 5_000_000, d["dev_cost"], 50_000)
        revise_cost = st.number_input("年次改訂費（円）", 0, 1_000_000, d["revise_cost"], 10_000)
    with c3:
        st.subheader("C 自給")
        saving_step = st.number_input("年ごとの削減額の増分（円）", 0, 500_000, d["saving_step"], 10_000)
        saving_cap = st.number_input("削減額の上限（円/年）", 0, 2_000_000, d["saving_cap"], 10_000)
        horizon = st.slider("期間（年）", 3, 15, 10)

    p = dict(koma_rate=koma_rate, koma_per_week=koma_per_week,
             weeks_per_year=weeks_per_year, decline=decline,
             fee_per_school=fee_per_school, schools_per_year=schools_per_year,
             max_schools=max_schools, dev_cost=dev_cost, revise_cost=revise_cost,
             saving_step=saving_step, saving_cap=saving_cap)
    df = simulate(p, horizon)

    # ───────────── 可視化 ─────────────
    st.divider()
    view = st.radio("表示", ["年間", "累計"], horizontal=True)
    cols = ["A 時間売り", "B 型化", "C 自給（削減額）"]
    if view == "累計":
        cols = [f"{c} 累計" for c in cols]
    st.line_chart(df.set_index("年")[cols])

    be = breakeven_year(df["B 型化 累計"])
    m1, m2, m3 = st.columns(3)
    m1.metric(f"A {horizon}年後のコマ単価", f"{df['コマ単価'].iloc[-1]:,.0f} 円",
              f"{df['コマ単価'].iloc[-1] - koma_rate:,.0f} 円")
    m2.metric("B 累計黒字化", f"{be} 年目" if be is not None else "期間内なし")
    m3.metric("B 最悪ケース（導入0校）", f"−{dev_cost + revise_cost * horizon:,.0f} 円")

    with st.expander("年次データ"):
        st.dataframe(df.style.format("{:,.0f}"), width="stretch")

    # ───────────── 判断 ─────────────
    st.divider()
    st.subheader("自分の条件で判断する")
    q1 = st.checkbox("① B が導入0校で終わっても、生活の床（年金＋自給）を割らない")
    q2 = st.checkbox("② 2校目以降の準備時間が、1校目の2割以下に収まる見込み")
    q3 = st.checkbox("③ 制度・既存プラットフォーム（通信制の探究枠など）が需要を支えている")

    score = sum([q1, q2, q3])
    if score == 3:
        st.success("B（型化）を進める条件が揃っています。まず1校で実証。")
    elif score == 2:
        st.warning("条件が1つ欠けています。欠けた項目を先に確かめてから。")
    else:
        st.info("現時点では A（時間売り）と C（自給）を土台に。B は検証段階に留める。")

    st.caption("ヒント: 下落率を0%にしても B が A を上回るか、"
               "導入ペースを0.5に落としても黒字化するか、を試すと頑健性が分かります。")


if __name__ == "__main__":
    st.set_page_config(page_title="収入構造シミュレーター", layout="wide")
    render_income_structure_tab()
