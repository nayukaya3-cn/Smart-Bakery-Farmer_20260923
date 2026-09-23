# スマートパン屋農家を始める！ — ダッシュボード

## 起動
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 公開（無料）
GitHubにこのフォルダをpush → https://share.streamlit.io で `app.py` を指定してDeploy。
発行されたURLをFacebook投稿に貼れば、誰でも閲覧できます。

## 写真の追加
`assets/YYYYMMDD/` フォルダに写真を置き、`app.py` の `PHOTO_LOG` にキャプションを1行追加。

## 構成
ホーム / 播種シミュレーター / 圃場モニター / 原料レジリエンス / 探究学習プログラム / 活動ログ / 圃場フォト
