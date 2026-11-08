"""
10年戦略（2026〜2036）— 🔒 管理 ›「🧭 10年戦略（本人のみ）」ページの中身（pages/25_🧭_10年戦略.py から render を呼ぶ）

骨格はルーブリックと同じ：① 計算する → ② 可視化する → ③ 自分の条件で判断する
各フェーズの終わりに「判断ゲート」を置き、数字で「進む／縮める」を決める。

更新のしかた（ここだけ書きかえれば画面に反映されます）
  - GATE_INPUTS   … ゲート判定に使う実績値の初期値（実額は Secrets の [gate] に書く）
  - CHECKLIST     … フェーズごとに必ず整えるもの（保険・開業届・許可確認など）の状況
  - MOVE_ORDER    … いま動く順番（理科 → 特別支援 → 情報。ロボットは看板）
  - MOVE_TIMELINE … その順番を、いつ・何をするかに落とした表
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

import owner_gate as og

STRATEGY_UPDATED = "2026-11-08"


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
          "【動く順番】①理科の非常勤講師（「科学と人間生活」）→ ②特別支援学校の作業学習支援・職場実習の受け入れ → ③情報の単位を積む（急がない）。"
          "並行して小麦（10月下旬播種の知見）、車椅子通路、自助具の3D印刷、エヒメアヤメの郷での農作業（有給の実証期間）。"
          "ロボット安全教育は2027年3月に講座を受講し、看板として持つ（収入には数えない）",
          "日誌：毎月の圃場・制作ログを積み上げる",
          "📝 活動ログ（data/activity_log.csv）＋ assets/ の日付フォルダ",
          "記録が12か月途切れず続いたか",
          "まだ売らない。記録は「信頼の預金」"),
    Phase(1, "型化・試行", date(2028, 1, 1), date(2029, 12, 31),
          "自宅前畑・ハウス・家後畑", 10,
          "1コマプログラムの有償トライアル（通信制・単位制高校、特別支援学校の現場実習、総合型選抜の探究）、開業届・青色申告。"
          "2028年度から「情報＋ロボット安全＋特別支援」を組み合わせて売り、ロボット安全教育の最初の1件を狙う",
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
# 実績値はコードに書かず、Secrets の [gate] で上書きする（公開リポジトリに収支を残さないため）
_GATE_SECRET_KEYS = {
    "paid_schools": "有償契約の学校数",
    "keep_schools": "継続意向ありの学校数",
    "income_yen": "年間収入(円)",
    "expense_yen": "年間支出(円)",
    "months_without_me": "自分抜きで回った月数",
}


def gate_inputs() -> dict:
    d = dict(GATE_INPUTS)
    try:
        for k, v in st.secrets.get("gate", {}).items():
            if k in _GATE_SECRET_KEYS:
                d[_GATE_SECRET_KEYS[k]] = int(v)
    except Exception:  # noqa: BLE001  secrets.toml が無い環境
        pass
    return d

# フェーズごとに必ず整えるもの：(フェーズ, 項目, 状況, 確認先・メモ)
# 状況は「済」「進行中」「未着手」のいずれか
CHECKLIST = [
    (0, "活動ログを毎月1件以上残す", "進行中", "このタブの「記録の連続月数」で自動判定"),
    (0, "車椅子が通れる通路", "進行中", "2026年10月4日着工"),
    (0, "県の講師登録（理科・特別支援の両方）", "進行中", "両方の区分で出ているかを県教委に確認（2026年11〜12月）"),
    (0, "私立・通信制へ「科学と人間生活」で正式応募", "未着手", "私立は11〜1月に次年度の体制を決める。外すと1年待ち"),
    (0, "作業学習のある特別支援学校へ直接打診", "未着手", "2027年1〜3月。講師／実習助手（非常勤）＋パン工房・ほ場の実習受け入れの提案"),
    (0, "理科免許だけで特支高等部の講師ができるかの確認", "未着手", "免許法の経過措置の扱いを県教委に確認"),
    (0, "産業用ロボット インストラクターコース受講", "未着手", "2027年3月23〜26日。修了時に講習団体・SIerを1つ紹介してもらう。収入見込みには入れない"),
    (1, "賠償責任保険・傷害保険", "未着手", "生徒受け入れ前に加入"),
    (1, "保護者同意書の書式", "未着手", "ルーブリックの「安全・協働・記録」を運用規程に"),
    (1, "体調確認の手順書", "未着手", "活動ログの「体調確認」欄と対応させる"),
    (1, "高等学校教諭免許状（情報）", "進行中", "急がない。2027年度は理科・特支で働きながら単位を積み、本格的な応募は免許が揃ってから（中学校の情報は技術科の免許が別に必要）"),
    (1, "ロボット安全教育の最初の1件（看板の確かめ）", "未着手", "2028年度に1件を狙う。取れなくても理科・特支の柱は変えない"),
    (1, "開業届・青色申告承認申請", "未着手", "有償トライアル開始の前に税務署へ"),
    (2, "菓子製造業の営業許可要件の確認", "未着手", "保健所に事前相談（小屋の改築前）"),
    (2, "小屋の土地の地目（農地／宅地）確認", "未着手", "農地なら農業委員会で転用手続きを確認"),
    (3, "法人化 or 一般社団化の比較", "未着手", "税理士・行政書士に相談"),
    (3, "後継の指導者（1名以上）", "未着手", "ルーブリック・教材ノートで引き継ぐ"),
]

STATUS_ICON = {"済": "✅", "進行中": "🟡", "未着手": "⬜"}

# ─────────────────────────────────────────────
# いま動く順番（2026-11 見直し）：理科 → 特別支援 → 情報。ロボットのインストラクターは看板
#   (順番, 区分, 需要, 手元の資格, 判定, 収入の形, 次の一手)
#   ロボットは順番に入れない＝収入見込みに数えず、他の仕事との差をつける看板として持つ
# ─────────────────────────────────────────────
MOVE_ORDER = [
    ("1", "理科（科学と人間生活）", "中", "高校理科一種あり", "◎ 本命：今すぐ応募できる",
     "雇用（非常勤講師）", "県の講師登録＋私立・通信制へ正式応募"),
    ("2", "特別支援学校", "中〜高", "理科一種＋特支高等部の実習助手5年4か月（作業学習）",
     "◎ 経歴が最も活きる", "雇用（講師・実習助手）＋業務委託（実習受け入れ）", "作業学習のある学校へ直接打診"),
    ("3", "情報", "高（全国的に不足）", "免許は取得中", "△ 免許が揃うまで本格応募しない",
     "（将来）雇用", "理科・特支で働きながら単位を積む"),
    ("看板", "ロボット特別教育インストラクター", "あり（業務委託。最初の1件が難しい）", "講座を2027年3月に受講予定",
     "○ 収入に数えない", "業務委託", "修了時に講習団体・SIerを1つ紹介してもらう"),
]
MOVE_COLUMNS = ["順番", "区分", "需要", "手元の資格", "判定", "収入の形", "次の一手"]

MOVE_TIMELINE = [  # (時期, やること, 理由)
    ("2026年11〜12月", "県の講師登録が理科・特別支援の両方で出ているか確認／私立・通信制へ「科学と人間生活」で応募",
     "私立は11〜1月に次年度の体制を決める"),
    ("2027年1〜3月", "作業学習のある特別支援学校へ直接打診（講師／実習助手）",
     "パン工房とほ場を職場実習の場にする提案を同時にできる"),
    ("2027年3月", "ロボットのインストラクター講座を受講。講習団体・SIerを1つ紹介してもらう",
     "看板を「信用」と「つながり」に変える"),
    ("2027年度", "理科・特支で働きながら、情報の単位を積む", "情報の免許は急がない"),
    ("2028年度〜", "「情報＋ロボット安全＋特別支援」を組み合わせて売る",
     "福祉の現場でAI・ロボットの安全を教えられる人はほとんどいない"),
]

# 勝ち筋：特別支援学校の「作業学習 × ロボット・自動化 × 農業」
WINNING_EDGE = (
    "**勝ち筋は、特別支援学校の「作業学習 × ロボット・自動化 × 農業」。**"
    "卒業生の就労先は自動化が進む食品工場のラインなので、「ロボットの近くで安全に働く」準備は現実の進路課題です。"
    "看板（ロボット）は、本命（理科・特支）の応募書類で他の人との差をつけるために使います。"
)


def income_sources(include_signboard: bool = False) -> list[str]:
    """収入見込みに数える区分。看板（ロボット）は既定で数えない。"""
    return [r[1] for r in MOVE_ORDER if include_signboard or r[0] != "看板"]


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
    GI = gate_inputs()

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

    # ── いま動く順番（フェーズ0の中身） ──
    st.subheader("いま動く順番：理科 → 特別支援 → 情報")
    st.caption("ロボットのインストラクターは収入源として当てにせず、他の仕事との差をつける**看板**として持ちます。")
    st.dataframe(pd.DataFrame(MOVE_ORDER, columns=MOVE_COLUMNS), width="stretch", hide_index=True)
    st.dataframe(pd.DataFrame(MOVE_TIMELINE, columns=["時期", "やること", "理由"]),
                 width="stretch", hide_index=True)
    st.info(WINNING_EDGE)
    st.caption("収入見込みに数える区分：" + "・".join(income_sources()) +
               "　｜　要確認：理科免許だけで特支高等部の講師ができるか（免許法の経過措置）、"
               "インストラクター講座の修了が特別教育の講師の法的要件か（県教委・労働局に確認）。")

    # ── 判断ゲート ──
    st.subheader("判断ゲート")
    st.caption("フェーズ0は活動ログから自動で計算します。フェーズ1〜3は、実績が出たら Secrets の `[gate]` に書きます（収支のゲート2は所有者のみ表示）。")
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
        paid, keep = GI["有償契約の学校数"], GI["継続意向ありの学校数"]
        a, b = st.columns(2)
        a.metric("有償契約の学校数", f"{paid} 校", help="基準：2校以上")
        b.metric("継続意向ありの学校数", f"{keep} 校", help="基準：1校以上")
        st.progress(min(paid / 2, 1.0), text=f"有償契約：{paid} / 2 校")
        show_verdict(PHASES[1], [paid >= 2, keep >= 1], today)
        st.caption("想定する相手：開校1〜2年目で外部フィールドを探している学校、特別支援学校の現場実習、総合型選抜の探究。")

    with g2:
        # 収支は個人の家計・事業の数字なので所有者専用（owner_gate.py：収入構造ページと共通のロック）
        st.caption("このゲートは「収支が赤字でないか」を判定するため、所有者のみ表示します。")
        if og.owner_block("strategy_gate2"):
            st.markdown("**③ 自分の条件で判断する**：収支は数字で、体力と時間は自分の感覚で入れてください（保存はされません）。")
            inc = st.number_input("年間収入（円）", min_value=0, step=10000, value=int(GI["年間収入(円)"]))
            exp = st.number_input("年間支出（円）", min_value=0, step=10000, value=int(GI["年間支出(円)"]))
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
        months = GI["自分抜きで回った月数"]
        st.metric("自分抜きで回った月数", f"{months} / 12 か月")
        st.progress(min(months / 12, 1.0))
        handover = pd.DataFrame([
            ("ルーブリック", "pages/1_📋_学校向け_記録が残る探究.py の RUBRIC"),
            ("活動ログの書式", "data/activity_log.csv（列：日付,カテゴリ,内容）"),
            ("教材ノート", "notebooks/（Google Colab で開ける）"),
            ("安全・受け入れ手順", "🎓 学校の先生へ › 🤝 受け入れ体制 ＋ 下のチェックリスト"),
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
