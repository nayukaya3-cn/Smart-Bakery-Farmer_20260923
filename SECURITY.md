# セキュリティ方針とインシデント対応手順

このアプリ（https://smart-bakery-farm.streamlit.app/）は、**① 記録する → ② 検知して知らせる → ③ 人が判断して対応する** の3段構えで守ります。

## 1. 守りのしくみ

| 層 | しくみ | 場所 | 記録（ログ） | アラーム |
|---|---|---|---|---|
| アプリ内 | アップロードの大きさ・行数・画像形式の検査、解凍爆弾の防止 | `security_guard.py` / `soil_vision.py` | JSON 1行ログ（Manage app → Logs） | 警告以上を Webhook |
| アプリ内 | 生成AIの呼び出し上限（1訪問3回・1日40回） | `security_guard.py` | `ai_call` / `ai_rate_limited` / `ai_daily_cap_reached` | 上限到達は CRITICAL |
| アプリ内 | CSVの数式インジェクション対策（`=` `+` `-` `@` で始まるセルを無害化） | `security_guard.safe_csv` | ― | ― |
| アプリ内 | 警告が10分に10件以上 → 攻撃の疑い | `security_guard.log_event` | `burst_detected` | CRITICAL を Webhook |
| アプリ設定 | アップロード上限60MB、エラー詳細を画面に出さない、XSRF対策 | `.streamlit/config.toml` | ― | ― |
| リポジトリ | 依存の脆弱性・危険なコード・秘密情報の混入を検査 | `.github/workflows/security-scan.yml` | Actions のレポート（90日保存） | Issue `[security]` → メール |
| リポジトリ | 6時間ごとに死活監視と、所有者以外のコミット・防御設定の変更を検知 | `.github/workflows/watchdog.yml` | Actions のログ（90日保存） | Issue `[incident]` → メール |
| リポジトリ | 依存ライブラリの更新を毎週PRで提案 | `.github/dependabot.yml` | PR履歴 | ― |

ログには **IPアドレス・氏名・ファイルの中身を残しません**。セッションは匿名IDで区別します。

## 2. 初回設定（所有者が1回だけ行う）

1. **GitHub アカウントの二段階認証（2FA）を有効にする**（Settings → Password and authentication）。乗っ取りが最大のリスクです。
2. リポジトリの Settings → Code security で、次を有効にする。
   - Dependabot alerts / Dependabot security updates
   - Secret scanning / Push protection（APIキーを誤ってpushしようとすると止めてくれる）
3. Settings → Branches で `main` にルールを追加（force push と削除を禁止）。
4. Streamlit Community Cloud の アプリ → Settings → Secrets に登録（任意）。

```toml
ANTHROPIC_API_KEY = "sk-ant-..."          # 生成AIを使う場合のみ
SECURITY_WEBHOOK_URL = "https://hooks.slack.com/services/..."  # Slack / Discord の Webhook（任意）
ADMIN_TOKEN = "16文字以上のランダムな文字列"  # 🔒セキュリティログページ用
```

   `ADMIN_TOKEN` は `python -c "import secrets; print(secrets.token_urlsafe(24))"` で作れます。
5. Anthropic Console で、APIキーに**月額の利用上限**を設定する（アプリ側の上限と二重の守り）。

## 3. ログの見方

| event | 重大度 | 意味 |
|---|---|---|
| `upload_accepted` | INFO | ファイルを受け付けた |
| `upload_rejected` | WARNING | 大きすぎる・行数が多すぎる |
| `image_rejected` | WARNING | 壊れた画像、偽装ファイル、解凍爆弾の疑い |
| `csv_parse_failed` / `csv_schema_mismatch` | WARNING | CSVの形式が違う |
| `ai_call` | INFO | 生成AIを呼んだ（その日の累計つき） |
| `ai_rate_limited` | WARNING | 1訪問の上限に達した |
| `ai_daily_cap_reached` | CRITICAL | 1日の上限に達した（不正利用の疑い） |
| `ai_call_failed` | WARNING | AI呼び出しの失敗 |
| `admin_login_failed` | WARNING | 管理者トークンの誤り |
| `burst_detected` | CRITICAL | 警告が短時間に集中（攻撃の疑い） |

## 4. インシデント対応手順

| 状況 | すぐにやること（〜1時間） | その後 |
|---|---|---|
| **APIキー漏えいの疑い**（gitleaks 検出、`ai_daily_cap_reached` の連続） | ① Anthropic Console でキーを無効化 ② Streamlit Secrets から削除 | 新しいキーを発行。履歴にキーが残っていれば履歴を書き換えるより**無効化を優先** |
| **所有者以外のコミット／防御設定の変更**（`[incident]`） | ① GitHub のパスワード変更・2FA確認・セッション全ログアウト ② 該当コミットを確認し、不正なら revert | Settings → Security log で不審な操作を確認。Deploy keys・Personal access tokens を見直す |
| **アプリに接続できない** | Streamlit Cloud の Manage app → Logs でエラーを確認 | 依存更新が原因なら直前の Dependabot PR を revert |
| **依存の脆弱性**（`[security]`） | 修正版が出ていれば Dependabot PR をマージ | 修正版がなければ、その機能を一時的に止める |
| **`burst_detected`** | 🔒セキュリティログで内容を確認。必要ならアプリを一時停止（Manage app → Reboot/Delete） | 上限値（`security_guard.py` 冒頭）を厳しくする |

対応したら、Issue に「何が起きたか／何をしたか／再発防止」を3行で書いて閉じます（これが記録になります）。

## 5. 脆弱性の報告

このアプリの脆弱性に気づいた方は、公開の Issue ではなく、Facebook のメッセージで知らせてください。
