"""
収入構造シミュレーター（所有者専用）─ Googleログイン × メールアドレスの許可リスト

守り方:
  ① Googleアカウントでログイン（OpenID Connect）。Google側の2段階認証がそのまま効く。
     → パスワードやワンタイムコードをこのアプリで扱わない（自作の2FAより安全）。
  ② ログインしたメールアドレスが Secrets の OWNER_EMAILS にあり、Google が確認済み
     （email_verified）のときだけ表示する。
  ③ 認証の設定が無いときは、誰にも表示しない（設定漏れで公開されないように「閉じる側」に倒す）。

必要な Secrets（Streamlit Community Cloud → アプリ → Settings → Secrets）は
secrets.toml.example を参照。
"""
import sys
from pathlib import Path

import streamlit as st

# income_structure_tab.py はリポジトリ直下に置く想定。
# pages/ に置いた場合でも動くよう、このファイルのフォルダも探す。
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

import security_guard as sg  # noqa: E402
from income_structure_tab import render_income_structure_tab  # noqa: E402

st.set_page_config(page_title="収入構造（本人のみ）", page_icon="💴", layout="wide")


def _owner_emails() -> set[str]:
    try:
        raw = st.secrets.get("OWNER_EMAILS", [])
    except Exception:  # noqa: BLE001  secrets.toml が無い環境
        return set()
    if isinstance(raw, str):
        raw = [raw]
    return {e.strip().lower() for e in raw if e and "@" in e}


def _auth_configured() -> bool:
    try:
        auth = st.secrets.get("auth", {})
    except Exception:  # noqa: BLE001
        return False
    need = ("redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url")
    return all(auth.get(k) for k in need)


def owner_gate() -> None:
    """所有者でなければ st.stop() で止める。"""
    owners = _owner_emails()
    if not owners or not _auth_configured():
        st.error("このページは所有者専用です（認証の設定がまだ無いため、誰にも表示しません）。")
        st.stop()

    if not st.user.get("is_logged_in", False):  # 値が無いときは「未ログイン」扱い
        st.info("所有者専用のページです。Googleアカウントでログインしてください。")
        st.button("Googleでログイン", on_click=st.login, type="primary")
        st.stop()

    email = str(st.user.get("email", "")).lower()
    verified = bool(st.user.get("email_verified", False))
    if email not in owners or not verified:
        sg.log_event("owner_page_denied", "WARNING", page="income")  # メールアドレスは残さない
        st.error("このアカウントでは閲覧できません。")
        st.button("ログアウト", on_click=st.logout)
        st.stop()


owner_gate()

if not st.session_state.get("_owner_logged"):
    sg.log_event("owner_login", "INFO", page="income")
    st.session_state._owner_logged = True

top = st.columns([6, 1])
top[0].caption(f"ログイン中: {st.user.get('email')}")
top[1].button("ログアウト", on_click=st.logout)

render_income_structure_tab()
