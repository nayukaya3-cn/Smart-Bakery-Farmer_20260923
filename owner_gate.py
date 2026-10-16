"""
owner_gate.py ─ 所有者専用ページ・所有者専用ブロックの閲覧ロック（共通部品）

守り方（pages/11_収入構造.py から切り出して共通化）:
  ① Googleアカウントでログイン（OpenID Connect）。Google側の2段階認証がそのまま効く。
  ② ログインしたメールアドレスが Secrets の OWNER_EMAILS にあり、Google が確認済み
     （email_verified）のときだけ表示する。
  ③ 認証の設定が無いときは、誰にも表示しない（設定漏れで公開されないように「閉じる側」に倒す）。

使い方:
  ページ全体をロック   … require_owner("kakeibo")          # 所有者でなければ st.stop()
  ページの一部だけロック … if owner_block("strategy_gate2"): ...  # 所有者なら True、違えば案内を出して False

必要な Secrets は secrets.toml.example を参照。
"""
from __future__ import annotations

import streamlit as st

import security_guard as sg

_AUTH_KEYS = ("redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url")


def owner_emails() -> set[str]:
    try:
        raw = st.secrets.get("OWNER_EMAILS", [])
    except Exception:  # noqa: BLE001  secrets.toml が無い環境
        return set()
    if isinstance(raw, str):
        raw = [raw]
    return {str(e).strip().lower() for e in raw if e and "@" in str(e)}


def auth_configured() -> bool:
    try:
        auth = st.secrets.get("auth", {})
    except Exception:  # noqa: BLE001
        return False
    return all(auth.get(k) for k in _AUTH_KEYS)


def _logged_in() -> bool:
    try:
        return bool(st.user.get("is_logged_in", False))
    except Exception:  # noqa: BLE001  古いStreamlit・認証未設定
        return False


def is_owner() -> bool:
    """画面には何も出さずに、所有者としてログイン中かだけを返す。"""
    owners = owner_emails()
    if not owners or not auth_configured() or not _logged_in():
        return False
    email = str(st.user.get("email", "")).strip().lower()
    return email in owners and bool(st.user.get("email_verified", False))


def _denied_help() -> None:
    """閲覧できないとき、ログイン中の本人にだけ原因の手がかりを出す（他人の情報は出さない）。"""
    email = str(st.user.get("email", ""))
    verified = bool(st.user.get("email_verified", False))
    st.caption(f"いまログインしているアカウント：{email or '（取得できませんでした）'}")
    with st.expander("所有者なのに開けないとき"):
        st.markdown(
            "- Secrets の `OWNER_EMAILS` に、**上と同じアドレス**が入っているか確かめてください"
            "（全角・前後の空白・別のGoogleアカウントでのログインに注意）。\n"
            f"- Google の確認済みフラグ（email_verified）：**{'あり' if verified else 'なし'}**。"
            "「なし」なら Googleアカウント側でメールアドレスの確認を済ませてください。\n"
            "- Secrets を直したら、Manage app → Reboot app で再起動します。"
        )


def _gate(page: str, *, stop: bool) -> bool:
    if is_owner():
        key = f"_owner_logged_{page}"
        if not st.session_state.get(key):
            sg.log_event("owner_login", "INFO", page=page)
            st.session_state[key] = True
        return True

    halt = st.stop if stop else (lambda: None)
    if not owner_emails() or not auth_configured():
        st.error("この内容は所有者専用です（認証の設定がまだ無いため、誰にも表示しません）。")
        halt()
        return False

    if not _logged_in():
        st.info("🔒 所有者専用です。Googleアカウントでログインしてください。")
        st.button("Googleでログイン", on_click=st.login, type="primary", key=f"login_{page}")
        halt()
        return False

    if not st.session_state.get(f"_owner_denied_{page}"):  # 再描画のたびに警告を重ねない
        sg.log_event("owner_page_denied", "WARNING", page=page)  # メールアドレスは残さない
        st.session_state[f"_owner_denied_{page}"] = True
    st.error("このアカウントでは閲覧できません。")
    _denied_help()
    st.button("ログアウト", on_click=st.logout, key=f"logout_{page}")
    halt()
    return False


def require_owner(page: str) -> None:
    """ページ全体をロックする。所有者でなければ st.stop() で止める。"""
    _gate(page, stop=True)
    top = st.columns([6, 1])
    top[0].caption(f"🔒 所有者専用ページ｜ログイン中: {st.user.get('email')}")
    top[1].button("ログアウト", on_click=st.logout, key=f"logout_top_{page}")


def owner_block(page: str) -> bool:
    """ページの一部だけをロックする。所有者なら True。違えば案内を出して False（ページは止めない）。"""
    return _gate(page, stop=False)
