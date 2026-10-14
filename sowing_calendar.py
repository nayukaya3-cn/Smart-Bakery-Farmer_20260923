"""
今まく作物（秋の播種カレンダー）— 計算する → 可視化する → 自分の条件で判断する

home.py の「🔎 詳しく見る › ① 計算する」から sc.render() で呼び出します。
適期はすべて三原市西部（瀬戸内・暖地）向けの目安です。標高や今年の地温で前後します。
小麦だけは、一般的な地域目安（11月中〜12月上旬）ではなく、実体験の最適日（10/20頃）を使います。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st


@dataclass(frozen=True)
class Crop:
    name: str
    group: str            # 主食・パン原料／保存・防災／葉物／土づくり
    start: tuple          # (月, 日)
    end: tuple            # (月, 日)
    action: str           # 播種 or 定植・植付
    role: str             # 位置づけ
    work_days: int        # 作業に必要な日数（目安）
    storage_months: float  # 保存できる期間の目安（月）。0.25 ≒ 1週間


# 適期・保存期間は一般的な目安。自分の記録で上書きしていく前提の初期値。
CROPS = [
    Crop("パン用小麦（暖地向け品種）", "主食・パン原料", (10, 18), (10, 25), "播種",
         "本命。パン屋農家の原料。適期は実体験値（10/20頃が発芽率最適）", 2, 12),
    Crop("ライ麦", "主食・パン原料", (10, 15), (11, 10), "播種",
         "パン原料と緑肥を兼ねる。痩せ地や寒さにも強い", 1, 12),
    Crop("ソラマメ", "保存・防災", (10, 10), (10, 31), "播種",
         "春の収穫物。乾燥豆にすれば長く保存できる", 1, 12),
    Crop("ニンニク", "保存・防災", (10, 1), (10, 31), "植付",
         "保存性が高く、防災備蓄向き", 1, 8),
    Crop("エンドウ（スナップ・実取り）", "保存・防災", (10, 25), (11, 10), "播種",
         "早まきすると冬越し前に育ちすぎて寒害を受ける。まき急がない", 1, 1),
    Crop("葉物（ホウレンソウ・コマツナ・ミズナ・シュンギク）", "葉物", (10, 1), (10, 31), "播種",
         "短期で収穫でき、日々の自給に効く", 1, 0.25),
    Crop("タマネギ（苗の定植）", "保存・防災", (11, 10), (11, 25), "定植",
         "種まきの時期は過ぎたので苗を買う", 2, 6),
    Crop("緑肥（ヘアリーベッチ・エンバク）", "土づくり", (10, 1), (11, 30), "播種",
         "委託中の水田20aを野菜に転換する前の土づくり", 1, 0),
]

GROUP_COLORS = {
    "主食・パン原料": "#c98a2b",
    "保存・防災": "#6a9a4a",
    "葉物": "#7fb3a8",
    "土づくり": "#a08a68",
}


def season_year(today: date) -> int:
    """秋まきの「年」。7月以降はその年の秋、6月までは前年の秋を表示する。"""
    return today.year if today.month >= 7 else today.year - 1


def crop_table(today: date) -> pd.DataFrame:
    """① 計算する：適期と今日の関係（状態・残り日数）を出す。"""
    y = season_year(today)
    rows = []
    for c in CROPS:
        s, e = date(y, *c.start), date(y, *c.end)
        if today > e:
            state, left = "終了", 0
        elif today >= s:
            state, left = "適期中", (e - today).days
        else:
            state, left = "待機", (e - today).days
        rows.append(dict(作物=c.name, 区分=c.group, 作業=c.action, 開始=s, 締切=e,
                         状態=state, 締切まで日数=left, 開始まで日数=max((s - today).days, 0),
                         作業日数=c.work_days, 保存目安_月=c.storage_months, 位置づけ=c.role))
    return pd.DataFrame(rows).sort_values(["締切", "開始"]).reset_index(drop=True)


def schedule(df: pd.DataFrame, today: date, days_per_week: int) -> pd.DataFrame:
    """③ 判断の材料：締切が早い順に、作業できる日へ割り当てる（貪欲法）。

    週あたりの作業可能日数を「月曜から何日目まで作業する」と単純化し、
    1日に1作業だけ入れる。締切に間に合わないものは「要調整」と表示する。
    """
    workable = []
    d = today
    while len(workable) < 120:
        if d.weekday() < days_per_week:
            workable.append(d)
        d += timedelta(days=1)

    used: set[date] = set()
    out = []
    for _, r in df[df["状態"] != "終了"].iterrows():
        need, assigned = int(r["作業日数"]), []
        for wd in workable:
            if wd < max(r["開始"], today) or wd in used:
                continue
            if wd > r["締切"]:
                break
            assigned.append(wd)
            if len(assigned) == need:
                break
        used.update(assigned)
        ok = len(assigned) == need
        out.append(dict(作物=r["作物"], 作業=r["作業"],
                        予定日="・".join(f"{a:%m/%d}" for a in assigned) or "—",
                        締切=f"{r['締切']:%m/%d}",
                        判定="間に合う" if ok else "要調整（作業日を増やすか優先度を下げる）"))
    return pd.DataFrame(out)


def render(today: date | None = None) -> None:
    today = today or date.today()
    df = crop_table(today)

    st.header("🗓️ 今まく作物：秋の播種カレンダー")
    st.write(
        "三原市西部（瀬戸内・暖地）の秋まき・秋植えを、**① 計算する → ② 可視化する → ③ 自分の条件で判断する** "
        "の3段構えで整理しています。小麦の適期だけは、一般的な目安ではなく**実体験の最適日（10/20頃）**を使っています。"
    )

    # ── ① 計算する ──────────────────────────
    st.subheader("① 計算する：今まける作物と残り日数")
    active = df[df["状態"] == "適期中"]
    upcoming = df[df["状態"] != "終了"].sort_values("締切")
    m1, m2, m3 = st.columns(3)
    m1.metric("いま適期の作物", f"{len(active)} 品目")
    if not upcoming.empty:
        nxt = upcoming.iloc[0]
        m2.metric("いちばん近い締切", f"{nxt['締切']:%m/%d}", f"あと {nxt['締切まで日数']} 日", delta_color="off")
        m2.caption(nxt["作物"])
    wheat = df[df["作物"].str.startswith("パン用小麦")].iloc[0]
    sow_day = date(wheat["開始"].year, 10, 20)
    m3.metric("小麦の最適日", f"{sow_day:%m/%d}",
              f"あと {(sow_day - today).days} 日" if sow_day >= today else "過ぎました", delta_color="off")

    show = df[["作物", "作業", "開始", "締切", "状態", "締切まで日数", "位置づけ"]].copy()
    show["開始"] = show["開始"].map(lambda d: f"{d:%m/%d}")
    show["締切"] = show["締切"].map(lambda d: f"{d:%m/%d}")
    st.dataframe(show, hide_index=True, width="stretch")

    # ── ② 可視化する ─────────────────────────
    st.subheader("② 可視化する：播種カウントダウン")
    g = df.copy()
    g["締切+1"] = pd.to_datetime(g["締切"]) + pd.Timedelta(days=1)  # 締切日を棒に含める
    fig = px.timeline(g, x_start="開始", x_end="締切+1", y="作物", color="区分",
                      color_discrete_map=GROUP_COLORS, hover_data={"位置づけ": True, "締切+1": False})
    fig.update_yaxes(autorange="reversed", title=None)
    fig.add_vline(x=pd.Timestamp(today), line_dash="dot", line_color="#555")
    fig.add_vline(x=pd.Timestamp(sow_day), line_color="#c98a2b", line_width=2)
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
    st.plotly_chart(fig, width="stretch")
    st.caption("点線が今日、オレンジの実線が小麦の最適日（10/20）です。棒の右端が各作物の締切です。")

    st.markdown("**保存できる期間の目安**（防災・自給の観点）")
    keep = df[df["保存目安_月"] > 0].sort_values("保存目安_月")
    fig2 = px.bar(keep, x="保存目安_月", y="作物", orientation="h", color="区分",
                  color_discrete_map=GROUP_COLORS, labels={"保存目安_月": "保存目安（月）"})
    fig2.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
    fig2.update_yaxes(title=None)
    st.plotly_chart(fig2, width="stretch")
    st.caption("小麦・ソラマメ（乾燥豆）・ニンニク・タマネギは長く貯蔵でき、「平時の自給で支出を抑える」方針に合う組み合わせです。"
               "保存期間は乾燥・貯蔵条件しだいの目安です。")

    # ── ③ 自分の条件で判断する ─────────────────
    st.subheader("③ 自分の条件で判断する：手間の配分")
    c1, c2 = st.columns([1, 2])
    with c1:
        names = df.loc[df["状態"] != "終了", "作物"].tolist()
        default = [n for n in names if not n.startswith(("葉物", "緑肥", "ライ麦"))]
        chosen = st.multiselect("今季やる作物", names, default=default)
        days = st.slider("1週間に畑に出られる日数", 1, 7, 3)
    with c2:
        plan = schedule(df[df["作物"].isin(chosen)], today, days)
        if plan.empty:
            st.info("作物を選ぶと、締切が早い順に作業日を割り当てます。")
        else:
            st.dataframe(plan, hide_index=True, width="stretch")
            ng = (plan["判定"] != "間に合う").sum()
            if ng:
                st.warning(f"{ng} 件が締切に間に合いません。畑に出る日を増やすか、優先度の低い作物を外してください。")
            else:
                st.success("すべて締切内に収まります。小麦 → ソラマメ・ニンニク → エンドウ → タマネギの順で、作業のピークが分散しています。")

    with st.expander("水田20a（委託中）をどう使うか"):
        st.write(
            "水田は冬の排水が悪いことが多く、いきなり野菜を作ると根腐れしやすくなります。"
            "まずは昔ながらの**麦の裏作**か**緑肥**で一冬様子を見て、排水（溝切り・暗渠）を確かめてから野菜に移るほうが失敗が少なくなります。"
        )

    st.markdown('<p class="note">※ 適期は瀬戸内・暖地の一般的な目安です。圃場の標高や今年の地温で前後します。'
                "小麦は実体験の数値を最優先にし、実測の発芽率を活動ログに残して次年度の目安を更新します。</p>",
                unsafe_allow_html=True)
