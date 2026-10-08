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

## 3Dプリンター・AIロボットのタブに記録を載せる
| 置き場所 | 表示されるタブ |
|---|---|
| `assets/3d_printer/YYYYMMDD/` | 🖨️ 3Dプリンター |
| `assets/robot/YYYYMMDD/` | 🤖 AIロボット |

- 対応形式：画像（jpg / png / gif / webp）、動画（mov / mp4 / m4v / webm）、PDF、テキスト（txt / md）
- ファイル名がそのまま説明文になります（例：`太い持ち手_初印刷-1.jpg` →「太い持ち手 初印刷」）。
- PDFはページを画像にして表示します（最初の10ページまで。全体は「PDFを保存」から）。
- iPhoneの .mov（HEVC）は Chrome で再生できないことがあります。設定 → カメラ → フォーマット →「互換性優先」で撮るか、mp4 に変換すると確実です。
- GitHub のファイル1つあたりの上限は 100MB です。長い動画は短く切るか YouTube に置いてリンクを貼ってください。
- 各タブの「➕ ファイルを取り込んで確認する」は、そのセッション内だけの確認用です（公開ページには残りません）。

## 「💻 情報Ⅰ」タブ：教材の追加と Google Colab
- 例題1〜3のノートブック：`notebooks/joho1_examples.ipynb`（タブの「▶ Google Colab で例題を開く」から開く）
- 教材を追加するときは `assets/joho1/YYYYMMDD/` に置く
  - `.ipynb` →「▶ Google Colab で開く」ボタンが付く（GitHub に置いたものだけ）
  - `.py` → 表示＋「Colab 用ノートブック（.ipynb）に変換して保存」（`# %%` の行でセルを区切れる）
  - `.pdf` `.md` `.txt` `.csv` 画像 → そのまま表示
- Colab のボタンは、リポジトリが **公開（Public）** で、ファイルが GitHub の `main` ブランチにあるときに動きます。
  リポジトリ名を変えたら `media_gallery.py` の `GITHUB_REPO` を直してください。

## 生成AIで雑草候補を提案させる（任意）
環境変数 `ANTHROPIC_API_KEY` を設定（Streamlit Cloud では Settings → Secrets に
`ANTHROPIC_API_KEY = "sk-ant-..."`）。未設定でも手動選択で動きます。

## 構成
| ファイル | 役割 |
|---|---|
| app.py | 画面（11タブ） |
| media_gallery.py | 画像・動画・PDF・テキスト・ノートブックの表示部品、Colab リンク |
| notebooks/ | Google Colab 用ノートブック |
| soil_vision.py | 画像解析（ExG・大津二値化・グリッド集計）、可変施肥、指標植物のベイズ更新、生成AI呼び出し |
| assets/ | 圃場写真（日付フォルダ） |


補足
次回以降は、conda activate bakery を実行してから streamlit run app.py で起動します。
conda create が "Solving environment" のまま長時間止まる場合は、Anaconda 本体が古いことが原因です。conda create -n bakery python=3.11 -y --override-channels -c conda-forge を試してください。


## 📋 学校向け：記録が残る探究（`pages/1_📋_学校向け_記録が残る探究.py`）
通信制高校・サポート校の探究学習の外部フィールドとして、学校が「適正な教育」を説明できる記録を用意するページです。
- **ルーブリック**：5観点×4段階（問いを立てる／①計算する／②可視化する／③自分の条件で判断する／安全・協働・記録）。観点や記述はファイル冒頭の `RUBRIC` を書きかえると全体に反映されます。
- **活動ログ**：生徒ID（匿名）ごとの日付・開始/終了・活動・取得データ・成果物・安全説明・体調確認・所見。
- **記録ダッシュボード**：実施回数・延べ学習時間・安全確認の実施率・ルーブリックの伸び・記入漏れの検出、学校への**実施報告書**（テキスト）を自動作成。
- 初期表示は**架空の記入例**です（実施実績ではありません）。サイドバーの「空の記録から始める」で切り替え。
- 記録はサーバーに残りません。CSVで保存し、次回CSVを読み込んで復元します。
- 指導者の資格は `INSTRUCTORS`、更新日は `UPDATED` を書きかえて更新します。
