# スマートパン屋農家を始める！ — ダッシュボード

## 起動
```bash
conda create -n bakery_dashboard python=3.11   # 初回のみ
conda activate bakery_dashboard
pip install -r requirements.txt
streamlit run app.py
```
※ Python 3.9.7 は Streamlit の対象外（古い 1.12 しか入らず `st.link_button` 等でエラー）。3.10 以上を使ってください。

## 公開（無料）
GitHubにこのフォルダをpush → https://share.streamlit.io で `app.py` を指定してDeploy。
発行されたURLをFacebook投稿に貼れば、誰でも閲覧できます。

## 写真の追加
`assets/YYYYMMDD/` フォルダに写真（.jpg/.png）を置き、`app.py` の `PHOTO_LOG` にキャプションを1行追加。
追加した写真は「📷 圃場フォト」と「🔬 AI土壌診断」の両方で自動的に選べるようになります。

## 生成AIで雑草候補を提案させる（任意）
環境変数 `ANTHROPIC_API_KEY` を設定（Streamlit Cloud では Settings → Secrets に
`ANTHROPIC_API_KEY = "sk-ant-..."`）。未設定でも手動選択で動きます。

## 構成
| ファイル | 役割 |
|---|---|
| app.py | 画面（8タブ） |
| soil_vision.py | 画像解析（ExG・大津二値化・グリッド集計）、可変施肥、指標植物のベイズ更新、生成AI呼び出し |
| assets/ | 圃場写真（日付フォルダ） |


補足
次回以降は、conda activate bakery を実行してから streamlit run app.py で起動します。
conda create が "Solving environment" のまま長時間止まる場合は、Anaconda 本体が古いことが原因です。conda create -n bakery python=3.11 -y --override-channels -c conda-forge を試してください。

