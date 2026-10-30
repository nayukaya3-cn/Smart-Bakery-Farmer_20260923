"""
10年戦略（2026〜2036）（所有者専用）─ フェーズ・判断ゲート・準備チェックリスト

ホームは「見せる」場所、ここは「決める」場所。10年戦略は収支・体力・撤退ラインを含むため、
ホームのタブから外して 🔒 管理 に置き、本人だけが見られるようにする。

計算と画面の本体は strategy.py（render）。ロックは owner_gate.py（家計簿・収入構造と共通）。
活動ログは data/activity_log.csv を読む（ホームの 📝 活動ログ と同じファイル）。
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import owner_gate as og  # noqa: E402
import strategy as stg  # noqa: E402

st.set_page_config(page_title="10年戦略（本人のみ）", page_icon="🧭", layout="wide")
og.require_owner("strategy")


def load_log() -> pd.DataFrame:
    """ホームで追加した記録（同じセッション内）があればそれを、なければ CSV を使う。"""
    if "log" in st.session_state:
        return st.session_state.log
    try:
        log = pd.read_csv(ROOT / "data" / "activity_log.csv", encoding="utf-8-sig", dtype=str)
        log["日付"] = pd.to_datetime(log["日付"], errors="coerce")
        return log.dropna(subset=["日付"])
    except Exception:  # noqa: BLE001  CSVが無い・壊れているときも画面は止めない
        return pd.DataFrame(columns=["日付", "カテゴリ", "内容"])


stg.render(load_log(), ROOT / "assets")
