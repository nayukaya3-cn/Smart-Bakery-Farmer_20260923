"""
コンテンジェンシープラン（所有者専用）─ 現状把握（戦略情報）→ 次の一手（戦術・戦場情報）

ホームは「見せる」場所なので、判断に使う数字（家計の床・収入・在庫）はここに分けて置く。
最上段の1行だけ見れば「いまの段階」と「今日の一手」が分かるようにする。

  ① 現状把握 … フェーズ・記録の連続月数・7つの指標を4段階（平時・注意・警戒・非常）に読み替える
  ② 次の一手 … 段階ごとに決めておいた if-then を引く。動く前に過剰反応（β）のガードを通す
  ③ 振り返り … 判断と結果を記録し、しきい値と打ち手を直す

保存について: 観測値と判断記録はサーバーに残さない（CSVで手元に保存し、次回読み込む）。
計算の本体は contingency.py。ロックは owner_gate.py（家計簿・収入構造と共通）。
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import contingency as cp  # noqa: E402
import owner_gate as og  # noqa: E402
import security_guard as sg  # noqa: E402
import strategy as stg  # noqa: E402

st.set_page_config(page_title="コンテンジェンシープラン（本人のみ）", page_icon="🛡️", layout="wide")
og.require_owner("contingency")

today = dt.date.today()


def page_path(no: str) -> str | None:
    hits = sorted((ROOT / "pages").glob(f"{no}_*.py"))
    return f"pages/{hits[0].name}" if hits else None


def link(no: str, label: str, icon: str) -> None:
    p = page_path(no)
    try:
        st.page_link(p, label=label, icon=icon)
    except Exception:  # noqa: BLE001  ナビに無い環境でも止めない
        st.caption(f"{icon} {label}（左のメニューから開けます）")


def security_count() -> int:
    """このアプリの警告件数（WARNING 以上）。再起動で0に戻る点に注意。"""
    try:
        ev = sg.recent_events()
        return int(ev["severity"].isin(["WARNING", "ERROR", "CRITICAL"]).sum()) if len(ev) else 0
    except Exception:  # noqa: BLE001
        return 0


def record_streak() -> int:
    try:
        log = pd.read_csv(ROOT / "data" / "activity_log.csv", encoding="utf-8-sig", dtype=str)
        log["日付"] = pd.to_datetime(log["日付"], errors="coerce")
        log = log.dropna(subset=["日付"])
        n, _ = stg.streak(stg.monthly_records(log, ROOT / "assets", today), today)
        return n
    except Exception:  # noqa: BLE001
        return 0


# ───────────── 観測値（セッションに保持。CSVで保存・復元） ─────────────
for _s in cp.SIGNALS:  # 入力欄の値＝セッションの値（同じ再描画のうちに最上段へ反映させるため）
    if f"cp_in_{_s.key}" not in st.session_state:
        st.session_state[f"cp_in_{_s.key}"] = float(security_count()) if _s.key == "security" else _s.default
if "cp_d" not in st.session_state:
    st.session_state.cp_d = 0.0
if "cp_log" not in st.session_state:
    st.session_state.cp_log = pd.DataFrame(columns=cp.DECISION_COLS)

with st.sidebar:
    st.header("観測値・記録の保存")
    st.caption("サーバーには残しません。終わったらダウンロードしてください。")
    obs = pd.DataFrame([{"key": s.key, "値": st.session_state[f"cp_in_{s.key}"]} for s in cp.SIGNALS]
                       + [{"key": "D", "値": st.session_state.cp_d}])
    st.download_button("観測値をCSVで保存", sg.safe_csv(obs), f"観測値_{today}.csv", "text/csv")
    st.download_button("判断の記録をCSVで保存", sg.safe_csv(st.session_state.cp_log),
                       "判断の記録.csv", "text/csv")
    up = st.file_uploader("観測値のCSVを読み込む", type="csv", key="cp_up_obs")
    if up is not None:
        _o = sg.read_csv_safely(up, page="contingency", kind="obs")
        if _o is not None and {"key", "値"} <= set(_o.columns):
            for k, v in zip(_o["key"], pd.to_numeric(_o["値"], errors="coerce")):
                if k == "D" and pd.notna(v):
                    st.session_state.cp_d = float(v)
                elif k in cp.SIG and pd.notna(v):
                    st.session_state[f"cp_in_{k}"] = float(v)
    up2 = st.file_uploader("判断の記録のCSVを読み込む", type="csv", key="cp_up_log")
    if up2 is not None:
        _l = sg.read_csv_safely(up2, page="contingency", kind="decision")
        if _l is not None:
            st.session_state.cp_log = _l.reindex(columns=cp.DECISION_COLS)

# ───────────── 計算（画面より先に。最上段の1行に使う） ─────────────
values = {s.key: float(st.session_state[f"cp_in_{s.key}"]) for s in cp.SIGNALS}
table = cp.assess(values)
lv = cp.overall(table)
beta_ok = sum(bool(st.session_state.get(f"cp_beta_{i}", False)) for i in range(len(cp.BETA_CHECKS)))
moves = cp.next_moves(table, st.session_state.cp_d, beta_ok)

# ───────────── 最上段：これだけ見れば動ける ─────────────
st.title("🛡️ コンテンジェンシープラン")
st.caption("現状把握（戦略情報）→ 次の一手（戦術・戦場情報）→ 振り返り")
banner = getattr(st, ["success", "info", "warning", "error"][lv])
driver = table.iloc[0]["指標"] if lv else "すべての指標が平時"
banner(f"**{cp.LEVEL_ICON[lv]} いまの段階：{cp.LEVELS[lv]}**（いちばん悪い指標：{driver}）　"
       f"→ 今日の一手：**{moves[0]}**")

tab1, tab2, tab3 = st.tabs(["① 現状把握（戦略情報）", "② 次の一手（戦術・戦場情報）", "③ 振り返り"])

# ───────────── ① 現状把握 ─────────────
with tab1:
    phase = stg.current_phase(today)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("10年戦略のフェーズ", f"{phase.no}：{phase.name}")
    m2.metric("次の判断ゲートまで", f"{(phase.end - today).days} 日", phase.gate, delta_color="off")
    m3.metric("記録の連続月数", f"{record_streak()} か月")
    m4.metric("総合の段階", f"{cp.LEVEL_ICON[lv]} {cp.LEVELS[lv]}",
              f"注意以上 {int((table['段階'] > 0).sum())} 指標", delta_color="off")

    st.subheader("7つの指標を入れる")
    st.caption("値は自分で一次情報を確かめて入れます（自動では取りに行きません）。しきい値は contingency.py で直せます。")
    cols = st.columns(2)
    for i, s in enumerate(cp.SIGNALS):
        with cols[i % 2]:
            th = " / ".join(f"{cp.LEVELS[j + 1]}{'≧' if s.higher_is_worse else '≦'}{t:g}" for j, t in enumerate(s.th))
            st.number_input(f"{s.name}（{s.unit}）", step=1.0, key=f"cp_in_{s.key}",
                            help=f"{th}｜確かめる先：{s.source}")

    st.subheader("段階の一覧（悪い順）")
    st.dataframe(table[["表示", "指標", "値", "単位", "次の一手", "確かめる先"]],
                 width="stretch", hide_index=True)
    st.caption("総合の段階は「いちばん悪い指標」で決めます（見落としを防ぐ保守的な読み方）。")

    st.write("**詳しい数字は各ページで**")
    l1, l2, l3 = st.columns(3)
    with l1:
        link("4", "自給家計簿（主食の在庫・カオスヘッジ）", "🌾")
    with l2:
        link("11", "収入構造（インフレ下の実質値）", "💴")
    with l3:
        link("9", "セキュリティログ", "🔒")

# ───────────── ② 次の一手 ─────────────
with tab2:
    st.subheader("動く前に：過剰反応（β）のガード")
    st.caption("危機の報道は、在庫の買い増しを連鎖させます（ブルウィップ効果）。"
               "確かめずに動かないこと自体が、いちばん効く打ち手のことがあります。")
    st.slider(
        "報道と実データの乖離 D（0＝報道どおり、1＝報道だけが騒いでいる）", 0.0, 1.0,
        step=0.05, key="cp_d",
        help=f"D ≧ {cp.D_THRESHOLD} なら買い増さない。研究の乖離指標 D（報道・SNSの騒ぎ vs 実データ）")
    for i, q in enumerate(cp.BETA_CHECKS):
        st.checkbox(q, key=f"cp_beta_{i}")
    st.subheader(f"今日の一手（{cp.LEVEL_ICON[lv]} {cp.LEVELS[lv]}）")
    for n, mv in enumerate(moves, 1):
        st.markdown(f"**{n}.** {mv}")

    with st.expander("段階ごとの行動計画（if-then：もし〜なら、〜する）"):
        plan = pd.DataFrame(
            {f"{cp.LEVEL_ICON[i]} {cp.LEVELS[i]}": list(cp.COMMON[i]) for i in range(len(cp.LEVELS))})
        st.dataframe(plan, width="stretch", hide_index=True)
        st.write("**指標ごとの打ち手**")
        st.dataframe(pd.DataFrame([{"指標": s.name, **{cp.LEVELS[j + 1]: a for j, a in enumerate(s.actions)}}
                                   for s in cp.SIGNALS]), width="stretch", hide_index=True)
        st.caption("迷う前に決めておいた打ち手ほど実行されやすい（実行意図：Gollwitzer, 1999）。"
                   "打ち手を変えたいときは contingency.py の SIGNALS と COMMON を書き換えます。")

    st.subheader("決めた一手を記録する")
    with st.form("cp_decide", clear_on_submit=True):
        pick = st.selectbox("一手", moves + ["（自分で書く）"])
        own = st.text_input("自分で書く場合・補足")
        note = st.text_input("結果・気づき（後で③で書き足せます）")
        if st.form_submit_button("記録に追加", type="primary"):
            row = {"日付": today, "段階": cp.LEVELS[lv],
                   "きっかけ": driver, "決めた一手": own if pick.startswith("（") else pick,
                   "結果・気づき": note}
            st.session_state.cp_log = pd.concat([st.session_state.cp_log, pd.DataFrame([row])],
                                                ignore_index=True)
            st.toast("記録しました。左のメニューからCSVで保存してください。")

# ───────────── ③ 振り返り ─────────────
with tab3:
    st.write("判断と結果を並べ、**しきい値が早すぎた／遅すぎた**、**打ち手が効いた／効かなかった**を見直します。")
    st.session_state.cp_log = st.data_editor(
        st.session_state.cp_log, num_rows="dynamic", width="stretch",
        column_config={"日付": st.column_config.DateColumn(),
                       "段階": st.column_config.SelectboxColumn(options=cp.LEVELS)},
        key="cp_ed_log")
    if len(st.session_state.cp_log):
        st.bar_chart(st.session_state.cp_log["段階"].value_counts().reindex(cp.LEVELS, fill_value=0))
    st.caption("見直しの目安：同じ段階で同じ一手を3回選んだら、その打ち手を前の段階に繰り上げる。"
               "一度も使わない打ち手は消す。")

st.divider()
st.caption("⚠️ 判断の練習と備えのための単純化モデルです。投資・法律の助言ではありません。"
           "災害時は自治体・気象庁の情報と避難指示に従ってください。")
