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

EXAMPLES = [
    "비밀번호를 5번 틀려서 잠겼어요. 어떻게 풀어요?",
    "입사 2년차인데 연차가 며칠이에요?",
    "회의실은 몇 주 전부터 예약할 수 있어요?",
    "대리인데 법인카드 한도가 얼마예요?",
    "야근하면 뭐 받을 수 있어요?",
    "육아휴직 급여는 얼마나 나와요?",
    "오늘 점심 뭐 먹을까요?",
]
# 결과별 표시 이름과 색 이름(CSS 클래스)
STATUS = {"answered": ("답변", "ok"), "abstained": ("담당자 연결", "warn"), "clarify": ("되묻기", "info")}

st.set_page_config(page_title="사내 헬프데스크", page_icon="🏢", layout="wide")

st.markdown("""
<style>
:root {
  --fr-accent: #2f6fed; --fr-ok: #15803d; --fr-warn: #b45309; --fr-info: #1d4ed8; --fr-bad: #b91c1c;
  --fr-line: rgba(127,127,127,.22); --fr-soft: rgba(127,127,127,.06); --fr-muted: rgba(127,127,127,.95);
}
.block-container { padding-top: 2rem; max-width: 1200px; }
h1 { font-size: 1.7rem !important; }
.fr-sub { font-size: 13.5px; color: var(--fr-muted); margin: -6px 0 14px; }
.fr-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 4px 0 14px; }
.fr-kpi { border: 1px solid var(--fr-line); border-radius: 10px; padding: 10px 12px; background: var(--fr-soft); min-width: 0; }
.fr-kpi .l { font-size: 12px; color: var(--fr-muted); margin-bottom: 4px; }
.fr-kpi .v { font-size: 15px; font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
.fr-kpi .s { font-size: 12px; color: var(--fr-muted); margin-top: 3px; overflow-wrap: anywhere; }
.fr-pill { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 12.5px; font-weight: 600; }
.fr-pill.ok { background: rgba(21,128,61,.13); color: var(--fr-ok); }
.fr-pill.warn { background: rgba(180,83,9,.13); color: var(--fr-warn); }
.fr-pill.info { background: rgba(29,78,216,.12); color: var(--fr-info); }
.fr-pill.bad { background: rgba(185,28,28,.12); color: var(--fr-bad); }
.fr-pill.muted { background: var(--fr-soft); color: var(--fr-muted); border: 1px solid var(--fr-line); }
.fr-answer { border: 1px solid var(--fr-line); border-left: 4px solid var(--fr-c); border-radius: 10px;
  padding: 12px 16px; background: var(--fr-soft); font-size: 14.5px; line-height: 1.75; margin-bottom: 10px; }
.fr-answer.ok { --fr-c: var(--fr-ok); } .fr-answer.warn { --fr-c: var(--fr-warn); } .fr-answer.info { --fr-c: var(--fr-info); }
.fr-cite { font-family: ui-monospace, Consolas, monospace; font-size: 11.5px; padding: 1px 6px; margin: 0 1px;
  border-radius: 6px; background: rgba(47,111,237,.12); color: var(--fr-accent); white-space: nowrap; }
.fr-h { font-size: 13px; font-weight: 600; margin: 4px 0 6px; }
.fr-src { font-size: 13px; padding: 6px 0; border-top: 1px dashed var(--fr-line); }
.fr-src .m { color: var(--fr-muted); font-size: 12px; }
.fr-step { font-size: 14px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.fr-num { display: inline-flex; width: 21px; height: 21px; border-radius: 50%; background: var(--fr-accent); color: #fff;
  font-size: 12px; align-items: center; justify-content: center; flex: none; }
.fr-note { font-size: 12.5px; color: var(--fr-muted); line-height: 1.6; margin: 4px 0; }
.fr-bar { position: relative; height: 8px; border-radius: 4px; background: var(--fr-line); margin: 8px 0 4px; }
.fr-bar .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 4px; background: var(--fr-accent); }
.fr-bar .mark { position: absolute; top: -4px; width: 2px; height: 16px; background: currentColor; opacity: .75; }
.fr-scale { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--fr-muted); }
.fr-chip { display: inline-block; font-size: 11.5px; padding: 1px 7px; border-radius: 6px; margin: 2px 3px 0 0;
  border: 1px solid var(--fr-line); }
.fr-cand { display: grid; grid-template-columns: 62px 1fr 92px 46px; gap: 8px; align-items: center; font-size: 12.5px;
  padding: 4px 0; border-top: 1px dashed var(--fr-line); }
.fr-cand.dim { opacity: .55; }
.fr-mini { height: 6px; border-radius: 3px; background: var(--fr-line); position: relative; }
.fr-mini .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--fr-accent); }
.fr-check { font-size: 13px; padding: 4px 0; border-top: 1px dashed var(--fr-line); line-height: 1.5; }
.fr-check b { font-weight: 600; } .fr-check .x { color: var(--fr-bad); font-weight: 700; } .fr-check .o { color: var(--fr-ok); font-weight: 700; }
.fr-trace { font-size: 12px; color: var(--fr-muted); margin-top: 6px; }
.fr-meta { font-size: 13px; margin: 2px 0 8px; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.fr-meta .dot { color: var(--fr-muted); }
.fr-meta .ok { color: var(--fr-ok); font-weight: 600; } .fr-meta .bad { color: var(--fr-bad); font-weight: 600; }
.fr-catrow { display: grid; grid-template-columns: 74px 1fr 38px; gap: 8px; align-items: center; font-size: 12.5px;
  padding: 3px 0; color: var(--fr-muted); }
.fr-catrow.on { color: inherit; font-weight: 600; }
.fr-catrow .fr-bar { margin: 0; height: 7px; }
.fr-catrow .fr-bar .fill { background: rgba(127,127,127,.45); }
.fr-catrow.on .fr-bar .fill { background: var(--fr-accent); }
.fr-catrow .v { text-align: right; font-variant-numeric: tabular-nums; }
.fr-panel-h { font-size: 15px; font-weight: 700; margin: 0 0 2px; }
.fr-panel-q { font-size: 12.5px; color: var(--fr-muted); margin-bottom: 10px; overflow-wrap: anywhere; }
.st-key-evidence .fr-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (min-width: 992px) {
  /* 대화가 길어져도 근거 패널이 화면에 붙어 있도록: 패널의 부모들을 열 높이만큼 늘린 뒤 sticky */
  [data-testid="stColumn"]:has(.st-key-evidence) > [data-testid="stVerticalBlock"] { height: 100%; }
  [data-testid="stLayoutWrapper"]:has(> .st-key-evidence) { flex: 1 1 auto; }
  .st-key-evidence { position: sticky; top: 4rem; max-height: calc(100vh - 5rem); overflow-y: auto; padding-right: 4px; }
}
@media (max-width: 760px) { .fr-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } .fr-cand { grid-template-columns: 58px 1fr 46px; } .fr-cand .mini { display: none; } }
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


# ---------------------------------------------------------------------------
# 사이드바: 위에는 사용자가 쓰는 것, 아래 접힌 메뉴에는 시연·채점용 설정
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("예시 질문")
    for ex in EXAMPLES:
        if st.button(ex, width="stretch"):
            st.session_state["pending"] = {"q": ex, "cat": None}
    if st.button("🗑️ 새 대화 시작", width="stretch"):
        st.session_state["chat"] = []
        st.session_state["focus"] = None
    st.divider()
    with st.expander("⚙️ 데모 설정 (시연·채점용)"):
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

st.title("🏢 새솔컴퍼니 사내 헬프데스크")
html_block('<div class="fr-sub">직원 문의를 IT지원·인사·총무·경비정산으로 분류하고 그 분야의 사내 규정에서만 답합니다. '
           '분야가 모호하면 되묻고, 규정에 없으면 지어내지 않고 담당 부서로 연결합니다. (가상 회사 규정 기반 과제용 데모)</div>')

tab_ask, tab_eval, tab_map = st.tabs(["문의하기", "평가 결과", "카테고리·근거 매핑"])


def render_meta(out: dict, conf: float) -> None:
    """답변 위 한 줄 요약: 결과 · 분야 · 신뢰도 · 검증."""
    cat = CATEGORIES[out["category"]]
    status_label, kind = STATUS[out["status"]]
    parts = [pill(status_label, kind), f"<b>{esc(cat['name'])}</b>"]
    parts.append("직접 선택한 분야" if out.get("chosen_category") else f"신뢰도 {out['confidence']:.2f}")
    ver = out.get("verification")
    if out["status"] == "answered" and ver:
        n_ok = sum(c["passed"] for c in ver["checks"])
        parts.append(f'<span class="ok">검증 통과 ✓</span> ({n_ok}/{len(ver["checks"])})' if ver["passed"]
                     else f'<span class="bad">검증 실패</span> ({n_ok}/{len(ver["checks"])})')
    html_block('<div class="fr-meta">' + ' <span class="dot">·</span> '.join(parts) + "</div>")


def render_answer(i: int, turn: dict) -> None:
    """답변 탭: 한 줄 요약 + 답변 + 출처. 되묻기면 짧은 안내와 분야 버튼만 보여 준다."""
    out = turn["out"]
    render_meta(out, turn["conf"])
    if out["status"] == "clarify":
        options = [out["category"]] + ([out["alternative"]] if out.get("alternative") else [])
        html_block(f'<div class="fr-answer info">질문이 어느 분야를 묻는지 분명하지 않아요(신뢰도 {out["confidence"]:.2f}). '
                   "어느 쪽으로 답해 드릴까요?</div>")
        cols = st.columns(len(options))
        for col, k in zip(cols, options):
            if col.button(f"{ro(CATEGORIES[k]['name'])} 물어보기", key=f"pick_{i}_{k}", type="primary",
                          help=CATEGORIES[k]["focus"]):
                st.session_state["pending"] = {"q": turn["q"], "cat": k}
                st.rerun()
        return
    _, kind = STATUS[out["status"]]
    html_block(f'<div class="fr-answer {kind}">{rich(out["answer"])}</div>')
    if out["status"] == "answered" and out.get("citations"):
        html_block('<div class="fr-h">출처</div>' + "".join(
            f'<div class="fr-src"><span class="fr-cite">{c["id"]}</span> <b>{esc(c["title"])}</b> '
            f'<span class="m">· {esc(c["doc"])} · {esc(c["source"])} · {esc(c["version"])}</span></div>'
            for c in out["citations"]))


def category_bars(out: dict, conf: float) -> str:
    """분야별 점수 막대(높은 순). 판정 분야는 강조, 세로선은 되묻기 임계값."""
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
        verdict = "사용자가 직접 고른 분야"
    elif out["category"] == "C0":
        verdict = "범위 밖은 되묻지 않고 담당자 연결"
    else:
        verdict = "되묻기" if out["confidence"] < conf else "통과"
    return (rows + f'<div class="fr-note">신뢰도 {out["confidence"]:.2f} · 임계값 {conf:.2f}(세로선) → {verdict}</div>')


def render_cards(out: dict, conf: float) -> None:
    """처리 과정 탭 맨 위의 요약 카드 4개."""
    cat = CATEGORIES[out["category"]]
    status_label, kind = STATUS[out["status"]]
    ver = out.get("verification")
    low = out["category"] != "C0" and out["confidence"] < conf
    if not ver or out["status"] != "answered":
        ver_value, ver_sub = pill("해당 없음", "muted"), "담당자 연결·되묻기는 검증하지 않음"
    else:
        n_ok = sum(c["passed"] for c in ver["checks"])
        ver_value = pill("통과" if ver["passed"] else "실패", "ok" if ver["passed"] else "bad")
        ver_sub = f"검사 {len(ver['checks'])}개 중 {n_ok}개 통과 · 답변 {out.get('attempts', 0)}회 생성"
    if out.get("chosen_category"):
        conf_sub = "사용자가 직접 선택"
    elif out["category"] == "C0":
        conf_sub = f"임계값 {conf:.2f} → 범위 밖은 되묻지 않음"
    else:
        conf_sub = f"임계값 {conf:.2f} → " + ("되묻기" if low else "통과")
    html_block('<div class="fr-kpis">'
               + kpi("판정 카테고리", f"{out['category']} · {esc(cat['name'])}", esc(cat["en"]))
               + kpi("판정 신뢰도", f"{out['confidence']:.2f}", conf_sub)
               + kpi("결과", pill(status_label, kind), esc(tools_text(out["tools_called"])))
               + kpi("검증", ver_value, ver_sub)
               + "</div>")


def render_process(out: dict, conf: float) -> None:
    """처리 과정 탭: 요약 카드 + ①~④ 단계별 상세."""
    render_cards(out, conf)
    cat = CATEGORIES[out["category"]]
    ver = out.get("verification")
    s1 = s2 = st.container()  # 패널 폭이 좁아 단계를 한 줄로 쌓는다
    with s1:
        with st.container(border=True):
            body = f'<div class="fr-step"><span class="fr-num">1</span>분야 판정 · {out["category"]} {esc(cat["name"])}</div>'
            body += category_bars(out, conf)
            if out.get("alternative"):
                alt = out["alternative"]
                body += f'<div class="fr-note">두 번째 후보: {esc(CATEGORIES[alt]["name"])}</div>'
            if out.get("evidence_types"):
                body += '<div class="fr-note">필요한 근거 유형 ' + "".join(
                    f'<span class="fr-chip">{esc(t)}</span>' for t in out["evidence_types"]) + "</div>"
            if out.get("category_reason"):
                body += f'<div class="fr-note">{esc(out["category_reason"])}</div>'
            html_block(body)

        with st.container(border=True):
            tool = TOOL_LABEL.get(out.get("tool"), "조회 안 함")
            body = f'<div class="fr-step"><span class="fr-num">2</span>근거 찾기 · {esc(tool)}</div>'
            if out["status"] == "clarify":
                body += '<div class="fr-note">신뢰도가 임계값보다 낮아 근거를 찾기 전에 되물었습니다.</div>'
            for g in out.get("gate", []):
                mark = '<span class="o">✓</span>' if g["passed"] else '<span class="x">✕</span>'
                body += f'<div class="fr-check">{mark} <b>{esc(CHECK_LABEL.get(g["check"], g["check"]))}</b> — {esc(g["detail"])}</div>'
            cands = out.get("candidates") or []
            if cands:
                used = {s.id for s in out.get("sections") or []} if out["status"] == "answered" else set()
                top = max(out["scores"].values(), default=1) or 1
                secs = load_sections()
                rows = []
                for sid in cands:
                    tag = pill("사용", "ok") if sid in used else f'{out["scores"][sid]:.2f}'
                    rows.append(f'<div class="fr-cand{"" if sid in used else " dim"}"><span class="fr-cite">{sid}</span>'
                                f'<span>{esc(secs[sid].title)}</span>'
                                f'<div class="fr-mini mini"><div class="fill" style="width:{out["scores"][sid] / top * 100:.0f}%"></div></div>'
                                f'<span>{tag}</span></div>')
                body += f'<div class="fr-note" style="margin-top:8px">검색 후보 {len(cands)}개 · 질문과 비슷한 순</div>' + "".join(rows)
            if out["status"] == "abstained":
                body += f'<div class="fr-note">담당자 연결 사유: {esc(out.get("handoff_reason"))}</div>'
            html_block(body)
            if out["status"] == "answered":
                for s in out.get("sections") or []:
                    with st.expander(f"[{s.id}] {s.title} 원문 보기"):
                        st.caption(f"{s.doc_title} · 출처: {s.source} · {s.version}")
                        st.markdown(s.text)

    with s2:
        with st.container(border=True):
            n = out.get("attempts", 0)
            note = ("근거 섹션만 보고 답하게 하고, 문장마다 출처 섹션을 붙이게 합니다." if n else
                    "담당자 연결·되묻기라 답변을 만들지 않았습니다.")
            html_block(f'<div class="fr-step"><span class="fr-num">3</span>답변 작성 · {n}회</div><div class="fr-note">{note}</div>')
            for i, d in enumerate(out.get("failed_drafts") or [], 1):
                with st.expander(f"검증에서 걸러진 초안 {i}"):
                    html_block(f'<div class="fr-note">{rich(d["answer"])}</div>'
                               + "".join(f'<div class="fr-check"><span class="x">✕</span> {esc(p)}</div>' for p in d["problems"]))
        with st.container(border=True):
            body = '<div class="fr-step"><span class="fr-num">4</span>검증 · 기계적 검사</div>'
            if ver and out["status"] == "answered":
                for c in ver["checks"]:
                    mark = '<span class="o">✓</span>' if c["passed"] else '<span class="x">✕</span>'
                    body += f'<div class="fr-check">{mark} <b>{esc(c["name"])}</b> — {esc(c["detail"])}</div>'
            else:
                body += '<div class="fr-note">담당자 연결·되묻기는 답변을 만들지 않으므로 검증하지 않습니다.</div>'
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
        st.caption("🔎 근거 패널에 표시 중")
    elif st.button("🔎 이 답의 근거 보기", key=f"focus_{i}", type="tertiary"):
        st.session_state["focus"] = i
        st.rerun()


def render_panel(chat: list, busy: bool) -> None:
    """오른쪽 근거 패널: 고른 답(기본은 가장 최근 답)의 판정·근거·검증 과정."""
    html_block('<div class="fr-panel-h">🔎 이번 답의 근거</div>')
    if busy:
        st.caption("새 문의를 처리하고 있어요. 끝나면 여기에 판정·근거·검증 과정이 보여요.")
        return
    i = st.session_state.get("focus")
    if i is None or i >= len(chat):
        i = len(chat) - 1
    if i < 0:
        st.caption("문의를 남기면 여기에 분야 판정 점수, 찾은 근거, 검증 결과가 보여요.")
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
    chat_col, side_col = st.columns([7, 5], gap="large")
with chat_col:
    if not chat:
        with st.chat_message("assistant", avatar="🏢"):
            st.markdown("안녕하세요, 새솔컴퍼니 사내 헬프데스크입니다. IT·인사·총무·경비 관련 문의를 남겨 주세요. "
                        "왼쪽의 예시 질문을 눌러 봐도 됩니다.")
    for i, turn in enumerate(chat):
        with st.chat_message("user", avatar="🧑‍💼"):
            note = ""
            if turn.get("cat"):
                note = f"  \n:blue[→ {CATEGORIES[turn['cat']]['name']} 분야로 다시 문의]"
            st.markdown(turn["q"] + note)
        with st.chat_message("assistant", avatar="🏢"):
            render_turn(i, turn)

    live = st.container()  # 진행 중인 질문은 입력창 위 이 자리에 그린다
    typed = st.chat_input("문의 내용을 입력하세요 (예: 재택근무는 주 며칠까지 돼요?)")
    pending = st.session_state.pop("pending", None)
    if typed and typed.strip():
        pending = {"q": typed.strip(), "cat": None}
    with side_col.container(key="evidence"):
        render_panel(chat, busy=bool(pending))
    if pending:
        with live.chat_message("user", avatar="🧑‍💼"):
            st.markdown(pending["q"])
        turn = {"q": pending["q"], "cat": pending["cat"], "conf": conf}
        with live.chat_message("assistant", avatar="🏢"):
            try:
                agent = get_agent(provider, (top_k, Settings.min_similarity, conf, use_scope, use_term, use_gate))
                out = run_with_progress(agent, pending["q"], pending["cat"])
                out["chosen_category"] = pending["cat"]
                turn["out"] = out
            except Exception as e:  # 키 오류·쿼터 초과·일시 장애
                turn["error"] = str(e)[:600]
        chat.append(turn)
        st.session_state["focus"] = len(chat) - 1  # 새 답이 오면 패널도 그 답으로
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
