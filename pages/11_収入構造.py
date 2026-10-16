"""
収入構造シミュレーター（所有者専用）─ Googleログイン × メールアドレスの許可リスト

守り方:
  ① Googleアカウントでログイン（OpenID Connect）。Google側の2段階認証がそのまま効く。
     → パスワードやワンタイムコードをこのアプリで扱わない（自作の2FAより安全）。
  ② ログインしたメールアドレスが Secrets の OWNER_EMAILS にあり、Google が確認済み
     （email_verified）のときだけ表示する。
  ③ 認証の設定が無いときは、誰にも表示しない（設定漏れで公開されないように「閉じる側」に倒す）。

必要な Secrets（Streamlit Community Cloud → アプリ → Settings → Secrets）は
secrets.toml.example を参照。ロックの本体は owner_gate.py（他のページと共通）。
"""
import sys
from pathlib import Path

import streamlit as st

# income_structure_tab.py はリポジトリ直下に置く想定。
# pages/ に置いた場合でも動くよう、このファイルのフォルダも探す。
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

import owner_gate as og  # noqa: E402
from income_structure_tab import render_income_structure_tab  # noqa: E402

st.set_page_config(page_title="収入構造（本人のみ）", page_icon="💴", layout="wide")

og.require_owner("income")

render_income_structure_tab()

