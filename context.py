"""사내 문의 응대: 문서 쪼개기 · 카테고리별 근거 조립 (파이프라인 ②).

보류(abstain) 판단은 이 단계에서 한다. ① 판정은 카테고리와 신뢰도만 내고,
고른 카테고리의 근거로 답할 수 있는지는 여기서 따로 판단한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DOCS_DIR = Path(__file__).parent / "docs"
ABSTAIN = "abstain"   # 근거 부족·범위 밖 → 답변 보류
CLARIFY = "clarify"   # 판정 신뢰도 낮음 → 질문 되묻기

# ---------------------------------------------------------------------------
# 카테고리 ↔ 근거 문서 매핑표. REPORT.md의 매핑표와 같은 내용이다.
# ---------------------------------------------------------------------------
CATEGORIES: dict[str, dict] = {
    "C1": {
        "focus": "계정·VPN·장비·소프트웨어·보안 같은 IT 지원",
        "name": "IT지원",
        "en": "IT Support",
        "tool": "lookup_it",
        "description": "헬프데스크 이용, 계정·비밀번호 규칙과 초기화, VPN·재택 접속, 노트북·모니터 지급과 교체, "
        "소프트웨어 설치 승인, 보안사고(피싱·악성코드·개인정보 유출) 신고, 이메일 용량·첨부, 보안 출력",
        "sections": [f"IT-{i:02d}" for i in range(1, 9)] + ["HR-07"],
        "out_of_scope": "개인 소유 기기 수리, 보안 통제를 우회하는 방법, 다른 직원의 계정 정보",
        "scope_patterns": [r"우회|뚫|해킹|크랙", r"(다른|타)\s*(직원|사람|팀원)\S*\s*(비밀번호|계정|메일)", r"개인\s*(폰|휴대폰|노트북|PC)\s*(수리|고쳐)"],
        "handoff_to": "IT헬프데스크(내선 1100, 사내 포털 'IT 요청')",
    },
    "C2": {
        "focus": "근무시간·휴가·재택·증명서 같은 인사·복무",
        "name": "인사",
        "en": "HR",
        "tool": "lookup_hr",
        "description": "근무시간과 시차출퇴근, 연장·야간·휴일근로의 사전 승인과 가산 수당·대체휴무(야근 수당 인정 여부 포함), 연차휴가 발생·신청·사용·촉진, "
        "경조휴가와 경조금, 병가, 재택근무 신청, 재직·경력증명서 발급",
        "sections": [f"HR-{i:02d}" for i in range(1, 9)],
        "out_of_scope": "개인별 급여·연봉 금액, 개별 인사평가 결과, 징계 사안, 노무 분쟁 법률 자문, 배우자 출산휴가·육아휴직의 세부 일수와 급여",
        "scope_patterns": [r"(내|제|저의|팀장님?|동료)\S*\s*(연봉|월급|급여)\s*(이|은|가)?\s*(얼마|몇)", r"인사\s*평가\s*결과|고과\s*결과",
                           r"징계|해고|부당", r"육아\s*휴직|배우자\s*출산"],
        "handoff_to": "인사팀(내선 1200, 인사시스템 문의하기)",
    },
    "C3": {
        "focus": "사원증·회의실·비품·택배·주차·명함·시설·법인차량 같은 총무",
        "name": "총무",
        "en": "General Affairs",
        "tool": "lookup_ga",
        "description": "사원증 발급·분실·재발급과 임시 출입증, 회의실 예약, 소모품·비품(의자·책상 등) 신청과 개인 구매 가능 여부, 우편·택배 발송, "
        "주차 등록과 방문객 주차, 명함 신청, 시설 고장 신고, 법인차량 예약과 이용",
        "sections": [f"GA-{i:02d}" for i in range(1, 9)],
        "out_of_scope": "개인 물품 보관·배송, 사옥 외부 시설, 임대차 계약 내용",
        "scope_patterns": [r"개인\s*택배\S*\s*(보관|맡)", r"임대차|임대료|관리비"],
        "handoff_to": "총무팀(내선 1300, 1층 총무 창구)",
    },
    "C4": {
        "focus": "법인카드·식대·출장비·택시비·접대비 같은 경비정산",
        "name": "경비정산",
        "en": "Expense",
        "tool": "lookup_expense",
        "description": "경비 정산 원칙과 제출 기한, 인정 증빙(세금계산서·카드전표·현금영수증·간이영수증), 직급별 법인카드 한도와 금지 업종, "
        "야근 식대·회식비, 국내·해외 출장비(일비·숙박비 상한·교통), 택시비, 거래처 접대비, 개인카드 정산과 반려 사유",
        "sections": [f"EX-{i:02d}" for i in range(1, 10)] + ["GA-08"],
        "out_of_scope": "개인 연말정산·세금 신고, 급여 계산, 회계 처리 방법",
        "scope_patterns": [r"연말\s*정산|종합\s*소득세|세금\s*신고|부가세\s*신고", r"분개|회계\s*처리|계정\s*과목"],
        "handoff_to": "재무팀 경비 담당(내선 1400, 경비시스템 문의하기)",
    },
    "C0": {
        "focus": "사내 문의가 아닌 질문",
        "name": "범위 밖",
        "en": "Out of Scope",
        "tool": None,
        "description": "위 네 분야 어디에도 속하지 않는 질문: 회사 업무와 무관한 개인 질문, 주식·투자, 다른 회사 제도, "
        "다른 직원의 개인정보 요청, 사내 규정이 아닌 일반 상식·잡담",
        "sections": [],
        "out_of_scope": "사내 규정 전체",
        "scope_patterns": [],
        "handoff_to": "해당 문의는 사내 헬프데스크가 답할 수 없습니다. 업무 관련이면 소속 팀장에게 문의해 주세요",
    },
}
TOOL_TO_CATEGORY = {c["tool"]: k for k, c in CATEGORIES.items() if c["tool"]}

# 어느 분야든 사내 헬프데스크가 다루지 않는 요청 (각 문서 '범위' 문단의 공통분모)
GLOBAL_SCOPE_PATTERNS = [
    r"(다른|타)\s*(직원|사람|팀원|팀장)\S*\s*(연락처|주소|전화번호|연봉|급여|평가)",
    r"(주식|코인|비트코인)\S*\s*(사도|살까|팔까|오를까|추천)",
    r"(다른|타)\s*회사(는|에서는)",
]

# 사내 제도 용어 사전. 질문이나 답변에 나온 용어가 근거에 없으면 '근거 밖'으로 본다.
TERMS = [
    # 근거 문서에 있는 용어
    "SSO", "VPN", "OTP", "2단계 인증", "관리자 권한", "표준 소프트웨어", "보안 출력", "대용량 파일 전송", "피싱",
    "시차출퇴근", "코어타임", "연장근로", "야간근로", "휴일근로", "대체휴무", "연차", "반차", "연차 사용 촉진",
    "반반차", "경조휴가", "경조금", "병가", "진단서", "재택근무", "수습", "재직증명서", "경력증명서", "원천징수영수증",
    "사원증", "임시 출입증", "회의실", "대회의실", "비품", "명함", "법인차량", "주차",
    "법인카드", "세금계산서", "현금영수증", "간이영수증", "매출전표", "일비", "숙박비", "접대비", "회식비", "지연 사유서",
    # 근거 문서에 없는 용어(답변에 나오면 지어낸 것으로 본다)
    "안식휴가", "리프레시 휴가", "보상휴가", "선택적 근로시간제", "재량근로", "탄력적 근로시간제",
    "육아휴직", "배우자 출산휴가", "출산전후휴가", "가족돌봄휴가", "생리휴가", "포괄임금", "성과급", "인센티브",
    "복지포인트", "사내대출", "식권", "법인 택시카드", "마일리지",
    "연말정산", "종합소득세", "부가가치세", "MDM", "NAC", "DRM", "BYOD", "USB 허용",
]


@dataclass
class Section:
    id: str
    title: str
    text: str      # 출처 줄을 뺀 본문
    doc: str       # 파일명
    doc_title: str
    source: str    # 섹션의 출처(기준서 문단·법령 조문·교재)
    version: str

    @property
    def body(self) -> str:
        return f"[{self.id}] {self.title}\n{self.text}"

    def citation(self) -> dict:
        return {"id": self.id, "title": self.title, "doc": self.doc_title, "source": self.source, "version": self.version}


@dataclass
class Settings:
    """실험 손잡이. 개선 시도는 한 번에 하나만 바꾼다."""

    top_k: int = 4                  # 카테고리 안에서 프롬프트에 넣을 섹션 수
    min_similarity: float = 0.05    # offline 게이트: 최고 유사도가 이보다 낮으면 보류
    confidence_threshold: float = 0.75  # ① 판정 신뢰도가 이보다 낮으면 되묻기
    use_scope_rules: bool = True    # 문서 '범위' 문단에서 뽑은 규칙으로 보류
    use_term_coverage: bool = True  # 질문의 금융 용어가 카테고리 근거에 없으면 보류
    use_llm_gate: bool = True       # (LLM 모드) 근거 충분성 LLM 판단

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class Assembly:
    category: str
    tool: str | None
    sections: list[Section] = field(default_factory=list)   # 최종적으로 프롬프트에 넣는 섹션
    candidates: list[str] = field(default_factory=list)     # 검색 상위 top_k 후보(게이트가 이 중에서 고른다)
    scores: dict[str, float] = field(default_factory=dict)
    sufficient: bool = False
    handoff_reason: str = ""
    gate: list[dict] = field(default_factory=list)  # 보류 판단 근거 기록


# ---------------------------------------------------------------------------
# 문서 쪼개기
# ---------------------------------------------------------------------------
SECTION_RE = re.compile(r"^## \[([A-Z]{2}-\d{2})\]\s*(.+)$", re.M)
SOURCE_RE = re.compile(r"^> 출처:\s*(.+)$", re.M)


@lru_cache(maxsize=1)
def load_sections() -> dict[str, Section]:
    sections: dict[str, Section] = {}
    for path in sorted(DOCS_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        doc_title = raw.splitlines()[0].lstrip("# ").strip()
        version = (re.search(r"^> 버전:\s*(.+)$", raw, re.M) or [None, ""])[1]
        heads = list(SECTION_RE.finditer(raw))
        for i, m in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(raw)
            chunk = raw[m.end():end]
            src = SOURCE_RE.search(chunk)
            sections[m.group(1)] = Section(
                id=m.group(1), title=m.group(2).strip(), text=SOURCE_RE.sub("", chunk).strip(), doc=path.name,
                doc_title=doc_title, source=src.group(1).strip() if src else "", version=version,
            )
    return sections


def check_mapping() -> list[str]:
    """매핑표 점검: 매핑된 섹션이 실제로 있는지, 어느 카테고리에도 연결되지 않은 섹션, 출처 없는 섹션이 있는지."""
    secs = load_sections()
    problems = []
    mapped = set()
    for key, cat in CATEGORIES.items():
        if key != "C0" and not cat["sections"]:
            problems.append(f"{key}: 연결된 근거 섹션이 없음")
        for sid in cat["sections"]:
            mapped.add(sid)
            if sid not in secs:
                problems.append(f"{key}: 매핑된 {sid}가 문서에 없음")
    for sid, s in secs.items():
        if sid not in mapped:
            problems.append(f"{sid}: 어느 카테고리에도 연결되지 않음")
        if not s.source:
            problems.append(f"{sid}: 출처 줄이 없음")
    return problems


# ---------------------------------------------------------------------------
# 검색 (카테고리 안에서만)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _vectorizer() -> TfidfVectorizer:
    docs = [s.body for s in load_sections().values()]
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), sublinear_tf=True).fit(docs)


def similarity(query: str, texts: list[str]) -> list[float]:
    vec = _vectorizer()
    return cosine_similarity(vec.transform([query]), vec.transform(texts))[0].tolist()


def rank_sections(question: str, section_ids: list[str]) -> list[tuple[Section, float]]:
    secs = load_sections()
    pool = [secs[s] for s in section_ids]
    scores = similarity(question, [s.body for s in pool])
    return sorted(zip(pool, scores), key=lambda x: -x[1])


def terms_in(text: str) -> set[str]:
    found = set()
    for t in TERMS:
        m = re.search(t, text, re.I)
        if m:
            found.add(m.group(0))
    return found


# ---------------------------------------------------------------------------
# ② 근거 조립 + 보류 판단
# ---------------------------------------------------------------------------
def assemble(question: str, category: str, settings: Settings, llm=None) -> Assembly:
    cat = CATEGORIES[category]
    asm = Assembly(category=category, tool=cat["tool"])

    if not cat["tool"]:
        asm.handoff_reason = "사내 헬프데스크가 다루지 않는 범위 밖 문의입니다."
        asm.gate.append({"check": "category", "passed": False, "detail": "C0(범위 밖)"})
        return asm

    ranked = rank_sections(question, cat["sections"])
    asm.scores = {s.id: round(score, 3) for s, score in ranked}
    asm.sections = [s for s, _ in ranked[: settings.top_k]]
    asm.candidates = [s.id for s in asm.sections]

    # (a) 규칙: 각 문서의 '범위' 문단에 적힌, 다루지 않는 요청인가
    if settings.use_scope_rules:
        for pat in GLOBAL_SCOPE_PATTERNS + cat["scope_patterns"]:
            m = re.search(pat, question)
            if m:
                asm.gate.append({"check": "scope_rule", "passed": False, "detail": f"범위 밖 신호 '{m.group(0)}'"})
                asm.handoff_reason = f"사내 규정이 다루지 않는 내용입니다 — {cat['out_of_scope']}"
                return asm
        asm.gate.append({"check": "scope_rule", "passed": True, "detail": "범위 밖 신호 없음"})

    # (b) 용어 커버리지: 질문의 금융 용어가 카테고리 근거 어디에도 없으면 답할 수 없다
    if settings.use_term_coverage:
        cat_text = "\n".join(load_sections()[s].body for s in cat["sections"])
        missing = sorted(t for t in terms_in(question) if not re.search(re.escape(t), cat_text, re.I))
        if missing:
            asm.gate.append({"check": "term_coverage", "passed": False, "detail": f"근거에 없는 용어: {', '.join(missing)}"})
            asm.handoff_reason = f"질문의 핵심 용어({', '.join(missing)})를 다루는 근거가 없습니다."
            return asm
        asm.gate.append({"check": "term_coverage", "passed": True, "detail": "질문 용어가 모두 근거에 있음"})

    # (c) 근거 충분성: LLM 모드는 LLM이 판단하고 필요한 섹션만 고른다. offline은 유사도 하한.
    if llm is not None and llm.online and settings.use_llm_gate:
        from prompts import sufficiency_prompt

        system, user = sufficiency_prompt(question, cat, asm.sections)
        verdict = llm.json(system, user)
        used = [s for s in asm.sections if s.id in set(verdict.get("needed_sections", []))]
        ok = bool(verdict.get("sufficient")) and bool(used)
        asm.gate.append({"check": "llm_gate", "passed": ok, "detail": verdict.get("reason", "")})
        if not ok:
            asm.handoff_reason = verdict.get("missing") or verdict.get("reason") or "근거가 부족합니다."
            return asm
        asm.sections = used
    else:
        best = max(asm.scores.values(), default=0.0)
        ok = best >= settings.min_similarity
        asm.gate.append({"check": "similarity", "passed": ok, "detail": f"최고 유사도 {best:.3f} (하한 {settings.min_similarity})"})
        if not ok:
            asm.handoff_reason = "질문과 충분히 관련된 근거를 찾지 못했습니다."
            return asm

    asm.sufficient = True
    return asm
