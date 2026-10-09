"""
10年戦略（2026〜2036）— 「🧭 10年戦略」タブの中身

骨格はルーブリックと同じ：① 計算する → ② 可視化する → ③ 自分の条件で判断する
各フェーズの終わりに「判断ゲート」を置き、数字で「進む／縮める」を決める。

更新のしかた（ここだけ書きかえれば画面に反映されます）
  - GATE_INPUTS   … 有償契約の数・収支など、ゲート判定に使う実績値
  - CHECKLIST     … フェーズごとに必ず整えるもの（保険・開業届・許可確認など）の状況
  - PHASES        … 期間・仕事・小冊子の役割・ゲートの基準（戦略そのものを見直すとき）
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

STRATEGY_UPDATED = "2026-10-10"


@dataclass(frozen=True)
class Phase:
    no: int
    name: str
    start: date
    end: date
    field: str          # 圃場（予定）
    area_a: float       # 圃場の目安（a＝アール）
    work: str           # 主な仕事
    booklet: str        # 小冊子の役割
    booklet_in_repo: str  # このリポジトリのどこがそれに当たるか
    gate: str           # 判断ゲート
    stance: str         # このフェーズの合言葉


PHASES = [
    Phase(0, "実証・記録", date(2026, 7, 1), date(2027, 12, 31),
          "自宅前畑・ハウス・家後畑", 10,
          "小麦（10月下旬播種の知見）、車椅子通路、自助具の3D印刷、情報科免許（2027年9月）、非常勤講師",
          "日誌：毎月の圃場・制作ログを積み上げる",
          "📝 活動ログ（data/activity_log.csv）＋ assets/ の日付フォルダ",
          "記録が12か月途切れず続いたか",
          "まだ売らない。記録は「信頼の預金」"),
    Phase(1, "型化・試行", date(2028, 1, 1), date(2029, 12, 31),
          "自宅前畑・ハウス・家後畑", 10,
          "1コマプログラムの有償トライアル（通信制・単位制高校、特別支援学校の現場実習、総合型選抜の探究）、開業届・青色申告",
          "カタログ：架空の記入例を実績に置き換える",
          "📋 学校向けページの記入例 → 実施記録",
          "有償契約2校以上、継続意向あり",
          "電話が先、資格は誠実に"),
    Phase(2, "柱を絞る", date(2030, 1, 1), date(2032, 12, 31),
          "寺院前農地", 20,
          "探究フィールド提供（B2B）＋防災・自給の暮らしコンサル。パンは店舗ではなく体験教材・イベント限定",
          "実施報告書：学校が上司に見せられる形",
          "📋 学校向けページの「実施報告書」自動作成",
          "体力・時間の余裕があり、収支が赤字でないか",
          "パン工房は「店」にしない"),
    Phase(3, "継承・公開", date(2033, 1, 1), date(2036, 12, 31),
          "農地", 50,
          "法人化 or 一般社団化の判断、エヒメアヤメの郷との統合、教材のオープン化、後継の指導者育成",
          "教科書・アーカイブ：自分がいなくても回る形",
          "notebooks/・ルーブリック・このリポジトリ全体",
          "自分抜きで1年回せるか",
          "成功は「規模」ではなく「継承できるか」"),
]

# ─────────────────────────────────────────────
# ゲート判定に使う実績値（実績が出たら書きかえる）
# ─────────────────────────────────────────────
GATE_INPUTS = {
    "有償契約の学校数": 0,          # フェーズ1：基準 2校以上
    "継続意向ありの学校数": 0,      # フェーズ1：基準 1校以上
    "年間収入(円)": 0,              # フェーズ2：収支が赤字でないか
    "年間支出(円)": 0,
    "自分抜きで回った月数": 0,      # フェーズ3：基準 12か月
}

# フェーズごとに必ず整えるもの：(フェーズ, 項目, 状況, 確認先・メモ)
# 状況は「済」「進行中」「未着手」のいずれか
CHECKLIST = [
    (0, "活動ログを毎月1件以上残す", "進行中", "このタブの「記録の連続月数」で自動判定"),
    (0, "車椅子が通れる通路", "進行中", "2026年10月4日着工"),
    (0, "高等学校教諭免許状（情報）", "進行中", "2027年9月取得予定"),
    (1, "賠償責任保険・傷害保険", "未着手", "生徒受け入れ前に加入"),
    (1, "保護者同意書の書式", "未着手", "ルーブリックの「安全・協働・記録」を運用規程に"),
    (1, "体調確認の手順書", "未着手", "活動ログの「体調確認」欄と対応させる"),
    (1, "開業届・青色申告承認申請", "未着手", "有償トライアル開始の前に税務署へ"),
    (2, "菓子製造業の営業許可要件の確認", "未着手", "保健所に事前相談（小屋の改築前）"),
    (2, "小屋の土地の地目（農地／宅地）確認", "未着手", "農地なら農業委員会で転用手続きを確認"),
    (3, "法人化 or 一般社団化の比較", "未着手", "税理士・行政書士に相談"),
    (3, "後継の指導者（1名以上）", "未着手", "ルーブリック・教材ノートで引き継ぐ"),
]

STATUS_ICON = {"済": "✅", "進行中": "🟡", "未着手": "⬜"}


def current_phase(today: date) -> Phase:
    for p in PHASES:
        if p.start <= today <= p.end:
            return p
    return PHASES[0] if today < PHASES[0].start else PHASES[-1]


# ─────────────────────────────────────────────
# ① 計算する：フェーズ0のゲート「記録が12か月途切れず続いたか」
# ─────────────────────────────────────────────
_DATE_DIR = re.compile(r"^(20\d{2})(\d{2})(\d{2})$")


def asset_months(assets: Path) -> pd.Series:
    """assets/ 以下の日付フォルダ（YYYYMMDD）を、月ごとの「制作・写真の記録」として数える。"""
    months = []
    if assets.exists():
        for d in assets.rglob("*"):
            m = _DATE_DIR.match(d.name)
            if d.is_dir() and m and any(d.iterdir()):
                months.append(pd.Period(f"{m.group(1)}-{m.group(2)}", freq="M"))
    return pd.Series(months, dtype="period[M]").value_counts()


def monthly_records(log: pd.DataFrame, assets: Path, today: date) -> pd.DataFrame:
    """月ごとの記録件数（活動ログ＋日付フォルダ）。最初の記録の月から今月まで、空白月も0で並べる。"""
    log_m = pd.to_datetime(log["日付"]).dt.to_period("M").value_counts()
    ast_m = asset_months(assets)
    first = min([*log_m.index, *ast_m.index], default=pd.Period(today, freq="M"))
    idx = pd.period_range(first, pd.Period(today, freq="M"), freq="M")
    df = pd.DataFrame({
        "月": idx,
        "活動ログ": log_m.reindex(idx, fill_value=0).values,
        "写真・制作フォルダ": ast_m.reindex(idx, fill_value=0).values,
    })
    df["合計"] = df["活動ログ"] + df["写真・制作フォルダ"]
    return df


def streak(df: pd.DataFrame, today: date) -> tuple[int, list[str]]:
    """今月（途中なので記録0でも中断扱いにしない）から遡って、途切れずに記録がある月数と、空白月の一覧。"""
    this_month = pd.Period(today, freq="M")
    rows = df[df["月"] < this_month] if df.loc[df["月"] == this_month, "合計"].sum() == 0 else df
    n = 0
    for v in rows["合計"].iloc[::-1]:
        if v > 0:
            n += 1
        else:
            break
    gaps = [str(m) for m, v in zip(df["月"], df["合計"]) if v == 0 and m < this_month]
    return n, gaps


# ─────────────────────────────────────────────
# ③ 自分の条件で判断する：ゲートの判定ルール
# ─────────────────────────────────────────────
def judge(ok: list[bool]) -> tuple[str, str]:
    if all(ok):
        return "進む", "success"
    if any(ok):
        return "保留（足りない条件を補ってから）", "warning"
    return "縮める（規模・期間を見直す）", "error"


def show_verdict(phase: Phase, ok: list[bool], today: date, label: str = "③ 判断") -> None:
    """ゲートの判定を表示する。そのフェーズに入る前は、基準の確認だけにとどめる（早すぎる「縮める」を出さない）。"""
    if today < phase.start:
        st.info(f"{label}：判定はフェーズ{phase.no}の終わり（{phase.end:%Y年%m月}）。"
                "いまは基準を確認しておく段階です。")
        return
    verdict, kind = judge(ok)
    getattr(st, kind)(f"{label}（いまの数値なら）：**{verdict}**")


def render(log: pd.DataFrame, assets: Path, today: date | None = None) -> None:
    today = today or date.today()
    cur = current_phase(today)

    st.header("🧭 10年戦略（2026〜2036）")
    st.write(
        "このダッシュボードの「計算する → 可視化する → 自分の条件で判断する」を、10年の歩み方にも使います。"
        "各フェーズの終わりに**判断ゲート**を置き、数字で「進む／縮める」を決めます。"
    )
    st.caption(f"最終更新：{STRATEGY_UPDATED}　｜　期間・基準は計画であり、実績ではありません。")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("いまのフェーズ", f"{cur.no}　{cur.name}")
    c1.caption(cur.stance)
    c2.metric("フェーズ終了まで", f"{(cur.end - today).days} 日")
    c2.caption(f"{cur.start:%Y/%m}〜{cur.end:%Y/%m}")
    c3.metric("圃場の目安", f"約 {cur.area_a:g} a")
    c3.caption(cur.field)
    c4.metric("2036年末まで", f"{(PHASES[-1].end - today).days // 365} 年")
    c4.caption("自分抜きで回る形がゴール")

    # ── ② 可視化する：10年の流れ ──
    st.subheader("10年の流れ")
    tl = pd.DataFrame([dict(フェーズ=f"{p.no} {p.name}", 開始=p.start, 終了=p.end,
                            仕事=p.work, ゲート=p.gate) for p in PHASES])
    fig = px.timeline(tl, x_start="開始", x_end="終了", y="フェーズ", color="フェーズ",
                      hover_data={"仕事": True, "ゲート": True, "フェーズ": False},
                      color_discrete_sequence=["#c98a2b", "#9bb884", "#6f9fb8", "#a689c4"])
    for p in PHASES:
        fig.add_annotation(x=pd.Timestamp(p.end), y=f"{p.no} {p.name}", text="◆ゲート",
                           showarrow=False, xanchor="right", font=dict(size=11))
    fig.add_vline(x=pd.Timestamp(today), line_dash="dot", line_color="#555")
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.caption("◆ が各フェーズ末の判断ゲート、点線が今日です。")

    table = pd.DataFrame([{
        "フェーズ": f"{p.no} {p.name}", "期間": f"{p.start:%Y}〜{p.end:%Y}",
        "圃場（目安）": f"{p.field}（約{p.area_a:g}a）", "主な仕事": p.work,
        "小冊子の役割": p.booklet, "このリポジトリでは": p.booklet_in_repo, "判断ゲート": p.gate,
    } for p in PHASES])
    st.dataframe(table, width="stretch", hide_index=True)

    # ── 判断ゲート ──
    st.subheader("判断ゲート")
    st.caption("フェーズ0は活動ログから自動で計算します。フェーズ1〜3は、実績が出たら `strategy.py` の `GATE_INPUTS` を書きかえます。")
    g0, g1, g2, g3 = st.tabs([f"ゲート{p.no}：{p.gate}" for p in PHASES])

    with g0:
        mr = monthly_records(log, assets, today)
        n, gaps = streak(mr, today)
        a, b, c = st.columns(3)
        a.metric("① 途切れず続いた月数", f"{n} / 12 か月")
        b.metric("記録のある月", f"{int((mr['合計'] > 0).sum())} か月")
        c.metric("空白の月", f"{len(gaps)} か月")
        st.progress(min(n / 12, 1.0), text=f"ゲート0の達成度：{min(n, 12)} / 12 か月")
        long = mr.melt(id_vars="月", value_vars=["活動ログ", "写真・制作フォルダ"],
                       var_name="種類", value_name="件数")
        long["月"] = long["月"].astype(str)
        f2 = px.bar(long, x="月", y="件数", color="種類",
                    color_discrete_map={"活動ログ": "#c98a2b", "写真・制作フォルダ": "#9bb884"})
        f2.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="",
                         xaxis_title=None, yaxis_title="件数")
        st.plotly_chart(f2, width="stretch")
        if gaps:
            st.warning("記録が空白の月：" + "、".join(gaps) + "　→ 1行でもよいので、その月の作業を書き足すと連続が戻ります。")
        if n >= 12:
            st.success("③ 判断：**進む**　（基準：12か月連続を達成）")
        else:
            st.info(f"③ 判断：あと **{12 - n} か月** 記録を続けると判定できます"
                    f"（フェーズ0の終わり：{PHASES[0].end:%Y年%m月}）。")
        st.caption("数え方：その月に活動ログが1件以上、または assets/ に日付フォルダ（YYYYMMDD）が1つ以上あれば「記録あり」。"
                   "今月は途中なので、まだ記録がなくても途切れた扱いにしません。")

    with g1:
        paid, keep = GATE_INPUTS["有償契約の学校数"], GATE_INPUTS["継続意向ありの学校数"]
        a, b = st.columns(2)
        a.metric("有償契約の学校数", f"{paid} 校", help="基準：2校以上")
        b.metric("継続意向ありの学校数", f"{keep} 校", help="基準：1校以上")
        st.progress(min(paid / 2, 1.0), text=f"有償契約：{paid} / 2 校")
        show_verdict(PHASES[1], [paid >= 2, keep >= 1], today)
        st.caption("想定する相手：開校1〜2年目で外部フィールドを探している学校、特別支援学校の現場実習、総合型選抜の探究。")

    with g2:
        st.markdown("**③ 自分の条件で判断する**：収支は数字で、体力と時間は自分の感覚で入れてください（保存はされません）。")
        inc = st.number_input("年間収入（円）", min_value=0, step=10000, value=int(GATE_INPUTS["年間収入(円)"]))
        exp = st.number_input("年間支出（円）", min_value=0, step=10000, value=int(GATE_INPUTS["年間支出(円)"]))
        hrs = st.slider("この事業に使っている時間（週あたり・時間）", 0, 60, 15)
        cap = st.slider("無理なく使える時間（週あたり・時間）", 0, 60, 20)
        body = st.select_slider("体力の余裕", ["きつい", "ややきつい", "ふつう", "余裕あり"], value="ふつう")
        bal = inc - exp
        a, b = st.columns(2)
        a.metric("① 年間収支", f"{bal:,} 円", delta="黒字" if bal >= 0 else "赤字",
                 delta_color="normal" if bal >= 0 else "inverse")
        b.metric("① 時間の余裕", f"{cap - hrs:+d} 時間/週")
        verdict, kind = judge([bal >= 0, hrs <= cap, body in ("ふつう", "余裕あり")])
        getattr(st, kind)(f"③ 判断（入力した条件なら）：**{verdict}**")
        if today < PHASES[2].start:
            st.caption(f"正式な判定はフェーズ2の終わり（{PHASES[2].end:%Y年%m月}）。いまは自分の条件を試しに入れてみる段階です。")
        st.caption("週2日の店舗は、仕込み・衛生管理・在庫で体力を固定的に使うため、この段階では選びません。"
                   "パンは探究の1単元（栽培→製粉→発酵の科学→焼成）と、予約・イベント限定にとどめます。")

    with g3:
        months = GATE_INPUTS["自分抜きで回った月数"]
        st.metric("自分抜きで回った月数", f"{months} / 12 か月")
        st.progress(min(months / 12, 1.0))
        handover = pd.DataFrame([
            ("ルーブリック", "pages/1_📋_学校向け_記録が残る探究.py の RUBRIC"),
            ("活動ログの書式", "data/activity_log.csv（列：日付,カテゴリ,内容）"),
            ("教材ノート", "notebooks/（Google Colab で開ける）"),
            ("安全・受け入れ手順", "🤝 受け入れ体制タブ ＋ 下のチェックリスト"),
        ], columns=["引き継ぐもの", "置き場所"])
        st.dataframe(handover, width="stretch", hide_index=True)
        show_verdict(PHASES[3], [months >= 12], today)
        st.caption("このリポジトリ自体が引き継ぎ書になるよう、手順は画面ではなくファイルに残します。")

    # ── フェーズごとに必ず整えるもの ──
    st.subheader("フェーズごとに必ず整えるもの")
    ck = pd.DataFrame(CHECKLIST, columns=["フェーズ", "項目", "状況", "確認先・メモ"])
    ck["状況"] = ck["状況"].map(lambda s: f"{STATUS_ICON.get(s, '')} {s}")
    show_all = st.toggle("全フェーズを表示", value=False)
    view = ck if show_all else ck[ck["フェーズ"] <= cur.no + 1]
    st.dataframe(view, width="stretch", hide_index=True)
    done = sum(1 for p, _, s, _ in CHECKLIST if p <= cur.no and s == "済")
    total = sum(1 for p, *_ in CHECKLIST if p <= cur.no)
    st.progress(done / total if total else 0.0, text=f"いまのフェーズまでに済んだ項目：{done} / {total}")

    fig3 = go.Figure(go.Scatter(
        x=[p.start for p in PHASES] + [PHASES[-1].end], y=[p.area_a for p in PHASES] + [PHASES[-1].area_a],
        mode="lines+markers", line_shape="hv", line_color="#9bb884",
        text=[p.field for p in PHASES] + [""], hovertemplate="%{x|%Y}：約%{y}a　%{text}<extra></extra>"))
    fig3.update_layout(height=220, margin=dict(l=10, r=10, t=30, b=10), title="圃場の広さの目安（a）",
                       yaxis_title="a", xaxis_title=None)
    with st.expander("圃場の広さの見通し"):
        st.plotly_chart(fig3, width="stretch")
        st.caption("広げるのはゲートを通ったときだけ。通らなければ、いまの広さのまま続けます。")
