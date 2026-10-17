/**
 * 作業日誌 Googleフォーム ＋ 自動集計（Google Apps Script）
 * ------------------------------------------------------------
 * できること
 *   1. 作業日誌を入力する Google フォームを作る（スマホから入力できる）
 *   2. 回答を「日誌」シートに、解析ページと同じ列（ID,日付,記入者,作業,本文,止まった時間(分),影響,備考）で自動追記する
 *      ID は D001, D002 … と自動で振る
 *   3. 「集計」シートで、作業×月の件数・「遅れ」「故障」「人手」の回数と件数・止まった時間を自動集計する
 *   4. メニュー「作業日誌 → 解析用CSVを作る」で、氏名・取引先名を伏せた CSV を Drive に保存する
 *      → スマートパン屋農家ダッシュボード「🔤 作業日誌テキスト分析」に読み込める
 *   5. 写真（任意・最大5枚）を受け付ける。届いた写真は日誌IDの名前（D012_1.jpg）に付け替えて
 *      「作業日誌_写真/YYYYMMDD」フォルダに移す（Googleが付ける回答者名をファイル名から消すため）
 *   6. メニュー「作業日誌 → 写真をZIPで保存（assets用）」で、月ごとの写真を diary/YYYYMMDD/D012_1.jpg の形でZIPにする
 *      → ダッシュボードの「写真をassetsに取り込む」で位置情報を消してから、リポジトリの assets/ に置く
 *
 * 使い方（最初の1回だけ）
 *   1. Google スプレッドシートを新しく作る（名前は例えば「work_diary_202610」）
 *   2. メニュー「拡張機能 → Apps Script」を開き、このファイルの中身を全部貼りつけて保存
 *   3. 関数「setup」を選んで ▶ 実行 → 権限を許可する
 *   4. スプレッドシートを再読み込みすると、メニューに「作業日誌」が出る
 *   5. 「設定」シートで記入者・匿名化辞書を直し、「作業日誌 → フォームの選択肢を更新」
 *   6. 写真の設問だけは Apps Script から作れない（Google の制限）ので、フォームの編集画面で1問足す：
 *      「＋」→ 質問の種類「ファイルのアップロード」→ タイトルを「写真（任意）」→
 *      特定のファイル形式のみ：画像／ファイルの最大数：5／最大サイズ：10MB → 必須はオフ
 *      → メニュー「作業日誌 → 写真の設問を確かめる」で、正しく足せたかを確かめる
 *   7. メニュー「作業日誌 → フォームの説明文を更新」で、写真の設問に「困りごとがあった日に1枚撮る」の案内を入れる
 *      （作成済みのフォームの説明文を新しくするときも、これを実行する。回答の記録は消えない）
 *
 * 方針
 *   - フォームはメールアドレスを集めない（記入者は仮名で選ぶ）
 *   - 日誌の原文は、このスクリプトから外部の生成AIに送らない
 *   - 写真の設問があるフォームは、回答者に Google アカウントでのログインを求める（Google の仕様）。
 *     写真のファイル名には回答者名が付くので、届いたらすぐ日誌IDの名前に付け替える
 *   - 写真には位置情報（GPS）が残ることがある。公開リポジトリに置く前に必ず消す（ダッシュボード側で消せる）
 *   - 人の顔・車のナンバー・取引先の看板は写さない
 */

// ===== 設定（setup のときの初期値。あとは「設定」シートで直す） =====
const CONFIG = {
  formTitle: '作業日誌',
  sheetDiary: '日誌',
  sheetSummary: '集計',
  sheetSettings: '設定',
  photoFolder: '作業日誌_写真',
  maxPhotos: 5,
  idPrefix: 'D',
  writers: ['記入者A', '記入者B', '記入者C', '記入者D', '記入者E'],
  tasks: ['播種', '育苗', '除草', '収穫', '出荷', '機械整備', 'その他'],
  impacts: ['なし', '作業', '出荷', '品質'],
  keywords: ['遅れ', '故障', '人手'],
  // 否定・充足の言い方（この形の日誌は「困りごとなし」の候補）。RE2 の正規表現
  negPatterns: {
    '遅れ': '(遅れ|遅延)(は|が|も)?(ない|なし|なかった|無し)',
    '故障': '故障(は|が|も)?(ない|なし|なかった|無し)',
    '人手': '人手(は|が|も)?(足りた|足りている|十分)',
  },
};

// 写真の2列は末尾に足す（既存の列の位置を変えると集計の数式がずれるため）
const HEADERS = ['ID', '日付', '記入者', '作業', '本文', '止まった時間(分)', '影響', '備考', '月', '受付時刻', '写真', '写真の説明'];
const EXPORT_IDX = [0, 1, 2, 3, 4, 5, 6, 7, 10, 11]; // CSV に出す列：ID〜備考、写真、写真の説明
const COL_PHOTO = 11;   // K列（1始まり）
const COL_PHOTO_NOTE = 12;
const Q = { // フォームの設問タイトル（集計とトリガーがこの名前で読む）
  date: '日付',
  writer: '記入者',
  task: '作業',
  body: '本文（その日の作業と気づいたこと）',
  stop: '止まった時間（分）',
  impact: '影響',
  note: '備考',
  photo: '写真（任意）',
  photoNote: '写真の説明（任意）',
};

// フォームの説明文（setup と「フォームの説明文を更新」の両方で使う）
// 困りごとの日に1枚撮ってもらうと、写真が日誌IDで結びつき、ダッシュボードの画像分析で
// 「テキストに書かれた困りごとが写真でも見えるか」を突き合わせる根拠になる。
const FORM_DESCRIPTION =
  '1日1件、その日の作業を記入してください。\n' +
  '・本文には氏名や取引先名を書かず、「担当」「取引先」などと書いてください。\n' +
  '・困りごとがなかった日も「特に問題なし」と記入してください（分母になります）。\n' +
  '・困りごと（遅れ・故障・人手不足）があった日は、その様子を写真で1枚撮ってください。' +
  '困りごとがない日は撮らなくてかまいません。\n' +
  '・写真は最大5枚です。人の顔・車のナンバー・取引先の看板は写さないでください。';
const PHOTO_HELP =
  '困りごとがあった日は、その様子を1枚撮ってください。' +
  '例：故障した機械の部位／刈り残した範囲／積み残した収穫物。人の顔・車のナンバー・看板は写さない。';
const PHOTO_NOTE_HELP = '何を写したか。例：故障した草刈機の刃／雨で入れなかった畝／積み残した収穫かご';

// ===================================================================
// メニュー
// ===================================================================
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('作業日誌')
    .addItem('解析用CSVを作る（匿名化）', 'exportCsv')
    .addItem('フォームの選択肢を更新', 'refreshChoices')
    .addItem('フォームのURLを表示', 'showFormUrl')
    .addSeparator()
    .addItem('写真の設問を確かめる', 'checkPhotoItem')
    .addItem('フォームの説明文を更新', 'updateFormTexts')
    .addItem('写真をZIPで保存（assets用）', 'exportPhotosZip')
    .addSeparator()
    .addItem('集計シートを作り直す', 'buildSummary')
    .addToUi();
}

// ===================================================================
// 最初の1回：シート・フォーム・トリガーを作る
// ===================================================================
function setup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const props = PropertiesService.getDocumentProperties();
  if (props.getProperty('FORM_ID')) {
    SpreadsheetApp.getUi().alert('すでに設定済みです。フォームを作り直す場合は、関数 resetSetup を実行してから setup をもう一度実行してください（日誌シートの記録は消えます）。');
    return;
  }

  // 日誌シート
  const diary = ss.getSheetByName(CONFIG.sheetDiary) || ss.insertSheet(CONFIG.sheetDiary, 0);
  diary.clear();
  diary.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight('bold').setBackground('#f3ead7');
  diary.setFrozenRows(1);
  diary.getRange('B:B').setNumberFormat('yyyy-mm-dd');
  diary.getRange('I:I').setNumberFormat('@');
  diary.setColumnWidth(5, 420);
  diary.getRange('E:E').setWrap(true);

  buildSettings_(ss);

  // フォーム（回答の控えは別シート「フォームの回答」に入る。分析は「日誌」シートを使う）
  const form = FormApp.create(CONFIG.formTitle);
  form.setDescription(FORM_DESCRIPTION);
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setConfirmationMessage('記録しました。ありがとうございました。');
  buildQuestions_(form);
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  props.setProperty('FORM_ID', form.getId());
  ScriptApp.newTrigger('onFormSubmit').forForm(form).onFormSubmit().create();

  buildSummary();
  SpreadsheetApp.flush();
  SpreadsheetApp.getUi().alert(
    'フォームを作りました。\n\n入力用URL：\n' + form.getPublishedUrl() +
    '\n\n「設定」シートで記入者と匿名化辞書を直したら、メニュー「作業日誌 → フォームの選択肢を更新」を実行してください。' +
    '\n\n写真の設問は、フォームの編集画面で手で1問足します（手順はメニュー「作業日誌 → 写真の設問を確かめる」）。'
  );
}

function buildQuestions_(form) {
  form.addDateItem().setTitle(Q.date).setRequired(true);
  form.addListItem().setTitle(Q.writer).setChoiceValues(CONFIG.writers).setRequired(true)
    .setHelpText('実名ではなく仮名を選びます');
  form.addMultipleChoiceItem().setTitle(Q.task).setChoiceValues(CONFIG.tasks).setRequired(true)
    .setHelpText('主な作業を1つ選びます（決まった語にそろえると集計がずれません）');
  form.addParagraphTextItem().setTitle(Q.body).setRequired(true)
    .setHelpText('例：雨で除草が遅れた。／草刈機が故障。／特に問題なし。');
  form.addTextItem().setTitle(Q.stop).setRequired(true)
    .setHelpText('困りごとで作業が止まった時間。なければ 0')
    .setValidation(FormApp.createTextValidation()
      .requireNumberBetween(0, 1440)
      .setHelpText('0〜1440 の数字で入力してください')
      .build());
  form.addMultipleChoiceItem().setTitle(Q.impact).setChoiceValues(CONFIG.impacts).setRequired(true)
    .setHelpText('困りごとが何に響いたか、いちばん大きいものを1つ');
  form.addParagraphTextItem().setTitle(Q.note).setRequired(false);
  // 写真の設問（ファイルのアップロード）は Apps Script では作れないので、編集画面で足す。説明欄だけ先に作る
  form.addTextItem().setTitle(Q.photoNote).setRequired(false)
    .setHelpText(PHOTO_NOTE_HELP);
}

function buildSettings_(ss) {
  const sh = ss.getSheetByName(CONFIG.sheetSettings) || ss.insertSheet(CONFIG.sheetSettings);
  sh.clear();
  const cols = [
    ['記入者（フォームの選択肢）'].concat(CONFIG.writers),
    ['作業（フォームの選択肢）'].concat(CONFIG.tasks),
    ['影響（フォームの選択肢）'].concat(CONFIG.impacts),
    ['匿名化：氏名（敬称の前）', '（例）山田', '（例）佐藤'],
    ['匿名化：取引先名', '（例）みどり青果'],
  ];
  cols.forEach((c, i) => {
    sh.getRange(1, i + 1, c.length, 1).setValues(c.map(v => [v]));
  });
  sh.getRange(1, 1, 1, cols.length).setFontWeight('bold').setBackground('#f3ead7');
  sh.setFrozenRows(1);
  sh.getRange(1, 7).setValue('メモ').setFontWeight('bold');
  sh.getRange(2, 7, 4, 1).setValues([
    ['選択肢を変えたら、メニュー「作業日誌 → フォームの選択肢を更新」'],
    ['匿名化辞書は CSV 出力のときだけ使います（日誌シートの原文は変えません）'],
    ['「（例）」で始まる行は無視します。実際の名前に書きかえてください'],
    ['作業の名前を途中で変えると、過去の行と集計が分かれます'],
  ]);
  sh.autoResizeColumns(1, 7);
}

// ===================================================================
// 回答が届いたら「日誌」シートに1行追加（ID を自動採番）
// ===================================================================
function onFormSubmit(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const ans = {};
    let photoIds = [];
    e.response.getItemResponses().forEach(r => {
      const item = r.getItem();
      if (item.getType() === FormApp.ItemType.FILE_UPLOAD) {
        photoIds = photoIds.concat(r.getResponse() || []); // 写真はファイルIDの配列で届く
      } else {
        ans[item.getTitle()] = r.getResponse();
      }
    });

    const ss = SpreadsheetApp.getActiveSpreadsheet() || SpreadsheetApp.openById(getSsId_());
    const diary = ss.getSheetByName(CONFIG.sheetDiary);
    ensureHeaders_(diary);
    const last = diary.getLastRow();
    const used = last < 2 ? [] : diary.getRange(2, 1, last - 1, 1).getValues()
      .map(r => parseInt(String(r[0]).replace(CONFIG.idPrefix, ''), 10)).filter(x => !isNaN(x));
    const n = (used.length ? Math.max.apply(null, used) : 0) + 1; // 行を消しても ID が重ならない
    const id = CONFIG.idPrefix + ('000' + n).slice(-Math.max(3, String(n).length));

    const d = ans[Q.date] ? new Date(ans[Q.date] + 'T00:00:00+09:00') : e.response.getTimestamp();
    const month = Utilities.formatDate(d, 'Asia/Tokyo', 'yyyy-MM');
    const stop = Number(ans[Q.stop] || 0);

    const photos = photoIds.length ? movePhotos_(ss, photoIds, id, d) : [];

    diary.appendRow([
      id, d, ans[Q.writer] || '', ans[Q.task] || '', clean_(ans[Q.body]), stop,
      ans[Q.impact] || '', clean_(ans[Q.note]), "'" + month, e.response.getTimestamp(),
      photos.join(';'), clean_(ans[Q.photoNote]),
    ]);
  } finally {
    lock.releaseLock();
  }
}

// 以前の setup で作った日誌シートにも、写真の2列の見出しを足す
function ensureHeaders_(diary) {
  const h = diary.getRange(1, COL_PHOTO, 1, 2).getValues()[0];
  if (h[0] !== HEADERS[COL_PHOTO - 1] || h[1] !== HEADERS[COL_PHOTO_NOTE - 1]) {
    diary.getRange(1, COL_PHOTO, 1, 2).setValues([[HEADERS[COL_PHOTO - 1], HEADERS[COL_PHOTO_NOTE - 1]]])
      .setFontWeight('bold').setBackground('#f3ead7');
  }
}

// 写真を「作業日誌_写真/YYYYMMDD/D012_1.jpg」に付け替える（回答者名の入ったファイル名を残さない）
function movePhotos_(ss, ids, diaryId, d) {
  const day = Utilities.formatDate(d, 'Asia/Tokyo', 'yyyyMMdd');
  const folder = childFolder_(photoRoot_(ss), day);
  const names = [];
  ids.slice(0, CONFIG.maxPhotos).forEach((fid, k) => {
    try {
      const f = DriveApp.getFileById(fid);
      const ext = (f.getName().match(/\.(jpe?g|png|webp|heic)$/i) || ['.jpg'])[0].toLowerCase();
      const name = diaryId + '_' + (k + 1) + ext;
      f.setName(name);
      f.setDescription('作業日誌 ' + diaryId);
      f.moveTo(folder);
      names.push(name);
    } catch (err) {
      console.warn('写真を移せませんでした: ' + err); // 写真が無くても日誌の記録は止めない
    }
  });
  return names;
}

function photoRoot_(ss) {
  const parents = DriveApp.getFileById(ss.getId()).getParents();
  const base = parents.hasNext() ? parents.next() : DriveApp.getRootFolder();
  return childFolder_(base, CONFIG.photoFolder);
}

function childFolder_(parent, name) {
  const it = parent.getFoldersByName(name);
  return it.hasNext() ? it.next() : parent.createFolder(name);
}

function getSsId_() {
  const formId = PropertiesService.getDocumentProperties().getProperty('FORM_ID');
  return FormApp.openById(formId).getDestinationId();
}

// 改行は全角スペースに（CSV と1行1件の解析に合わせる）。数式として解釈される先頭記号を無害化
function clean_(s) {
  let t = String(s || '').replace(/\r?\n/g, '　').trim();
  if (/^[=+\-@]/.test(t)) t = "'" + t;
  return t;
}

// ===================================================================
// 集計シート（数式なので、回答が届くたびに自動で更新される）
// ===================================================================
function buildSummary() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(CONFIG.sheetSummary) || ss.insertSheet(CONFIG.sheetSummary, 1);
  sh.clear();
  sh.getCharts().forEach(c => sh.removeChart(c));
  const D = "'" + CONFIG.sheetDiary + "'!";
  const body = D + '$E$2:$E';
  const head = r => sh.getRange(r).setFontWeight('bold').setBackground('#f3ead7');

  // ① 分母
  sh.getRange('A1').setValue('作業日誌の集計（自動更新）').setFontSize(14).setFontWeight('bold');
  sh.getRange('A2:B2').setValues([['日誌の件数（分母）', '=COUNTA(' + D + 'A2:A)']]);
  sh.getRange('A3:B3').setValues([['止まった時間の合計(分)', '=SUM(' + D + 'F2:F)']]);
  sh.getRange('B2:B3').setFontWeight('bold');

  // ② 検索語：回数・件数・否定の形
  sh.getRange('A5').setValue('① 検索語：回数と件数（件数は原文で確かめる前の「候補」）').setFontWeight('bold');
  const kwHead = ['検索語', '回数', '件数', '件数の割合', '否定の形（困りごとなし候補）', '否定を除いた件数', '否定の正規表現（編集可）'];
  sh.getRange(6, 1, 1, kwHead.length).setValues([kwHead]);
  head('A6:G6');
  CONFIG.keywords.forEach((kw, i) => {
    const r = 7 + i;
    sh.getRange(r, 1).setValue(kw);
    sh.getRange(r, 7).setValue(CONFIG.negPatterns[kw] || '');
    sh.getRange(r, 2, 1, 5).setFormulas([[
      '=IF(A' + r + '="","",SUMPRODUCT((LEN(' + body + ')-LEN(SUBSTITUTE(' + body + ',A' + r + ',"")))/LEN(A' + r + ')))',
      '=IF(A' + r + '="","",COUNTIF(' + body + ',"*"&A' + r + '&"*"))',
      '=IF(OR(A' + r + '="",$B$2=0),"",C' + r + '/$B$2)',
      '=IF(G' + r + '="","",SUMPRODUCT(ISNUMBER(FIND(A' + r + ',' + body + '))*REGEXMATCH(' + body + '&"",G' + r + ')))',
      '=IF(A' + r + '="","",C' + r + '-N(E' + r + '))',
    ]]);
  });
  const kwEnd = 6 + CONFIG.keywords.length;
  sh.getRange('D7:D' + kwEnd).setNumberFormat('0%');
  sh.getRange('A' + (kwEnd + 1)).setValue(
    '回数＝語が現れた数（1件に2回なら2）／件数＝その語を含む日誌の数。否定の形は「その語を含み、かつ否定の言い方に当たる日誌」。「人手が足りない」は「ない」を含むが困りごと。最終判断は原文で。'
  ).setFontColor('#777777');

  // ③ 作業×月（件数）
  const r1 = kwEnd + 3;
  sh.getRange(r1, 1).setValue('② 作業 × 月：日誌の件数').setFontWeight('bold');
  sh.getRange(r1 + 1, 1).setFormula(
    '=IFERROR(QUERY(' + D + 'A1:I,"select D, count(A) where A is not null group by D pivot I",1),"（まだ回答がありません）")'
  );

  // ④ 作業別・影響別・月別の止まった時間
  const r2 = r1 + CONFIG.tasks.length + 4;
  sh.getRange(r2, 1).setValue('③ 作業別：止まった時間と件数').setFontWeight('bold');
  sh.getRange(r2 + 1, 1).setFormula(
    '=IFERROR(QUERY(' + D + 'A1:I,"select D, sum(F), count(A), avg(F) where A is not null group by D order by sum(F) desc ' +
    'label sum(F) \'止まった時間(分)\', count(A) \'件数\', avg(F) \'1件あたり(分)\'",1),"")'
  );
  sh.getRange(r2, 6).setValue('影響別').setFontWeight('bold');
  sh.getRange(r2 + 1, 6).setFormula(
    '=IFERROR(QUERY(' + D + 'A1:I,"select G, sum(F), count(A) where A is not null group by G order by sum(F) desc ' +
    'label sum(F) \'止まった時間(分)\', count(A) \'件数\'",1),"")'
  );
  sh.getRange(r2, 10).setValue('月別').setFontWeight('bold');
  sh.getRange(r2 + 1, 10).setFormula(
    '=IFERROR(QUERY(' + D + 'A1:I,"select I, sum(F), count(A) where A is not null group by I order by I ' +
    'label I \'月\', sum(F) \'止まった時間(分)\', count(A) \'件数\'",1),"")'
  );
  sh.getRange(r2 + 1, 1, CONFIG.tasks.length + 2, 13).setNumberFormat('0.#');

  // ⑤ 困りごと候補の一覧（検索語を含み、否定の形ではない日誌）→ 原文を読む順番
  const r3 = r2 + CONFIG.tasks.length + 5;
  sh.getRange(r3, 1).setValue('④ 原文を読む候補（検索語を含み、否定の形ではない日誌）').setFontWeight('bold');
  const kwRe = CONFIG.keywords.join('|');
  const negRe = CONFIG.keywords.map(k => CONFIG.negPatterns[k]).filter(Boolean).join('|');
  sh.getRange(r3 + 1, 1).setFormula(
    '=IFERROR(FILTER({' + D + 'A2:A,' + D + 'B2:B,' + D + 'D2:D,' + D + 'E2:E,' + D + 'F2:F},' +
    'REGEXMATCH(' + body + '&"","' + kwRe + '"),NOT(REGEXMATCH(' + body + '&"","' + negRe + '"))),"（該当なし）")'
  );
  sh.getRange(r3 + 1, 2, 500, 1).setNumberFormat('yyyy-mm-dd');

  // グラフ：作業別の止まった時間
  const chart = sh.newChart().asBarChart()
    .addRange(sh.getRange(r2 + 1, 1, CONFIG.tasks.length + 1, 2))
    .setPosition(r1, 15, 0, 0)
    .setOption('title', '作業別：止まった時間（分）')
    .setOption('legend', { position: 'none' })
    .setNumHeaders(1)
    .build();
  sh.insertChart(chart);

  sh.setColumnWidth(1, 160);
  sh.setColumnWidth(4, 360);
  sh.setColumnWidth(7, 300);
}

// ===================================================================
// 解析用CSV（匿名化して Drive に保存）
// ===================================================================
function exportCsv() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const diary = ss.getSheetByName(CONFIG.sheetDiary);
  const last = diary.getLastRow();
  if (last < 2) { SpreadsheetApp.getUi().alert('日誌がまだありません。'); return; }

  const set = ss.getSheetByName(CONFIG.sheetSettings);
  const names = readList_(set, 4);
  const partners = readList_(set, 5);

  ensureHeaders_(diary);
  const rows = diary.getRange(1, 1, last, HEADERS.length).getValues()
    .map(r => EXPORT_IDX.map(j => r[j]));
  let masked = 0;
  const out = rows.map((r, i) => r.map((v, j) => {
    if (i === 0) return v;
    if (j === 1 && v instanceof Date) return Utilities.formatDate(v, 'Asia/Tokyo', 'yyyy-MM-dd');
    if (j === 4 || j === 7 || j === 9) { // 本文・備考・写真の説明
      const m = mask_(String(v), names, partners);
      if (m !== String(v)) masked++;
      return m;
    }
    return v;
  }));

  // 匿名化のあとに辞書の語が残っていないか
  const joined = out.slice(1).map(r => r[4] + ' ' + r[7] + ' ' + r[9]).join('\n');
  const left = names.concat(partners).filter(w => joined.indexOf(w) !== -1);
  if (left.length) {
    SpreadsheetApp.getUi().alert('匿名化のあとに残った語があります：' + left.join('、') + '\nCSVは作りませんでした。');
    return;
  }

  const csv = '﻿' + out.map(r => r.map(csvCell_).join(',')).join('\r\n') + '\r\n';
  const name = 'work_diary_' + Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyyMMdd') + '.csv';
  const file = DriveApp.createFile(name, csv, MimeType.CSV);
  const parents = DriveApp.getFileById(ss.getId()).getParents();
  if (parents.hasNext()) file.moveTo(parents.next()); // スプレッドシートと同じフォルダに置く

  SpreadsheetApp.getUi().alert(
    'CSVを保存しました：' + name + '\n' +
    '日誌 ' + (out.length - 1) + ' 件（匿名化で置き換えた欄：' + masked + '）\n\n' + file.getUrl() +
    '\n\nダッシュボード「🔤 作業日誌テキスト分析」で読み込めます。外部の生成AIには貼らないでください。'
  );
}

function readList_(sheet, col) {
  if (!sheet) return [];
  const n = sheet.getLastRow();
  if (n < 2) return [];
  return sheet.getRange(2, col, n - 1, 1).getValues()
    .map(r => String(r[0]).trim())
    .filter(v => v && v.indexOf('（例）') !== 0);
}

function mask_(text, names, partners) {
  const byLen = a => a.slice().sort((x, y) => y.length - x.length);
  byLen(partners).forEach(w => { text = text.split(w).join('［取引先］'); });
  byLen(names).forEach(w => { text = text.split(w).join('［人名］'); });
  return text;
}

function csvCell_(v) {
  let s = v === null || v === undefined ? '' : String(v);
  if (/^[=+\-@]/.test(s)) s = "'" + s; // Excel で開いたときの数式実行を防ぐ
  return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

// ===================================================================
// 設定シートの選択肢をフォームに反映
// ===================================================================
function refreshChoices() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const set = ss.getSheetByName(CONFIG.sheetSettings);
  const form = FormApp.openById(PropertiesService.getDocumentProperties().getProperty('FORM_ID'));
  const lists = { [Q.writer]: readList_(set, 1), [Q.task]: readList_(set, 2), [Q.impact]: readList_(set, 3) };
  form.getItems().forEach(item => {
    const vals = lists[item.getTitle()];
    if (!vals || !vals.length) return;
    if (item.getType() === FormApp.ItemType.LIST) item.asListItem().setChoiceValues(vals);
    if (item.getType() === FormApp.ItemType.MULTIPLE_CHOICE) item.asMultipleChoiceItem().setChoiceValues(vals);
  });
  SpreadsheetApp.getUi().alert('フォームの選択肢を更新しました。');
}

// フォームを作り直したいとき（フォーム本体は Drive に残るので、不要なら手で削除する）
function resetSetup() {
  PropertiesService.getDocumentProperties().deleteProperty('FORM_ID');
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'onFormSubmit') ScriptApp.deleteTrigger(t);
  });
  SpreadsheetApp.getUi().alert('設定を消しました。setup をもう一度実行できます。');
}

function showFormUrl() {
  const form = FormApp.openById(PropertiesService.getDocumentProperties().getProperty('FORM_ID'));
  SpreadsheetApp.getUi().alert('入力用URL：\n' + form.getPublishedUrl() + '\n\n編集用URL：\n' + form.getEditUrl());
}

// ===================================================================
// 写真
// ===================================================================
// 写真の設問（ファイルのアップロード）が足されているかを確かめる
function checkPhotoItem() {
  const form = FormApp.openById(PropertiesService.getDocumentProperties().getProperty('FORM_ID'));
  const ups = form.getItems(FormApp.ItemType.FILE_UPLOAD);
  const ui = SpreadsheetApp.getUi();
  if (!ups.length) {
    ui.alert(
      '写真の設問がまだありません。\n\n' +
      'フォームの編集画面（下のURL）で：\n' +
      '1. 「＋」で質問を足し、種類を「ファイルのアップロード」にする\n' +
      '2. タイトル：' + Q.photo + '\n' +
      '3. 特定のファイル形式のみ許可：画像\n' +
      '4. ファイルの最大数：' + CONFIG.maxPhotos + '／最大ファイルサイズ：10MB\n' +
      '5. 「必須」はオフ。「' + Q.photoNote + '」の上に移動する\n' +
      '6. 足したら、メニュー「作業日誌 → フォームの説明文を更新」で撮り方の案内を入れる\n\n' +
      '※ この設問を足すと、回答者は Google アカウントでのログインが必要になります。\n\n' + form.getEditUrl()
    );
    return;
  }
  const item = ups[0];
  const title = item.getTitle();
  const helpOk = item.getHelpText() === PHOTO_HELP;
  ui.alert('写真の設問があります：「' + title + '」\n' +
    (title === Q.photo ? '' : 'タイトルは「' + Q.photo + '」にそろえると説明と合います（動作はタイトルに関係なく動きます）。\n') +
    (helpOk ? '' : '撮り方の案内（困りごとがあった日に1枚撮る）がまだです。メニュー「作業日誌 → フォームの説明文を更新」を実行してください。\n') +
    '\n届いた写真は「' + CONFIG.photoFolder + '/日付」フォルダに、日誌IDの名前で入ります。');
}

// 作成済みのフォームの説明文・写真の設問の案内を、このファイルの文言にそろえる（回答の記録は消えない）
function updateFormTexts() {
  const ui = SpreadsheetApp.getUi();
  const id = PropertiesService.getDocumentProperties().getProperty('FORM_ID');
  if (!id) { ui.alert('まだフォームがありません。先に setup を実行してください。'); return; }
  const form = FormApp.openById(id);
  form.setDescription(FORM_DESCRIPTION);
  const done = ['フォームの説明文'];
  const ups = form.getItems(FormApp.ItemType.FILE_UPLOAD);
  if (ups.length) { ups[0].setHelpText(PHOTO_HELP); done.push('写真の設問の案内'); }
  const notes = form.getItems().filter(function (it) { return it.getTitle() === Q.photoNote; });
  if (notes.length) { notes[0].setHelpText(PHOTO_NOTE_HELP); done.push('写真の説明の例'); }
  ui.alert('更新しました：' + done.join('・') +
    (ups.length ? '' : '\n\n写真の設問がまだありません。足したあとで、もう一度実行してください（メニュー「写真の設問を確かめる」に手順があります）。'));
}

// 指定した月の写真を diary/YYYYMMDD/D012_1.jpg の形でZIPにし、スプレッドシートと同じフォルダに保存する
function exportPhotosZip() {
  const ui = SpreadsheetApp.getUi();
  const def = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM');
  const res = ui.prompt('写真をZIPで保存', 'どの月の写真ですか（例：' + def + '）。空欄なら今月。', ui.ButtonSet.OK_CANCEL);
  if (res.getSelectedButton() !== ui.Button.OK) return;
  const month = (res.getResponseText().trim() || def);
  if (!/^\d{4}-\d{2}$/.test(month)) { ui.alert('「2026-10」の形で入力してください。'); return; }

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const diary = ss.getSheetByName(CONFIG.sheetDiary);
  ensureHeaders_(diary);
  const last = diary.getLastRow();
  if (last < 2) { ui.alert('日誌がまだありません。'); return; }
  const rows = diary.getRange(2, 1, last - 1, HEADERS.length).getValues();
  const root = photoRoot_(ss);
  const blobs = [];
  let missing = 0;
  rows.forEach(r => {
    const d = r[1] instanceof Date ? r[1] : new Date(r[1]);
    if (Utilities.formatDate(d, 'Asia/Tokyo', 'yyyy-MM') !== month || !r[COL_PHOTO - 1]) return;
    const day = Utilities.formatDate(d, 'Asia/Tokyo', 'yyyyMMdd');
    const dayFolders = root.getFoldersByName(day);
    const folder = dayFolders.hasNext() ? dayFolders.next() : null;
    String(r[COL_PHOTO - 1]).split(';').filter(String).forEach(name => {
      const it = folder ? folder.getFilesByName(name) : null;
      if (it && it.hasNext()) {
        blobs.push(it.next().getBlob().setName('diary/' + day + '/' + name));
      } else {
        missing++;
      }
    });
  });
  if (!blobs.length) { ui.alert(month + ' の写真はありません。'); return; }

  const zipName = 'diary_photos_' + month.replace('-', '') + '.zip';
  const zip = Utilities.zip(blobs, zipName);
  const file = DriveApp.createFile(zip);
  const parents = DriveApp.getFileById(ss.getId()).getParents();
  if (parents.hasNext()) file.moveTo(parents.next());
  ui.alert(
    'ZIPを保存しました：' + zipName + '（写真 ' + blobs.length + ' 枚' + (missing ? '／見つからない写真 ' + missing + ' 枚' : '') + '）\n\n' +
    file.getUrl() + '\n\n' +
    '次の手順：\n' +
    '1. ダッシュボード「🔤 作業日誌テキスト分析」の「写真をassetsに取り込む」でこのZIPを読み込み、位置情報を消したZIPを保存\n' +
    '2. 写真を目で確かめる（人の顔・車のナンバー・看板が写っていないか）\n' +
    '3. 保存したZIPを展開し、diary フォルダごとリポジトリの assets/ にアップロード'
  );
}
