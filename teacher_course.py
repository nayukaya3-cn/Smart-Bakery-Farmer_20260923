"""
⏱️ 学校の先生向け 3分コース ─ ホームと「📝 教科×情報Ⅰ › 科学と人間生活＝フィールドワーク事前学習」で共用

同じ関数 render() を2か所から呼ぶので、文面を直すときはここだけ書きかえれば両方に反映されます（連動）。

ピボット：「科学と人間生活」は「総合的な探究の時間（探究学習）」におけるフィールドワークの事前学習として、
         極めて親和性が高く、非常に有益な科目である。
"""
from pathlib import Path

import streamlit as st

import social as sn

FIELD_AREA_M2 = 96  # 圃場面積（㎡）。home.py と同じ値
ROOT = Path(__file__).parent

PIVOT = ("「科学と人間生活」は、「総合的な探究の時間（探究学習）」におけるフィールドワークの事前学習として、"
         "極めて親和性が高く、非常に有益な科目です。")


def page_path(no: str) -> str:
    """pages/ の中から番号で始まるファイルを探す（Mac由来の文字の違いに強くする）。"""
    hits = sorted((ROOT / "pages").glob(f"{no}_*.py"))
    return f"pages/{hits[0].name}" if hits else f"pages/{no}_"


SUBJECT_PAGE = page_path("27")    # 📝 教科×情報Ⅰ：科学と人間生活＝フィールドワーク事前学習
FIELDWORK_PAGE = page_path("26")  # 🎓 学校向けの探究：フィールドワーク伴走（❶〜❺）
SCHOOL_PAGE = page_path("1")      # 記録が残る探究（ルーブリック・活動ログ）
COMPARE_PAGE = page_path("3")     # 比べて確かめる探究（90分モデル）


def _link(page: str, label: str, icon: str) -> None:
    """ページが見つからない環境でもアプリ全体が止まらないようにする。"""
    try:
        st.page_link(page, label=label, icon=icon)
    except Exception:  # noqa: BLE001
        st.caption(f"{icon} {label}（左のメニューから開けます）")


def render(where: str = "home") -> None:
    """3分コースを描く。where="subject" のときは、教科ページ向けに見出しの説明だけ変える。"""
    st.subheader("⏱️ 学校の先生向け 3分コース")
    if where == "subject":
        st.caption("ホームの3分コースと同じ内容です。教科の先生が「事前学習として何を準備するか」を判断するために置いています。")
    else:
        st.caption("このページは情報が多いので、判断に必要なことだけを3つにまとめました。")
    st.info(f"**{PIVOT}**　教科の知識をレンズ（眼鏡）として掛けてから畑に来ると、"
            "風車も発酵肥料の湯気も「問いの種」に変わります。")
    a, b, c = st.columns(3)
    with a.container(border=True):
        st.markdown(
            "**① 1分：なぜ事前学習に効くのか**\n\n"
            "- **問いの解像度**：光や熱・微生物・自然災害を学んでおくと、現場の現象に気づける\n"
            "- **文理融合**：「技術的にできるか」と「地域が受け入れるか」を同じ現場で見る\n"
            "- **科学的アプローチ**：何を測り、どう比べ、どう記録するかを授業で先に一度やっておく\n\n"
            f"舞台は三原市西部の約{FIELD_AREA_M2}㎡の畑。小麦からパンまでを、"
            "**有事の自給力・平時の省力化と有事の自律性・地域とのつながり**の3つのレンズで観察します。"
        )
        if where != "subject":
            _link(SUBJECT_PAGE, "科目の位置づけ・単元と調査地の対応表", "🔭")
    with b.container(border=True):
        st.markdown(
            "**② 1分：パン工場の衛生管理（HACCP）と同じ骨格で伴走**\n\n"
            "- ❶ **事前**＝危害分析（見学で終わる・事故になる原因を先に点数化）\n"
            "- ❷ **日々の伴走**＝本番まで1日1課題。準備度をベイズ推定して声かけの順を決める\n"
            "- ❸ **本番**＝重要管理点（アレルゲン・暑さ指数・問いの質・写真）だけを基準で測る\n"
            "- ❹ **事後**＝予想と事実の「ずれ」をインサイトとして数える\n"
            "- ❺ **次の一手**＝ずれを次の探究に変えて提案し、4週間伴走する"
        )
        _link(FIELDWORK_PAGE, "伴走キット（❶〜❺）を開く", "🧭")
        _link(COMPARE_PAGE, "比べる探究の90分モデルを体験する", "⚖️")
    with c.container(border=True):
        st.markdown(
            "**③ 1分：安全と、次の一歩**\n\n"
            "受け入れ準備の進み具合（保険・緊急時対応など）は、**未整備の項目も含めて**"
            "「🎓 学校の先生へ › 🤝 受け入れ体制」で公開しています。\n\n"
            "いまは **フェーズ0（実証・記録）** で、**受け入れ実績はまだありません**。"
            "伴走キット（ワークシート・質問集・管理表）は、他の調査地でもそのまま使えます。"
            "有償の試行は2028〜2029年（フェーズ1）を目安にしています。\n\n"
            "それまでの間も、ご意見や情報交換は歓迎です。"
        )
        _link(SCHOOL_PAGE, "記録（ルーブリック・活動ログ）を見る", "📋")
        sn.buttons("で声をかける", stacked=True)
    st.divider()
