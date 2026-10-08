"""
security_guard.py ─ 公開アプリのセキュリティ対策・ログ記録・アラーム

① 記録する : セキュリティに関わる出来事（アップロード拒否・AI呼び出し・上限到達・例外）を
              JSON 1行ログとして標準出力へ。Streamlit Community Cloud の「Manage app → Logs」で見られる。
              直近 500 件はサーバーのメモリにも保持し、管理者ページで表示・CSV保存できる。
② 検知する : 警告が短時間に集中したら「バースト」として重大度を上げる。
③ 知らせる : st.secrets / 環境変数 SECURITY_WEBHOOK_URL があれば、警告以上を Webhook
              （Slack / Discord 互換）へ送る。同じ種類の通知は 10 分に 1 回まで。

方針：
- 個人情報（IPアドレス・氏名・ファイル内容）はログに残さない。セッションは匿名IDで区別する。
- サーバーのメモリ上のログは再起動で消える。長く残したい記録は Webhook 先か CSV で保存する。
"""
from __future__ import annotations

import collections
import datetime as dt
import hmac
import io
import json
import logging
import os
import threading
import time
import urllib.request
import uuid

import pandas as pd
import streamlit as st

JST = dt.timezone(dt.timedelta(hours=9))

# ── しきい値（ここを書きかえれば運用を調整できる） ──
MAX_CSV_BYTES = 5 * 1024 * 1024       # CSV は 5MB まで
MAX_CSV_ROWS = 50_000                 # CSV は 5万行まで
MAX_IMAGE_BYTES = 15 * 1024 * 1024    # 画像は 15MB まで
AI_CALLS_PER_SESSION = 3              # 生成AI：1セッションあたり
AI_CALLS_PER_DAY = 40                 # 生成AI：アプリ全体で1日あたり（APIキーの不正利用・課金爆発を防ぐ）
BURST_WINDOW_SEC = 600                # 10分間に
BURST_THRESHOLD = 10                  # 警告が10件以上 → バースト（攻撃の疑い）
ALERT_COOLDOWN_SEC = 600              # 同じ種類の通知は10分に1回

SEVERITY = {"INFO": 20, "WARNING": 30, "CRITICAL": 50}

_logger = logging.getLogger("security")
if not _logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_h)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


# ─────────────────────────────────────────────
# 共有状態（全セッション共通・プロセス内）
# ─────────────────────────────────────────────
@st.cache_resource
def _shared() -> dict:
    return {
        "lock": threading.Lock(),
        "events": collections.deque(maxlen=500),
        "warn_times": collections.deque(maxlen=1000),
        "ai_day": "",
        "ai_count": 0,
        "last_alert": {},
        "last_burst": 0.0,
    }


def _secret(name: str) -> str:
    try:
        v = st.secrets.get(name, "")
    except Exception:  # noqa: BLE001  secrets.toml が無い環境
        v = ""
    return str(v or os.environ.get(name, ""))


def session_id() -> str:
    if "_sec_sid" not in st.session_state:
        st.session_state._sec_sid = uuid.uuid4().hex[:10]
    return st.session_state._sec_sid


# ─────────────────────────────────────────────
# ① 記録する
# ─────────────────────────────────────────────
def log_event(event: str, severity: str = "INFO", page: str = "", **fields) -> None:
    """セキュリティイベントを1行JSONで記録する。fields に個人情報を入れないこと。"""
    try:
        sid = session_id()
    except Exception:  # noqa: BLE001
        sid = "-"
    rec = {
        "ts": dt.datetime.now(JST).isoformat(timespec="seconds"),
        "severity": severity,
        "event": event,
        "page": page,
        "session": sid,
        **{k: (v if isinstance(v, (int, float, bool)) or v is None else str(v)[:200]) for k, v in fields.items()},
    }
    _logger.log(SEVERITY.get(severity, 20), json.dumps(rec, ensure_ascii=False))
    s = _shared()
    burst = False
    with s["lock"]:
        s["events"].append(rec)
        if SEVERITY.get(severity, 20) >= SEVERITY["WARNING"]:
            now = time.time()
            s["warn_times"].append(now)
            recent = [t for t in s["warn_times"] if now - t <= BURST_WINDOW_SEC]
            if (len(recent) >= BURST_THRESHOLD and event != "burst_detected"
                    and now - s["last_burst"] > BURST_WINDOW_SEC):  # 同じ攻撃の波では1回だけ
                burst, s["last_burst"] = True, now
    if SEVERITY.get(severity, 20) >= SEVERITY["WARNING"]:
        _alert(rec)
    if burst:
        log_event("burst_detected", "CRITICAL", page=page,
                  detail=f"{BURST_WINDOW_SEC // 60}分間に警告{BURST_THRESHOLD}件以上")


def recent_events() -> pd.DataFrame:
    s = _shared()
    with s["lock"]:
        rows = list(s["events"])
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# ③ 知らせる（Webhook）
# ─────────────────────────────────────────────
def _alert(rec: dict) -> None:
    url = _secret("SECURITY_WEBHOOK_URL")
    if not url.startswith("https://"):
        return
    s = _shared()
    key = rec["event"]
    now = time.time()
    with s["lock"]:
        if now - s["last_alert"].get(key, 0) < ALERT_COOLDOWN_SEC:
            return
        s["last_alert"][key] = now
    text = (f"[{rec['severity']}] スマートパン屋農家アプリ: {rec['event']}\n"
            + "\n".join(f"{k}: {v}" for k, v in rec.items() if k not in ("severity", "event")))
    body = json.dumps({"text": text, "content": text[:1900]}).encode()  # Slack は text, Discord は content

    def _send() -> None:
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).close()  # nosec B310
        except Exception as e:  # noqa: BLE001
            _logger.warning(json.dumps({"event": "alert_send_failed", "error": type(e).__name__}))

    threading.Thread(target=_send, daemon=True).start()


# ─────────────────────────────────────────────
# 入力の検査
# ─────────────────────────────────────────────
def check_upload(up, max_bytes: int, page: str, kind: str) -> bool:
    """アップロードファイルの大きさを確かめる。大きすぎれば拒否して記録する。"""
    if up is None:
        return False
    size = getattr(up, "size", None) or len(up.getvalue())
    if size > max_bytes:
        log_event("upload_rejected", "WARNING", page=page, kind=kind, reason="too_large", bytes=size)
        st.error(f"ファイルが大きすぎます（上限 {max_bytes // (1024 * 1024)} MB）。")
        return False
    log_event("upload_accepted", "INFO", page=page, kind=kind, bytes=size)
    return True


def read_csv_safely(up, page: str, kind: str = "csv", **kwargs) -> pd.DataFrame | None:
    """アップロードCSVを、大きさ・行数・形式を確かめてから読む。失敗時は None。"""
    if not check_upload(up, MAX_CSV_BYTES, page, kind):
        return None
    try:
        df = pd.read_csv(io.BytesIO(up.getvalue()), nrows=MAX_CSV_ROWS + 1, **kwargs)
    except Exception as e:  # noqa: BLE001
        log_event("csv_parse_failed", "WARNING", page=page, kind=kind, error=type(e).__name__)
        st.error("CSVを読み込めませんでした。列名と形式を確認してください。")
        return None
    if len(df) > MAX_CSV_ROWS:
        log_event("upload_rejected", "WARNING", page=page, kind=kind, reason="too_many_rows")
        st.error(f"行数が多すぎます（上限 {MAX_CSV_ROWS:,} 行）。")
        return None
    return df


# ─────────────────────────────────────────────
# 出力の無害化：CSVの数式インジェクション対策
# ─────────────────────────────────────────────
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _neutralize(v):
    if isinstance(v, str) and v.startswith(_FORMULA_START):
        return "'" + v
    return v


def safe_csv(df: pd.DataFrame, index: bool = False) -> bytes:
    """Excel で開いたとき、= や + で始まるセルが数式として実行されないようにして CSV 化する。"""
    out = df.copy()
    for c in out.columns:
        if not pd.api.types.is_numeric_dtype(out[c]):  # object / string（pandas 3）どちらも対象
            out[c] = out[c].astype(object).map(_neutralize)
    if index and not pd.api.types.is_numeric_dtype(out.index):
        out.index = out.index.astype(object).map(_neutralize)
    return out.to_csv(index=index).encode("utf-8-sig")


# ─────────────────────────────────────────────
# 生成AIの呼び出し上限（APIキーの不正利用・課金爆発の防止）
# ─────────────────────────────────────────────
def ai_quota_ok(page: str) -> bool:
    """呼び出してよければ True を返し、回数を1つ消費する。"""
    used = st.session_state.get("_sec_ai_used", 0)
    if used >= AI_CALLS_PER_SESSION:
        log_event("ai_rate_limited", "WARNING", page=page, scope="session", used=used)
        st.warning(f"生成AIの利用は1回の訪問あたり {AI_CALLS_PER_SESSION} 回までです。")
        return False
    s = _shared()
    today = dt.datetime.now(JST).date().isoformat()
    with s["lock"]:
        if s["ai_day"] != today:
            s["ai_day"], s["ai_count"] = today, 0
        if s["ai_count"] >= AI_CALLS_PER_DAY:
            capped = True
        else:
            capped = False
            s["ai_count"] += 1
            total = s["ai_count"]
    if capped:
        log_event("ai_daily_cap_reached", "CRITICAL", page=page, cap=AI_CALLS_PER_DAY)
        st.warning("本日の生成AI利用枠に達しました。手動で雑草を選んでください。")
        return False
    st.session_state._sec_ai_used = used + 1
    log_event("ai_call", "INFO", page=page, today_total=total)
    return True


# ─────────────────────────────────────────────
# 管理者認証（ログ閲覧ページ用）
# ─────────────────────────────────────────────
def admin_ok(token: str) -> bool:
    expected = _secret("ADMIN_TOKEN")
    if not expected or len(expected) < 16:
        return False
    ok = hmac.compare_digest(token.encode(), expected.encode())
    if token and not ok:
        log_event("admin_login_failed", "WARNING", page="security_log")
    return ok
