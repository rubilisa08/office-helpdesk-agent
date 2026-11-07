"""새솔컴퍼니 사내 헬프데스크 데모 화면: python -m streamlit run app.py"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from context import CATEGORIES, Settings, load_sections
from llm import resolve_provider
from verify import CITE_RE, ID_RE

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"

# 예시 질문: (버튼 이름, 질문). 답변·계산·되묻기·담당자 연결·범위 밖을 한 번씩 볼 수 있게 골랐다.
EXAMPLES = [
    ("IT지원 · 계정 잠김", "비밀번호를 5번 틀려서 잠겼어요. 어떻게 풀어요?"),
    ("인사 · 연차 일수", "입사 2년차인데 연차가 며칠이에요?"),
    ("총무 · 회의실 예약", "회의실은 몇 주 전부터 예약할 수 있어요?"),
    ("경비정산 · 카드 한도", "대리인데 법인카드 한도가 얼마예요?"),
    ("모호한 질문 · 야근", "야근하면 뭐 받을 수 있어요?"),
    ("규정에 없음 · 육아휴직", "육아휴직 급여는 얼마나 나와요?"),
    ("범위 밖 · 점심 메뉴", "오늘 점심 뭐 먹을까요?"),
]
# 결과별 표시 이름과 색 이름(CSS 클래스)
STATUS = {"answered": ("답변", "ok"), "abstained": ("담당자 연결", "warn"), "clarify": ("되묻기", "info")}
AVATAR = {"user": ":material/person:", "assistant": ":material/support_agent:"}

st.set_page_config(page_title="사내 헬프데스크", page_icon="🏢", layout="wide", initial_sidebar_state="collapsed")

# 디자인: 오피스 블루(밝은 배경 + 남색 상단 바 + 흰 카드, 근거는 세로 타임라인). 테마 기본값은 .streamlit/config.toml
st.markdown("""
<style>
:root {
  --fr-navy: #0C447C; --fr-accent: #185FA5; --fr-accent-l: #85B7EB; --fr-tint: #E6F1FB;
  --fr-line: #D6E2F0; --fr-bg: #F4F7FB; --fr-card: #FFFFFF; --fr-text: #1B2A3D; --fr-muted: #5F6B7A;
  --fr-ok: #3B6D11; --fr-ok-bg: #EAF3DE; --fr-warn: #854F0B; --fr-warn-bg: #FAEEDA;
  --fr-info: #0C447C; --fr-info-bg: #E6F1FB; --fr-bad: #A32D2D; --fr-bad-bg: #FCEBEB;
}
.block-container { padding-top: 3.2rem; max-width: 1240px; }
/* 상단 소개 카드: 제목 + 핵심 동작 칩 4개 */
.fr-top { background: var(--fr-card); border: 1px solid var(--fr-line); border-left: 5px solid var(--fr-accent);
  border-radius: 0 12px 12px 0; padding: 14px 20px 16px; margin-bottom: 12px; }
.fr-top .row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.fr-top .name { font-size: 21px; font-weight: 700; letter-spacing: -.3px; line-height: 1.3; color: var(--fr-text); }
.fr-top .demo { font-size: 11.5px; color: var(--fr-muted); border: 1px solid var(--fr-line); border-radius: 999px;
  padding: 1px 9px; white-space: nowrap; }
.fr-top .feats { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.fr-top .feat { font-size: 12.5px; background: var(--fr-tint); color: var(--fr-navy); border-radius: 999px;
  padding: 3px 11px; white-space: nowrap; }
.fr-top .feat i { font-style: normal; margin-right: 4px; }
/* 예시 질문 칩 */
.fr-chips-h { font-size: 12.5px; color: var(--fr-muted); margin: 2px 0 6px; }
.st-key-chips { gap: 6px !important; margin-bottom: 6px; }
.st-key-chips button { border-radius: 999px !important; min-height: 30px; padding: 2px 12px !important;
  background: var(--fr-card) !important; border: 1px solid #B5D4F4 !important; color: var(--fr-navy) !important; }
.st-key-chips button p { font-size: 12.5px !important; }
.st-key-chips button:hover { background: var(--fr-tint) !important; border-color: var(--fr-accent) !important; }
.st-key-chips .st-key-newchat button { border-color: var(--fr-line) !important; color: var(--fr-muted) !important; }
/* 대화 */
[data-testid="stChatMessage"] { background: transparent !important; padding: 2px 0 !important; gap: 10px; }
[data-testid="stChatMessage"] [data-testid^="stChatMessageAvatar"] { background: var(--fr-navy); color: #fff; border-radius: 9px; }
[data-testid="stChatMessage"]:has(.fr-user) [data-testid^="stChatMessageAvatar"] { background: #DCE6F2; color: var(--fr-navy); }
[data-testid^="stChatMessageAvatar"] [data-testid="stIconMaterial"] { color: inherit !important; }
.fr-user { font-size: 14.5px; font-weight: 600; color: var(--fr-text); padding-top: 5px; overflow-wrap: anywhere; }
.fr-user .re { display: block; font-size: 12.5px; font-weight: 400; color: var(--fr-accent); margin-top: 2px; }
.fr-card { background: var(--fr-card); border: 1px solid var(--fr-line); border-radius: 12px; padding: 12px 16px;
  font-size: 14.5px; line-height: 1.75; color: var(--fr-text); margin-bottom: 4px; }
.fr-card .body { margin-top: 6px; }
.fr-card .srcs { margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--fr-line); }
.fr-src { font-size: 12.5px; padding: 2px 0; line-height: 1.6; }
.fr-src .m { color: var(--fr-muted); font-size: 12px; }
.fr-meta { font-size: 12.5px; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; color: var(--fr-muted); }
.fr-meta b { color: var(--fr-text); font-weight: 600; }
.fr-meta .dot { color: #B4C3D6; }
.fr-meta .ok { color: var(--fr-ok); font-weight: 600; } .fr-meta .bad { color: var(--fr-bad); font-weight: 600; }
.fr-pill { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.fr-pill.ok { background: var(--fr-ok-bg); color: var(--fr-ok); }
.fr-pill.warn { background: var(--fr-warn-bg); color: var(--fr-warn); }
.fr-pill.info { background: var(--fr-info-bg); color: var(--fr-info); }
.fr-pill.bad { background: var(--fr-bad-bg); color: var(--fr-bad); }
.fr-pill.muted { background: var(--fr-bg); color: var(--fr-muted); border: 1px solid var(--fr-line); }
.fr-cite { font-family: ui-monospace, Consolas, monospace; font-size: 11.5px; padding: 1px 6px; margin: 0 1px;
  border-radius: 5px; background: var(--fr-tint); color: var(--fr-navy); white-space: nowrap; }
/* 근거 타임라인(오른쪽) */
.st-key-evidence { background: var(--fr-card); border: 1px solid var(--fr-line); border-radius: 12px; padding: 16px 18px 8px; }
.fr-panel-h { font-size: 15px; font-weight: 700; color: var(--fr-text); margin: 0 0 2px; }
.fr-panel-q { font-size: 12.5px; color: var(--fr-muted); margin-bottom: 8px; overflow-wrap: anywhere; }
.st-key-evidence [class*="st-key-tl_"] { position: relative; margin-left: 6px; padding: 0 0 14px 18px;
  border-left: 2px solid #B5D4F4; gap: .75rem; }
.st-key-evidence [class*="st-key-tl_"]::before { content: ""; position: absolute; left: -7px; top: 3px; width: 12px; height: 12px;
  border-radius: 50%; background: var(--fr-accent); box-shadow: 0 0 0 3px var(--fr-card); }
.st-key-evidence [class*="st-key-tl_4"] { border-left-color: transparent; }
.st-key-evidence [class*="st-key-tl_"][class*="-off"]::before { background: #B4C3D6; }
.fr-step { font-size: 13.5px; font-weight: 700; color: var(--fr-text); line-height: 1.4; }
.fr-step .s { font-weight: 400; color: var(--fr-muted); }
.fr-note { font-size: 12.5px; color: var(--fr-muted); line-height: 1.6; margin: 3px 0; }
.fr-chip { display: inline-block; font-size: 11.5px; padding: 0 7px; border-radius: 5px; margin: 2px 3px 0 0;
  background: var(--fr-bg); border: 1px solid var(--fr-line); color: var(--fr-text); }
.fr-catrow { display: grid; grid-template-columns: 64px 1fr 34px; gap: 8px; align-items: center; font-size: 12.5px;
  padding: 2px 0; color: var(--fr-muted); }
.fr-catrow.on { color: var(--fr-text); font-weight: 700; }
.fr-bar { position: relative; height: 7px; border-radius: 4px; background: var(--fr-tint); }
.fr-bar .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 4px; background: var(--fr-accent-l); }
.fr-catrow.on .fr-bar .fill { background: var(--fr-accent); }
.fr-bar .mark { position: absolute; top: -4px; width: 2px; height: 15px; background: var(--fr-navy); opacity: .55; }
.fr-catrow .v { text-align: right; font-variant-numeric: tabular-nums; }
.fr-verdict { display: inline-block; font-size: 12.5px; margin-top: 4px; }
.fr-check { font-size: 12.5px; padding: 3px 0; line-height: 1.5; color: var(--fr-text); }
.fr-check .x { color: var(--fr-bad); font-weight: 700; } .fr-check .o { color: var(--fr-ok); font-weight: 700; }
.fr-check .d { color: var(--fr-muted); }
.fr-cand { display: grid; grid-template-columns: 58px 1fr 48px; gap: 8px; align-items: center; font-size: 12.5px; padding: 2px 0; }
.fr-cand.dim { opacity: .55; }
.fr-trace { font-size: 11.5px; color: var(--fr-muted); padding: 8px 0 4px; border-top: 1px dashed var(--fr-line); }
/* 평가 탭 카드 */
.fr-h { font-size: 13px; font-weight: 700; margin: 4px 0 6px; }
.fr-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 4px 0 14px; }
.fr-kpi { border: 1px solid var(--fr-line); border-radius: 12px; padding: 10px 14px; background: var(--fr-card); min-width: 0; }
.fr-kpi .l { font-size: 12px; color: var(--fr-muted); margin-bottom: 4px; }
.fr-kpi .v { font-size: 16px; font-weight: 700; line-height: 1.35; overflow-wrap: anywhere; color: var(--fr-text); }
.fr-kpi .s { font-size: 12px; color: var(--fr-muted); margin-top: 3px; overflow-wrap: anywhere; }
@media (min-width: 992px) {
  /* 대화가 길어져도 근거 타임라인이 화면에 붙어 있도록: 패널의 부모들을 열 높이만큼 늘린 뒤 sticky */
  [data-testid="stColumn"]:has(.st-key-evidence) > [data-testid="stVerticalBlock"] { height: 100%; }
  [data-testid="stLayoutWrapper"]:has(> .st-key-evidence) { flex: 1 1 auto; }
  .st-key-evidence { position: sticky; top: 4rem; max-height: calc(100vh - 5rem); overflow-y: auto; }
}
@media (max-width: 760px) {
  .fr-top { padding: 12px 14px; } .fr-top .name { font-size: 17px; } .fr-top .demo { margin-left: 0; }
  .fr-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="헬프데스크를 준비하고 있어요… (처음 한 번만 30초~1분 걸려요)")
def get_agent(provider: str, knobs: tuple):
    from agent import Agent

    keys = ("top_k", "min_similarity", "confidence_threshold", "use_scope_rules", "use_term_coverage", "use_llm_gate")
    return Agent(provider, Settings(**dict(zip(keys, knobs))))


# 화면에 보이는 이름: 코드 이름 대신 사용자 언어로
TOOL_LABEL = {c["tool"]: f"{c['name']} 규정 조회" for c in CATEGORIES.values() if c["tool"]}
TOOL_LABEL.update({"abstain": "담당자 연결", "clarify": "되묻기"})
CHECK_LABEL = {"scope_rule": "범위 확인", "term_coverage": "용어 확인", "llm_gate": "근거 충분성",
               "similarity": "유사도 확인", "category": "분야 확인"}
# 진행 표시에서 노드가 끝날 때 보여 줄 문구
STEP_LABEL = {"classify": "① 분야 판정", "check_confidence": "신뢰도 확인", "clarify": "되묻기 준비",
              "gather": "② 규정에서 근거 찾기", "answer": "③ 답변 작성", "verify": "④ 검증",
              "abstain": "담당자 연결 안내", "finalize": "답변 완료"}


def esc(text) -> str:
    return html.escape(str(text))


def rich(text: str) -> str:
    """LLM이 쓴 글을 안전하게 HTML로: 이스케이프 → 인용 [AP-07]을 배지로 → 줄바꿈."""
    out = CITE_RE.sub(lambda m: "".join(f'<span class="fr-cite">{sid}</span>' for sid in ID_RE.findall(m.group(0))),
                      esc(text))
    return out.replace("\n", "<br>")


def kpi(label: str, value: str, sub: str = "") -> str:
    return f'<div class="fr-kpi"><div class="l">{label}</div><div class="v">{value}</div>' + \
        (f'<div class="s">{sub}</div>' if sub else "") + "</div>"


def pill(text: str, kind: str) -> str:
    return f'<span class="fr-pill {kind}">{esc(text)}</span>'


def html_block(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def ro(word: str) -> str:
    """조사 '로/으로': 받침이 없거나 ㄹ 받침이면 '로', 그 밖의 받침이면 '으로'."""
    code = ord(word[-1]) - 0xAC00
    jong = code % 28 if 0 <= code < 11172 else 0
    return f"{word}{'로' if jong in (0, 8) else '으로'}"


def tools_text(tools: list[str]) -> str:
    return ", ".join(TOOL_LABEL.get(t, t) for t in tools)


def human_trace(trace: list[str]) -> str:
    text = " → ".join(t.removeprefix("→ ") for t in trace)
    for code, label in TOOL_LABEL.items():
        text = text.replace(code, label)
    return text


def new_chat() -> None:
    st.session_state["chat"] = []
    st.session_state["focus"] = None


# ---------------------------------------------------------------------------
# 사이드바(기본 접힘): 시연·채점용 설정만 둔다. 직원이 쓰는 버튼은 본문 위쪽 칩에 있다.
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("⚙️ 데모 설정")
    st.caption("시연·채점용입니다. 직원 화면에는 필요 없는 값들이에요.")
    detected = resolve_provider()
    options = ["openai", "gemini", "offline"]
    provider = st.selectbox("답변 LLM", options, index=options.index(detected) if detected in options else 2,
                            help="API 키가 없으면 offline(키워드 분류 + 추출형 답변)으로 동작합니다.")
    if provider != detected and detected == "offline":
        st.warning(".env에 API 키가 없어 이 모드는 실패할 수 있습니다.")
    conf = st.slider("판정 신뢰도 임계값", 0.0, 1.0, Settings.confidence_threshold, 0.05,
                     help="판정 신뢰도가 이 값보다 낮으면 근거를 찾기 전에 되묻습니다. 범위 밖 질문은 되묻지 않고 담당자 연결로 안내합니다.")
    top_k = st.slider("검색 후보 섹션 수 (top_k)", 2, 8, Settings.top_k,
                      help="판정된 분야의 섹션 중 질문과 가장 비슷한 k개를 후보로 뽑습니다. 근거 충분성 판단이 그중 필요한 섹션만 골라 답변에 씁니다.")
    use_scope = st.toggle("범위 확인으로 담당자 연결", True)
    use_term = st.toggle("용어 확인으로 담당자 연결", True)
    use_gate = st.toggle("근거 충분성 판단", True, disabled=provider == "offline")

FEATURES = [("🗂️", "IT·인사·총무·경비 4개 분야"), ("📄", "규정 근거로만 답변"),
            ("❓", "모호하면 되묻기"), ("📞", "규정에 없으면 담당자 연결")]
html_block('<div class="fr-top"><div class="row"><span class="name">새솔컴퍼니 사내 헬프데스크</span>'
           '<span class="demo">가상 회사 규정 기반 과제용 데모</span></div><div class="feats">'
           + "".join(f'<span class="feat"><i>{icon}</i>{text}</span>' for icon, text in FEATURES) + "</div></div>")

tab_ask, tab_eval, tab_map = st.tabs(["문의하기", "평가 결과", "카테고리·근거 매핑"])


def meta_html(out: dict) -> str:
    """답변 카드 맨 위 한 줄: 결과 · 분야 · 신뢰도 · 검증."""
    cat = CATEGORIES[out["category"]]
    status_label, kind = STATUS[out["status"]]
    parts = [pill(status_label, kind), f"<b>{esc(cat['name'])}</b>"]
    parts.append("직접 선택한 분야" if out.get("chosen_category") else f"신뢰도 {out['confidence']:.2f}")
    ver = out.get("verification")
    if out["status"] == "answered" and ver:
        n_ok = sum(c["passed"] for c in ver["checks"])
        parts.append(f'<span class="ok">검증 통과 ✓ {n_ok}/{len(ver["checks"])}</span>' if ver["passed"]
                     else f'<span class="bad">검증 실패 {n_ok}/{len(ver["checks"])}</span>')
    return '<div class="fr-meta">' + ' <span class="dot">·</span> '.join(parts) + "</div>"


def render_answer(i: int, turn: dict) -> None:
    """대화 쪽 답변 카드: 요약 한 줄 + 답변 + 출처. 되묻기면 짧은 안내와 분야 버튼."""
    out = turn["out"]
    if out["status"] == "clarify":
        options = [out["category"]] + ([out["alternative"]] if out.get("alternative") else [])
        html_block(f'<div class="fr-card">{meta_html(out)}<div class="body">질문이 어느 분야를 묻는지 분명하지 않아요. '
                   "어느 쪽으로 답해 드릴까요?</div></div>")
        cols = st.columns(len(options))
        for col, k in zip(cols, options):
            if col.button(f"{ro(CATEGORIES[k]['name'])} 물어보기", key=f"pick_{i}_{k}", type="primary",
                          help=CATEGORIES[k]["focus"], width="stretch"):
                st.session_state["pending"] = {"q": turn["q"], "cat": k}
                st.rerun()
        return
    card = f'<div class="fr-card">{meta_html(out)}<div class="body">{rich(out["answer"])}</div>'
    if out["status"] == "answered" and out.get("citations"):
        card += '<div class="srcs">' + "".join(
            f'<div class="fr-src"><span class="fr-cite">{c["id"]}</span> {esc(c["title"])} '
            f'<span class="m">· {esc(c["doc"])} · {esc(c["version"])}</span></div>'
            for c in out["citations"]) + "</div>"
    html_block(card + "</div>")


def category_bars(out: dict, conf: float) -> str:
    """분야별 점수 막대(높은 순). 판정 분야는 진하게, 세로선은 되묻기 임계값."""
    scores = out.get("category_scores")
    if not scores:  # 점수를 내기 전 기록: 신뢰도 막대 하나만
        scores = {out["category"]: out["confidence"]}
    rows = ""
    for k, v in sorted(scores.items(), key=lambda kv: -kv[1]):
        rows += (f'<div class="fr-catrow{" on" if k == out["category"] else ""}"><span>{esc(CATEGORIES[k]["name"])}</span>'
                 f'<div class="fr-bar"><div class="fill" style="width:{v * 100:.0f}%"></div>'
                 f'<div class="mark" style="left:calc({conf * 100:.0f}% - 1px)" title="임계값 {conf:.2f}"></div></div>'
                 f'<span class="v">{v:.2f}</span></div>')
    if out.get("chosen_category"):
        verdict = pill("사용자가 직접 고른 분야", "muted")
    elif out["category"] == "C0":
        verdict = pill("범위 밖 → 담당자 연결", "warn")
    elif out["confidence"] < conf:
        verdict = pill("되묻기", "info")
    else:
        verdict = pill("통과", "ok")
    return (rows + f'<div class="fr-note">신뢰도 {out["confidence"]:.2f} · 임계값 {conf:.2f}(세로선) → '
            f'<span class="fr-verdict">{verdict}</span></div>')


def step_head(n: str, title: str, sub: str = "") -> str:
    return f'<div class="fr-step">{n} {esc(title)}' + (f' <span class="s">· {esc(sub)}</span>' if sub else "") + "</div>"


def render_process(out: dict, conf: float) -> None:
    """근거 타임라인: ① 분야 판정 → ② 근거 찾기 → ③ 답변 작성 → ④ 검증. 실행되지 않은 단계는 회색 점."""
    cat = CATEGORIES[out["category"]]
    ver = out.get("verification")
    answered = out["status"] == "answered"

    with st.container(key="tl_1"):
        body = step_head("①", "분야 판정", f"{cat['name']}")
        body += category_bars(out, conf)
        if out.get("alternative"):
            body += f'<div class="fr-note">두 번째 후보: {esc(CATEGORIES[out["alternative"]]["name"])}</div>'
        if out.get("evidence_types"):
            body += '<div class="fr-note">필요한 근거 유형 ' + "".join(
                f'<span class="fr-chip">{esc(t)}</span>' for t in out["evidence_types"]) + "</div>"
        if out.get("category_reason"):
            body += f'<div class="fr-note">{esc(out["category_reason"])}</div>'
        html_block(body)

    ran2 = out["status"] != "clarify"
    with st.container(key="tl_2" if ran2 else "tl_2-off"):
        tool = TOOL_LABEL.get(out.get("tool"), "조회 안 함")
        result = {"answered": pill("근거 충분 → 답변", "ok"), "abstained": pill("근거 부족 → 담당자 연결", "warn"),
                  "clarify": pill("되묻기 → 근거 찾기 전 멈춤", "info")}[out["status"]]
        body = step_head("②", "근거 찾기", tool) + f'<div class="fr-note">{result}</div>'
        for g in out.get("gate", []):
            mark = '<span class="o">✓</span>' if g["passed"] else '<span class="x">✕</span>'
            body += (f'<div class="fr-check">{mark} {esc(CHECK_LABEL.get(g["check"], g["check"]))} '
                     f'<span class="d">— {esc(g["detail"])}</span></div>')
        cands = out.get("candidates") or []
        if cands:
            used = {s.id for s in out.get("sections") or []} if answered else set()
            secs = load_sections()
            body += f'<div class="fr-note" style="margin-top:6px">검색 후보 {len(cands)}개 · 질문과 비슷한 순</div>'
            for sid in cands:
                tag = pill("사용", "ok") if sid in used else f'{out["scores"][sid]:.2f}'
                body += (f'<div class="fr-cand{"" if sid in used else " dim"}"><span class="fr-cite">{sid}</span>'
                         f'<span>{esc(secs[sid].title)}</span><span>{tag}</span></div>')
        if out["status"] == "abstained" and out.get("handoff_reason"):
            body += f'<div class="fr-note">담당자 연결 사유: {esc(out["handoff_reason"])}</div>'
        html_block(body)
        if answered:
            for s in out.get("sections") or []:
                with st.expander(f"[{s.id}] {s.title} 원문 보기"):
                    st.caption(f"{s.doc_title} · 출처: {s.source} · {s.version}")
                    st.markdown(s.text)

    n = out.get("attempts", 0)
    with st.container(key="tl_3" if n else "tl_3-off"):
        note = ("근거 섹션만 보고 답하게 하고, 문장마다 출처 섹션을 붙이게 합니다." if n else
                "담당자 연결·되묻기라 답변을 만들지 않았습니다.")
        html_block(step_head("③", "답변 작성", f"{n}회" if n else "건너뜀") + f'<div class="fr-note">{note}</div>')
        for j, d in enumerate(out.get("failed_drafts") or [], 1):
            with st.expander(f"검증에서 걸러진 초안 {j}"):
                html_block(f'<div class="fr-note">{rich(d["answer"])}</div>'
                           + "".join(f'<div class="fr-check"><span class="x">✕</span> {esc(p)}</div>' for p in d["problems"]))

    with st.container(key="tl_4" if ver and answered else "tl_4-off"):
        if ver and answered:
            n_ok = sum(c["passed"] for c in ver["checks"])
            body = step_head("④", "검증", f"{n_ok}/{len(ver['checks'])} 통과")
            for c in ver["checks"]:
                mark = '<span class="o">✓</span>' if c["passed"] else '<span class="x">✕</span>'
                body += f'<div class="fr-check">{mark} {esc(c["name"])} <span class="d">— {esc(c["detail"])}</span></div>'
        else:
            body = step_head("④", "검증", "건너뜀") + '<div class="fr-note">답변을 만들지 않았으므로 검증하지 않습니다.</div>'
        html_block(body)
    html_block(f'<div class="fr-trace">{esc(human_trace(out["trace"]))}</div>')


def render_error(i: int, turn: dict) -> None:
    """오류는 원문 대신 안내 문구와 다시 시도 버튼으로. 원문은 접어 둔다."""
    err = turn["error"]
    low = err.lower()
    if any(k in low for k in ("api_key", "api key", "credential", "401", "unauthorized", "permission_denied")):
        st.warning("이 모델의 API 키가 없거나 올바르지 않아요. 데모 설정에서 다른 모델을 골라 주세요.", icon="🔑")
    elif "한도" in err or any(k in low for k in ("quota", "credits", "429")):
        st.warning("쓸 수 있는 호출 한도를 다 썼어요. 나중에 다시 시도하거나 데모 설정에서 다른 모델을 골라 주세요.", icon="⏳")
    else:
        st.warning("일시적인 오류로 답변을 만들지 못했어요. 잠시 후 다시 시도해 주세요.", icon="⚠️")
    c1, c2 = st.columns([1, 4])
    if c1.button("다시 시도", key=f"retry_{i}"):
        st.session_state["chat"].pop(i)
        st.session_state["pending"] = {"q": turn["q"], "cat": turn.get("cat")}
        st.rerun()
    with c2.expander("오류 내용 보기"):
        st.code(err, language=None)


def render_turn(i: int, turn: dict) -> None:
    if turn.get("error"):
        render_error(i, turn)
        return
    render_answer(i, turn)
    if st.session_state.get("focus") == i:
        st.caption("근거 타임라인에 표시 중 →")
    elif st.button("이 답의 근거 보기 →", key=f"focus_{i}", type="tertiary"):
        st.session_state["focus"] = i
        st.rerun()


def user_html(q: str, cat: str | None) -> str:
    re_ask = f'<span class="re">→ {esc(CATEGORIES[cat]["name"])} 분야로 다시 문의</span>' if cat else ""
    return f'<div class="fr-user">{esc(q)}{re_ask}</div>'


def render_panel(chat: list, busy: bool) -> None:
    """오른쪽 근거 타임라인: 고른 답(기본은 가장 최근 답)의 판정·근거·검증 과정."""
    html_block('<div class="fr-panel-h">근거 타임라인</div>')
    if busy:
        st.caption("새 문의를 처리하고 있어요. 끝나면 여기에 판정·근거·검증 과정이 보여요.")
        return
    i = st.session_state.get("focus")
    if i is None or i >= len(chat):
        i = len(chat) - 1
    if i < 0:
        st.caption("문의를 남기면 여기에 ① 분야 판정 점수 → ② 찾은 근거 → ③ 답변 → ④ 검증 결과가 순서대로 보여요.")
        return
    turn = chat[i]
    html_block(f'<div class="fr-panel-q">Q. {esc(turn["q"])}</div>')
    if turn.get("error"):
        st.caption("이 문의는 오류로 답변을 만들지 못했어요.")
        return
    render_process(turn["out"], turn["conf"])


def run_with_progress(agent, question: str, cat: str | None) -> dict:
    """단계가 끝날 때마다 ✓를 하나씩 켜는 진행 표시와 함께 실행한다."""
    out = None
    with st.status("답변을 준비하고 있어요…", expanded=True) as status:
        for node, state in agent.stream(question, chosen_category=cat):
            label = STEP_LABEL.get(node, node)
            if node == "classify":
                label += f" — {CATEGORIES[state['category']]['name']}" + (
                    "(직접 선택)" if cat else f" (신뢰도 {state['confidence']:.2f})")
            elif node == "gather":
                label += f" — {len(state.get('sections') or [])}개 섹션" if state.get("sufficient") else " — 근거 부족"
            elif node == "verify":
                label += " — 통과" if state["verification"]["passed"] else " — 다시 작성"
            st.write(f"✓ {label}")
            out = state
        done = {"answered": "답변을 마쳤어요", "abstained": "담당 부서로 안내해 드려요", "clarify": "분야를 골라 주세요"}
        status.update(label=done.get(out.get("status"), "완료"), state="complete", expanded=False)
    return dict(out)


# ---------------------------------------------------------------------------
with tab_ask:
    chat = st.session_state.setdefault("chat", [])
    html_block('<div class="fr-chips-h">예시 질문 — 눌러서 물어보기</div>')
    with st.container(key="chips", horizontal=True):
        for label, ex in EXAMPLES:
            if st.button(label, help=ex, key=f"ex_{label}"):
                st.session_state["pending"] = {"q": ex, "cat": None}
        with st.container(key="newchat", width="content"):
            st.button("새 대화", icon=":material/refresh:", on_click=new_chat)
    chat_col, side_col = st.columns([7, 5], gap="large")
with chat_col:
    if not chat:
        with st.chat_message("assistant", avatar=AVATAR["assistant"]):
            html_block('<div class="fr-card">안녕하세요, 새솔컴퍼니 사내 헬프데스크입니다. IT·인사·총무·경비 관련 문의를 남겨 주세요. '
                       "위의 예시 질문을 눌러 봐도 됩니다.</div>")
    for i, turn in enumerate(chat):
        with st.chat_message("user", avatar=AVATAR["user"]):
            html_block(user_html(turn["q"], turn.get("cat")))
        with st.chat_message("assistant", avatar=AVATAR["assistant"]):
            render_turn(i, turn)

    live = st.container()  # 진행 중인 질문은 입력창 위 이 자리에 그린다
    typed = st.chat_input("문의 내용을 입력하세요 (예: 재택근무는 주 며칠까지 돼요?)")
    pending = st.session_state.pop("pending", None)
    if typed and typed.strip():
        pending = {"q": typed.strip(), "cat": None}
    with side_col.container(key="evidence"):
        render_panel(chat, busy=bool(pending))
    if pending:
        with live.chat_message("user", avatar=AVATAR["user"]):
            html_block(user_html(pending["q"], pending["cat"]))
        turn = {"q": pending["q"], "cat": pending["cat"], "conf": conf}
        with live.chat_message("assistant", avatar=AVATAR["assistant"]):
            try:
                agent = get_agent(provider, (top_k, Settings.min_similarity, conf, use_scope, use_term, use_gate))
                out = run_with_progress(agent, pending["q"], pending["cat"])
                out["chosen_category"] = pending["cat"]
                turn["out"] = out
            except Exception as e:  # 키 오류·쿼터 초과·일시 장애
                turn["error"] = str(e)[:600]
        chat.append(turn)
        st.session_state["focus"] = len(chat) - 1  # 새 답이 오면 타임라인도 그 답으로
        st.rerun()


# ---------------------------------------------------------------------------
with tab_eval:
    hist = RESULTS / "history.md"
    if hist.exists():
        runs = sorted(RESULTS.glob("run_*.json"), reverse=True)
        pick = st.selectbox("실행 결과 보기", runs, format_func=lambda p: p.stem)
        if pick:
            data = json.loads(pick.read_text(encoding="utf-8"))
            sm = data["summary"]
            fmt = lambda v: "-" if v is None else f"{v:.0%}"  # noqa: E731
            html_block('<div class="fr-h">과제 지표</div><div class="fr-kpis">'
                       + kpi("도구 호출 적절성", fmt(sm["tool_score"]))
                       + kpi("답변 적절성", fmt(sm["answer_score"]))
                       + kpi("모델", esc(f"{sm['provider']}/{sm['model']}"), esc(sm.get("data", "")))
                       + kpi("채점기", esc(sm["grader"]))
                       + '</div><div class="fr-h">PRD 지표</div><div class="fr-kpis" style="grid-template-columns:repeat(5,minmax(0,1fr))">'
                       + kpi("분류 정확도", fmt(sm["router_accuracy"]))
                       + kpi("근거 적합성", fmt(sm.get("retrieval_relevance")))
                       + kpi("답변 정확성", fmt(sm.get("answer_accuracy")))
                       + kpi("근거 없는 정보 생성", fmt(sm.get("unsupported_rate")))
                       + kpi("보류(담당자 연결) 정확도", fmt(sm.get("abstain_accuracy")))
                       + "</div>")
            df = pd.DataFrame([{
                "ID": r["id"], "질문": r["question"], "판정": f"{r['category']} {r.get('confidence') or 0:.2f}",
                "기대 도구": ", ".join(r["expected_tools"]), "실제 도구": ", ".join(r["tools_called"]),
                "도구": "○" if r["tool_score"] else "×", "답변": "○" if r["answer_score"] else "×",
                "원인": " / ".join(r["diagnosis"]),
            } for r in data["records"]])
            st.dataframe(df, hide_index=True, width="stretch")
        with st.expander("개선 시도별 기록 전체"):
            st.markdown(hist.read_text(encoding="utf-8"))
    else:
        st.info("아직 평가 기록이 없습니다. `python evaluate.py --label baseline`을 실행하세요.")

# ---------------------------------------------------------------------------
with tab_map:
    secs = load_sections()
    rows = []
    for key, c in CATEGORIES.items():
        rows.append({
            "카테고리": f"{key} · {c['name']} ({c['en']})", "도구": TOOL_LABEL.get(c["tool"] or "abstain"),
            "근거 섹션": ", ".join(f"{s} {secs[s].title}" for s in c["sections"]) or "(없음 → 담당자 연결)",
            "다루지 않는 범위(→ 담당자 연결)": c["out_of_scope"], "넘길 곳": c["handoff_to"],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown("##### 섹션별 출처")
    st.dataframe(pd.DataFrame([{"섹션": s.id, "제목": s.title, "문서": s.doc_title, "출처": s.source, "버전": s.version}
                               for s in secs.values()]), hide_index=True, width="stretch")
