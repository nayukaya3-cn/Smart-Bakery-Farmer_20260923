"""
エヒメアヤメの郷での農作業 ─ 「有給の実証期間」を数値で残す
配置先: pages/2_🌾_あやめの郷_農作業.py （Streamlit のマルチページ構成）

位置づけ
  地元の農業法人での農作業を、ただのアルバイトではなく
  「スマートパン屋農家・体験農園（2029年ごろ本格稼働）に向けた実証の場」として記録する。
  骨格はほかのページと同じ：① 計算する → ② 可視化する → ③ 自分の条件で判断する

更新のしかた（ここだけ書きかえれば画面に反映されます）
  - PARTNER_NAME     … 法人名を公開してよいか確認してから書く（未確認なら「地元の農業法人」）
  - CALENDAR         … 年間の繁忙期。あやめの郷の行は「例」なので、実際の作業計画に置き換える
  - data/ayame_work_log.csv … 作業記録。ここに追記してpushすれば消えない

公開ページなので、お金（時給・年金など）の実額は書かない。計算欄は閲覧者の手元だけで動き、保存されない。
"""
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import security_guard as sg
import social as sn

st.set_page_config(page_title="あやめの郷での農作業", page_icon="🌾", layout="wide")

# ─────────────────────────────────────────────
# 基本設定
# ─────────────────────────────────────────────
PARTNER_NAME = "エヒメアヤメの郷"   # 公開の可否を法人に確認してから。未確認なら "地元の農業法人" に
WEEK_CAP_DEFAULT = 40              # 週あたりの上限時間（これを超える話は断る基準）
LOG_CSV = Path(__file__).parent.parent / "data" / "ayame_work_log.csv"
LOG_COLS = ["日付", "作業", "時間(h)", "気づき・教材化のネタ", "来訪者・生徒の反応"]

# 年間カレンダー（2027年度）。種別：授業期間／自分の圃場／あやめの郷
# 「外せない」= その期間は他の予定を入れない
CALENDAR = [
    # 種別, 項目, 開始, 終了, 外せない
    ("非常勤（授業期間）", "1学期",                 "2027-04-08", "2027-07-20", False),
    ("非常勤（授業期間）", "2学期",                 "2027-09-01", "2027-12-24", False),
    ("非常勤（授業期間）", "3学期",                 "2028-01-08", "2028-03-19", False),
    ("自分の圃場",         "小麦 追肥",             "2028-02-01", "2028-03-31", False),
    ("自分の圃場",         "小麦 収穫・乾燥",       "2027-06-01", "2027-06-30", True),
    ("自分の圃場",         "小麦 播種（最適期10/20頃）", "2027-10-15", "2027-10-31", True),
    ("あやめの郷（例）",   "花の季節の来訪者対応（例）", "2027-04-10", "2027-05-10", False),
    ("あやめの郷（例）",   "夏の草刈り（例）",       "2027-07-01", "2027-08-31", False),
    ("あやめの郷（例）",   "秋の収穫期（例）",       "2027-09-20", "2027-10-31", True),
    ("あやめの郷（例）",   "冬の圃場整備（例）",     "2027-12-01", "2028-02-28", False),
]
FARM_KINDS = ("自分の圃場", "あやめの郷（例）")


def load_log() -> pd.DataFrame:
    """data/ayame_work_log.csv を読む。無い・壊れているときは空の表で続ける。"""
    try:
        df = pd.read_csv(LOG_CSV, encoding="utf-8-sig", dtype=str).fillna("")
        df = df[LOG_COLS]
        df = df.apply(lambda c: c.str.replace(r"^'(?=[=+\-@])", "", regex=True).str.strip())
        return normalize(df)
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=LOG_COLS)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in LOG_COLS:
        if c not in df.columns:
            df[c] = ""
    df = df[LOG_COLS]
    df["日付"] = pd.to_datetime(df["日付"], errors="coerce").dt.date
    df["時間(h)"] = pd.to_numeric(df["時間(h)"], errors="coerce").fillna(0.0)
    for c in ["作業", "気づき・教材化のネタ", "来訪者・生徒の反応"]:
        df[c] = df[c].astype(str).replace({"nan": "", "None": ""})
    return df.dropna(subset=["日付"]).reset_index(drop=True)


if "ayame_log" not in st.session_state:
    st.session_state.ayame_log = load_log()

# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🌾 あやめの郷での農作業")
    st.caption("記録はページを閉じると消えます。CSVで保存し、"
               "`data/ayame_work_log.csv` に置いてpushすると、公開ページにも残ります。")
    st.download_button("作業記録をCSVで保存", sg.safe_csv(st.session_state.ayame_log),
                       "ayame_work_log.csv", "text/csv", width="stretch")
    up = st.file_uploader("作業記録のCSVを読み込む", type="csv")
    if up is not None:
        _df = sg.read_csv_safely(up, page="ayame", kind="work_log", dtype=str)
        if _df is not None:
            st.session_state.ayame_log = normalize(_df)
    st.divider()
    sn.buttons("で活動内容を見る", stacked=True)

# ─────────────────────────────────────────────
# ヘッダー
# ─────────────────────────────────────────────
st.title("🌾 あやめの郷での農作業 ─ 有給の実証期間")
st.markdown(
    f"三原市西部の農業法人 **{PARTNER_NAME}** での農作業を、"
    "スマートパン屋農家・体験農園の**本格稼働（2029年ごろ）に向けた実証の場**として記録します。"
    "設備投資をせずに、現場と実績を先に積み上げる進め方です。"
)
c1, c2, c3 = st.columns(3)
c1.info("**① 計算する**\n\n1週間に使える時間を、授業・農作業・研究で割り振る")
c2.info("**② 可視化する**\n\n授業期間と農繁期の重なりを、1年の地図にする")
c3.info("**③ 自分の条件で判断する**\n\n作業記録を積み、続けるか・広げるかを数字で決める")

tab1, tab2, tab3, tab4 = st.tabs(
    ["① 週の時間配分", "② 年間カレンダー", "③ 作業記録（実証ログ）", "🛡️ 安全と取り決め"]
)

# ─────────────────────────────────────────────
# ① 計算する：週の時間配分
# ─────────────────────────────────────────────
with tab1:
    st.subheader("① 1週間の時間は足りるか")
    st.caption("初期値は説明用の仮置きです。自分の条件に書きかえてください（保存されません）。")

    a, b, c = st.columns(3)
    with a:
        st.markdown("**非常勤講師**")
        koma = st.number_input("授業コマ数／週", 0, 20, 6)
        prep = st.number_input("1コマあたりの準備・採点(h)", 0.0, 5.0, 1.0, 0.5)
        days_t = st.number_input("勤務日数／週", 0, 5, 2)
        commute_t = st.number_input("往復の移動時間(h／日)", 0.0, 5.0, 1.5, 0.5)
    with b:
        st.markdown(f"**{PARTNER_NAME}**")
        days_f = st.number_input("農作業の日数／週", 0, 6, 2)
        hours_f = st.number_input("1日の作業時間(h)", 0.0, 10.0, 5.0, 0.5)
        commute_f = st.number_input("往復の移動時間(h／日)", 0.0, 3.0, 0.5, 0.5, key="cf")
    with c:
        st.markdown("**その他**")
        own = st.number_input("自分の圃場(h／週)", 0.0, 30.0, 4.0, 0.5)
        study = st.number_input("研究・免許の勉強(h／週)", 0.0, 40.0, 8.0, 0.5)
        cap = st.number_input("週の上限(h)", 10, 70, WEEK_CAP_DEFAULT)

    parts = {
        "授業": koma * 50 / 60,
        "準備・採点": koma * prep,
        "移動（学校）": days_t * commute_t,
        "農作業": days_f * hours_f,
        "移動（農作業）": days_f * commute_f,
        "自分の圃場": own,
        "研究・勉強": study,
    }
    total = sum(parts.values())
    work_days = days_t + days_f

    m1, m2, m3 = st.columns(3)
    m1.metric("合計（時間／週）", f"{total:.1f} h", f"上限まで {cap - total:+.1f} h",
              delta_color="normal" if total <= cap else "inverse")
    m2.metric("外に出る日数／週", f"{work_days} 日", "休みが週1日未満" if work_days >= 7 else None,
              delta_color="inverse")
    move = parts["移動（学校）"] + parts["移動（農作業）"]
    m3.metric("移動が占める割合", f"{move / total * 100:.0f} %" if total else "—")

    fig = go.Figure()
    for k, v in parts.items():
        fig.add_bar(y=["1週間"], x=[v], name=k, orientation="h",
                    hovertemplate=f"{k}: %{{x:.1f}} h<extra></extra>")
    fig.add_vline(x=cap, line_dash="dash", annotation_text=f"上限 {cap} h")
    fig.update_layout(barmode="stack", height=230, margin=dict(l=10, r=10, t=30, b=10),
                      xaxis_title="時間／週", legend=dict(orientation="h", y=-0.4))
    st.plotly_chart(fig, width="stretch")

    if total > cap:
        st.error(f"上限を {total - cap:.1f} h 超えています。コマ数か農作業の日数を減らすか、"
                 "勤務先を近くにまとめて移動時間を削ってください。")
    elif work_days >= 7:
        st.warning("休みの日がありません。けがや体調不良は、授業と農作業の両方を同時に止めます。")
    else:
        st.success("上限の内側です。農繁期（② の「外せない」期間）は、この配分が崩れないかも確かめてください。")

    with st.expander("収入の柱がどれだけ分散しているか（任意・保存されません）"):
        st.caption("金額は入れなくても、だいたいの割合（%）で構いません。"
                   "ハーフィンダール指数（HHI）＝割合の2乗の合計。1に近いほど一本足です。")
        default = pd.DataFrame({"収入の柱": ["柱A", "柱B", "柱C"], "割合(%)": [0, 0, 0]})
        inc = st.data_editor(default, num_rows="dynamic", width="stretch", key="inc")
        s = pd.to_numeric(inc["割合(%)"], errors="coerce").fillna(0).clip(lower=0)
        if s.sum() > 0:
            share = s / s.sum()
            hhi = float((share ** 2).sum())
            st.metric("HHI（0〜1）", f"{hhi:.2f}", f"柱の実質的な本数 ≒ {1 / hhi:.1f} 本")
            st.caption("目安：0.5 を超えると、1本が止まったときの影響が大きい構成です。")

# ─────────────────────────────────────────────
# ② 可視化する：年間カレンダー
# ─────────────────────────────────────────────
with tab2:
    st.subheader("② 授業期間と農繁期の重なり（2027年度）")
    st.caption("あやめの郷の行は（例）です。実際の作業計画に書きかえると、重なりが計算し直されます。")

    cal = pd.DataFrame(CALENDAR, columns=["種別", "項目", "開始", "終了", "外せない"])
    cal["開始"] = pd.to_datetime(cal["開始"]).dt.date
    cal["終了"] = pd.to_datetime(cal["終了"]).dt.date
    cal = st.data_editor(
        cal, num_rows="dynamic", width="stretch", key="cal",
        column_config={
            "種別": st.column_config.SelectboxColumn(
                options=["非常勤（授業期間）", "自分の圃場", "あやめの郷（例）", "あやめの郷"]),
            "開始": st.column_config.DateColumn(format="YYYY-MM-DD"),
            "終了": st.column_config.DateColumn(format="YYYY-MM-DD"),
        },
    ).dropna(subset=["開始", "終了"])

    if not cal.empty:
        g = cal.assign(開始=pd.to_datetime(cal["開始"]),
                       終了=pd.to_datetime(cal["終了"]) + pd.Timedelta(days=1),
                       表示=np.where(cal["外せない"].fillna(False), "外せない", "通常"))
        fig = px.timeline(g, x_start="開始", x_end="終了", y="種別", color="種別",
                          pattern_shape="表示", hover_name="項目",
                          pattern_shape_map={"通常": "", "外せない": "/"})
        fig.update_yaxes(autorange="reversed", title=None)
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                          legend=dict(orientation="h", y=-0.25, title=None))
        st.plotly_chart(fig, width="stretch")
        st.caption("斜線＝外せない期間（播種・収穫など、ずらすと結果が変わる作業）")

        # 重なりの検出：外せない農作業 × 授業期間
        terms = cal[cal["種別"].str.startswith("非常勤")]
        farms = cal[cal["種別"].str.startswith(FARM_KINDS + ("あやめの郷",)) & cal["外せない"].fillna(False)]
        rows = []
        for _, f in farms.iterrows():
            for _, t in terms.iterrows():
                s, e = max(f["開始"], t["開始"]), min(f["終了"], t["終了"])
                if s <= e:
                    rows.append(dict(外せない作業=f["項目"], 授業期間=t["項目"],
                                     重なり=f"{s:%m/%d}〜{e:%m/%d}", 日数=(e - s).days + 1))
        if rows:
            st.warning("**時間割を組む段階で空けておきたい期間**")
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.caption("対策の例：この期間は非常勤のコマを特定の曜日に寄せ、"
                       "農作業はほかの曜日にまとめるよう、採用面談の段階で相談する。")
        else:
            st.success("外せない農作業と授業期間の重なりはありません。")

# ─────────────────────────────────────────────
# ③ 自分の条件で判断する：作業記録（実証ログ）
# ─────────────────────────────────────────────
with tab3:
    st.subheader("③ 作業記録 ─ 「数値で知っている状態」をつくる")
    st.markdown(
        "作業時間・気づき・来訪者の反応を積み上げると、2029年の本格稼働に向けた"
        "**需要検証のデータ**と、探究学習の**教材の種**がそのまま揃います。"
    )

    with st.form("add_log", clear_on_submit=True):
        f1, f2, f3 = st.columns([1, 2, 1])
        d = f1.date_input("日付", dt.date.today())
        w = f2.text_input("作業内容", placeholder="例：草刈り、苗の植え付け、来訪者の案内")
        h = f3.number_input("時間(h)", 0.0, 12.0, 4.0, 0.5)
        n1, n2 = st.columns(2)
        note = n1.text_area("気づき・教材化のネタ", placeholder="例：同じ畑でも日陰側は乾きが遅い → 土壌水分の測定テーマに", height=80)
        react = n2.text_area("来訪者・生徒の反応", placeholder="例：家族連れが種まき体験に関心", height=80)
        if st.form_submit_button("記録を追加") and w.strip():
            new = pd.DataFrame([[d, w.strip(), h, note.strip(), react.strip()]], columns=LOG_COLS)
            st.session_state.ayame_log = normalize(pd.concat([st.session_state.ayame_log, new]))
            sg.log_event("ayame_log_added", "INFO", page="ayame")
            st.success("追加しました。ページを閉じる前にCSVで保存してください（左のメニュー）。")

    log = st.session_state.ayame_log.sort_values("日付")
    if log.empty:
        st.info("まだ記録がありません。最初の作業日から、1行ずつ積み上げていきます。")
    else:
        k1, k2, k3, k4 = st.columns(4)
        months = pd.to_datetime(log["日付"]).dt.to_period("M")
        k1.metric("累計作業時間", f"{log['時間(h)'].sum():.1f} h")
        k2.metric("作業日数", f"{log['日付'].nunique()} 日")
        k3.metric("教材化のネタ", f"{(log['気づき・教材化のネタ'] != '').sum()} 件")
        k4.metric("来訪者・生徒の反応", f"{(log['来訪者・生徒の反応'] != '').sum()} 件")

        # 記録が途切れていないか（10年戦略 フェーズ0のゲート「12か月途切れず」と同じ基準）
        span = pd.period_range(months.min(), pd.Timestamp.today().to_period("M"), freq="M")
        monthly = (log.assign(月=months).groupby("月")["時間(h)"].sum()
                   .reindex(span, fill_value=0.0))
        gaps = int((monthly == 0).sum())
        fig = go.Figure(go.Bar(x=monthly.index.astype(str), y=monthly.values,
                               marker_color=np.where(monthly.values == 0, "#c9b8a0", "#6b8f4e")))
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10),
                          yaxis_title="作業時間(h)", title="月ごとの作業時間（灰色＝記録なしの月）")
        st.plotly_chart(fig, width="stretch")
        st.caption(f"記録のある月：{len(span) - gaps} / {len(span)} か月　"
                   "（10年戦略フェーズ0の判断ゲート：記録が12か月途切れず続いたか）")

        st.dataframe(log.sort_values("日付", ascending=False), width="stretch", hide_index=True)

    st.divider()
    st.markdown("**判断の目安（1年後に見直す）**")
    st.dataframe(pd.DataFrame([
        ("記録が12か月途切れず続いた", "続ける。体験農園への移行計画（小さく）を立てる"),
        ("教材化のネタが月1件以上たまった", "探究学習の1コマプログラムに組み込み、学校に提案する"),
        ("来訪者・生徒の反応が増えている", "体験の受け入れを試行（安全計画と保険を先に整える）"),
        ("週の上限を超える月が続いた", "日数を減らす。実証より体を優先する"),
    ], columns=["こうなったら", "こうする"]), width="stretch", hide_index=True)

# ─────────────────────────────────────────────
# 安全と取り決め
# ─────────────────────────────────────────────
with tab4:
    st.subheader("🛡️ 始める前に整えること")
    st.caption("農作業でけがをすると、授業と農作業の収入が同時に止まります。ここが最大のリスクです。")
    items = [
        "雇用契約（作業内容・時給・勤務日）を書面でもらった",
        "労災保険の扱いを法人に確認した",
        "夏の作業は時間帯を決めた（早朝・夕方中心、こまめな休憩と水分）",
        "刈払機など危険な機械の扱いを、法人のやり方で確認した",
        "非常勤の勤務先に、兼業（農作業）を伝えた",
        "給与が2か所からになるので、確定申告の準備をした",
        f"作業記録を公開ページに載せてよいか、{PARTNER_NAME}に確認した",
    ]
    done = sum(st.checkbox(i, key=f"chk{n}") for n, i in enumerate(items))
    st.progress(done / len(items), text=f"{done} / {len(items)} 項目")
    st.caption("チェックは保存されません（確認用）。")

st.divider()
st.caption("このページの計算は説明用の単純化モデルです。初期値はすべて仮置きで、実際の条件に置き換えて使います。")
