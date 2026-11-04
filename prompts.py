"""분류 지침 · 근거 충분성 판단 · 답변 규칙 · 채점 지침.

예시는 data/fewshot.json에서만 가져온다(평가셋과 분리).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

FEWSHOT_PATH = Path(__file__).parent / "data" / "fewshot.json"


@lru_cache(maxsize=1)
def fewshot() -> dict:
    return json.loads(FEWSHOT_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# ① 카테고리 판정: 카테고리와 신뢰도만 낸다. 되묻기·보류 여부는 여기서 판단하지 않는다.
# ---------------------------------------------------------------------------
EVIDENCE_TYPES = ["기준·자격", "절차·신청 방법", "기한", "금액·한도", "담당 부서", "금지·예외", "계산"]


def router_prompt(question: str, categories: dict) -> tuple[str, str]:
    cat_lines = "\n".join(f"- {k}: {c['name']}({c['en']}) — {c['description']}" for k, c in categories.items())
    examples = "\n".join(
        f"질문: {e['question']}\n출력: {json.dumps({k: e[k] for k in ('category', 'confidence', 'alternative', 'evidence_types')}, ensure_ascii=False)}"
        for e in fewshot()["router"]
    )
    system = f"""너는 사내 헬프데스크로 들어온 직원 문의를 담당 분야별로 분류하는 분류기다.
질문 하나를 아래 카테고리 중 정확히 하나로 분류하고, 그 분류를 얼마나 확신하는지 함께 낸다.

{cat_lines}

규칙:
- 문의가 '어느 부서의 규정·절차'를 묻는지로 고른다. 질문에 나온 단어가 아니라 질문의 의도를 본다(예: '야근 택시비'는 근무시간이 아니라 경비정산).
- 답을 알고 있는지, 근거가 있는지는 판단하지 않는다. 그 판단은 다음 단계가 한다.
- 사내 제도·절차를 묻는 문의는 C1~C4 중 하나다. 그 분야 안에서 규정에 없을 법한 세부나 예외를 묻더라도 분야는 그대로 고른다.
- 회사 업무와 무관한 개인 질문, 주식·투자, 다른 회사 제도, 다른 직원의 개인정보 요청, 잡담은 C0다.
- confidence(0~1)는 '이 카테고리가 맞을 가능성'이다. 질문이 두 분야 중 어느 쪽인지 질문만으로 정할 수 없으면 0.6 미만으로 낮게 주고, alternative에 두 번째 후보 카테고리를 적는다. 분명하면 alternative는 null.
- evidence_types에는 답에 필요한 근거 유형을 {EVIDENCE_TYPES} 중에서 고른다.
- JSON으로만 답한다: {{"category": "<C0~C4>", "confidence": 0.0~1.0, "alternative": "<C0~C4>" 또는 null, "evidence_types": [...], "reason": "<한 문장>"}}

예시:
{examples}"""
    return system, f"질문: {question}"


# offline(키 없음) 분류 지침: 분야별 키워드. 가장 많이 겹치는 분야를 고르고, 겹친 비율을 신뢰도로 쓴다.
OFFLINE_KEYWORDS = {
    "C1": ["it", "비밀번호", "계정", "로그인", "잠김", "sso", "vpn", "otp", "노트북", "모니터", "장비", "소프트웨어", "프로그램",
           "설치", "관리자 권한", "피싱", "악성코드", "보안", "메일", "첨부", "프린터", "출력", "헬프데스크"],
    "C2": ["연차", "반차", "휴가", "경조", "병가", "근무시간", "출근", "퇴근", "시차", "코어타임", "연장근로", "야근 수당",
           "대체휴무", "재택", "증명서", "재직", "경력", "원천징수", "인사"],
    "C3": ["사원증", "출입", "회의실", "비품", "사무용품", "의자", "책상", "택배", "우편", "주차", "명함", "시설",
           "냉난방", "에어컨", "누수", "법인차량", "차량 예약", "총무"],
    "C4": ["경비", "정산", "법인카드", "카드 한도", "영수증", "증빙", "세금계산서", "식대", "회식", "출장", "일비", "숙박",
           "택시", "교통비", "접대", "개인카드", "반려"],
}
OFFLINE_OTHER_SIGNALS = [r"주식|코인|비트코인|사도 ?될까", r"점심 ?메뉴|날씨|맛집|연애", r"다른 회사|타사"]


# ---------------------------------------------------------------------------
# ② 근거 충분성(보류 판단): 고른 카테고리의 근거만으로 답할 수 있는가
# ---------------------------------------------------------------------------
def sufficiency_prompt(question: str, category: dict, sections: list) -> tuple[str, str]:
    ex = "\n\n".join(
        f"질문: {e['question']}\n근거 섹션: {', '.join(e['sections'])}\n출력: {json.dumps(e['verdict'], ensure_ascii=False)}"
        for e in fewshot()["sufficiency"]
    )
    system = f"""너는 근거 충분성 심사관이다. 아래 근거 섹션'만'으로 질문에 답할 수 있는지 판단한다.
너의 일반 지식으로 보충해야만 답할 수 있다면 충분하지 않다.

판단 기준:
- 문의가 요구하는 핵심 정보(기준, 절차, 기한, 금액·한도, 담당 부서)가 근거에 명시되어 있어야 sufficient=true.
- 문의가 근거에 없는 제도, 개인별 정보(본인 급여액·평가 결과), 예외 승인을 요구하면 sufficient=false.
- 이 카테고리({category['name']})가 다루지 않는 범위: {category['out_of_scope']}
- needed_sections에는 답변에 실제로 필요한 섹션 ID만 넣는다. 관련 없는 섹션은 빼라.
- JSON으로만 답한다: {{"sufficient": true|false, "needed_sections": ["ID", ...], "reason": "<한 문장>", "missing": "<부족한 정보, 충분하면 빈 문자열>"}}

예시:
{ex}"""
    body = "\n\n".join(s.body for s in sections)
    return system, f"질문: {question}\n\n근거 섹션:\n{body}"


# ---------------------------------------------------------------------------
# ③ 근거만으로 답변
# ---------------------------------------------------------------------------
ANSWER_RULES = """너는 새솔컴퍼니 사내 헬프데스크 담당자다. 직원 문의에 아래 '근거 섹션'(사내 규정)에 적힌 내용만으로 정중하게 답한다.

답변 규칙:
1. 근거에 없는 사실·수치·용어·예시를 덧붙이지 않는다. 너의 일반 지식으로 보충하지 않는다.
2. 모든 문장 끝에 근거 섹션 ID를 [HR-03]처럼 붙인다. 근거 섹션 목록에 있는 ID만 쓴다.
3. 수치는 근거에 적힌 그대로 쓴다. 질문에 숫자가 주어진 계산 문제라면 근거의 공식에 그 숫자를 넣어 '계산식 = 결과' 형태로 한 줄에 보여 준다(예: 20,000 × 3 = 60,000원). 계산식은 검증 단계에서 다시 계산된다.
4. 문의의 일부를 근거가 다루지 않으면, 그 부분은 '규정에 없는 내용'이라고 밝히고 담당 부서 문의를 안내하며 추측하지 않는다.
5. 승인·예외 처리를 약속하지 않는다. 승인은 팀장·담당 부서의 권한이므로 '규정상 ~이 필요합니다'처럼 절차를 안내한다.
6. 문의가 잘못된 전제(예: '그냥 쓰면 되죠?', '나중에 내도 되죠?')를 깔고 있으면 근거에 따라 바로잡는다.
7. 한국어 존댓말로 2~6문장, 필요하면 짧은 목록을 쓴다. 신청 경로(사내 포털 메뉴, 시스템 이름)가 근거에 있으면 함께 알려 준다.
8. 출처 목록은 따로 붙이지 않는다. 시스템이 인용한 섹션 ID로 출처 목록을 만든다."""


def answer_prompt(question: str, sections: list, feedback: list[str] | None = None) -> tuple[str, str]:
    ex = "\n\n".join(f"질문: {e['question']}\n답변: {e['answer']}" for e in fewshot()["answer"])
    system = f"{ANSWER_RULES}\n\n예시:\n{ex}"
    body = "\n\n".join(s.body for s in sections)
    user = f"근거 섹션:\n{body}\n\n질문: {question}"
    if feedback:
        user += "\n\n이전 답변이 검증에 실패했다. 다음 문제를 고쳐서 다시 답하라:\n- " + "\n- ".join(feedback)
    return system, user


# ---------------------------------------------------------------------------
# 채점기(LLM judge): 표현이 아니라 사실을 본다
# ---------------------------------------------------------------------------
JUDGE_SYSTEM = """너는 엄격한 채점관이다. 답변이 '반드시 담아야 할 사실'을 담았는지, '말하면 안 되는 것'을 말했는지 판정한다.

채점 원칙:
- 표현이 아니라 사실(의미)을 본다. 단어가 달라도 같은 사실을 말하면 담은 것이다. 같은 단어가 있어도 다른 뜻이면 담지 않은 것이다.
- 사실의 일부만 담았으면 담지 않은 것으로 본다(예: 세 요소 중 둘만 말함).
- '말하면 안 되는 것'은 답변이 그 주장을 긍정하거나 사실처럼 제시할 때만 위반이다. 그 주장을 부정·반박하거나 '그렇게 단정할 수 없다'고 말하는 것은 위반이 아니다.
- 답변의 근거 표기([HR-03] 등)는 채점과 무관하다.
- JSON으로만 답한다:
{"facts": [{"fact": "...", "included": true|false, "why": "..."}], "violations": [{"claim": "...", "violated": true|false, "why": "..."}]}"""


def judge_prompt(question: str, answer: str, must_include: list[str], must_not: list[str]) -> tuple[str, str]:
    user = (
        f"질문: {question}\n\n답변:\n{answer}\n\n"
        f"반드시 담아야 할 사실:\n" + "\n".join(f"- {f}" for f in must_include) + "\n\n"
        f"말하면 안 되는 것:\n" + "\n".join(f"- {c}" for c in must_not)
    )
    return JUDGE_SYSTEM, user


# ---------------------------------------------------------------------------
# Jev(의사결정 모델)에게 묻는 질문. Jev는 글 대신 질문별 보정된 확률을 돌려준다.
# ---------------------------------------------------------------------------
def jev_router_questions(categories: dict) -> dict:
    """① 판정: 카테고리 하나를 고르는 choice 질문 + 근거 유형별 noul 질문(같은 호출에서 병렬 평가)."""
    from jev import choice, noul

    qs = {
        "category": choice(
            "이 직원 문의는 어느 부서의 규정·절차를 묻는가? 질문에 나온 단어가 아니라 질문의 의도를 본다. "
            "답을 알고 있는지, 근거가 있는지는 판단하지 않는다. 사내 제도를 묻는 문의는 규정에 없을 법한 세부를 묻더라도 그 분야를 고른다.",
            {k: f"{c['name']}({c['en']}): {c['description']}" for k, c in categories.items()},
        )
    }
    for i, t in enumerate(EVIDENCE_TYPES):
        qs[f"etype_{i}"] = noul(f"이 질문에 답하려면 '{t}' 유형의 근거가 필요한가?")
    return qs


def jev_gate_questions(category: dict, sections: list) -> dict:
    """② 근거 충분성: 근거만으로 답할 수 있는가 + 섹션별로 필요한가."""
    from jev import noul

    qs = {
        "answerable": noul(
            "근거 섹션'만'으로, 일반 지식을 보충하지 않고 질문에 답할 수 있는가?",
            true="문의가 요구하는 핵심 정보(기준·절차·기한·금액·담당 부서)가 근거 섹션에 명시되어 있다.",
            false=f"문의가 근거에 없는 정보를 요구한다(예: 규정에 없는 제도, 개인별 급여·평가, 예외 승인). "
                  f"이 분야가 다루지 않는 범위: {category['out_of_scope']}",
        )
    }
    for s in sections:
        qs[f"need_{s.id}"] = noul(f"질문에 답하려면 섹션 [{s.id}] {s.title}의 내용이 필요한가?")
    return qs


def jev_support_questions(sentences: list[str]) -> dict:
    """④ 문장별 근거 지지: 답변의 각 문장이 근거 섹션으로 뒷받침되는가."""
    from jev import noul

    return {
        f"s{i}": noul(
            f"답변 문장이 근거 섹션에 의해 직접 뒷받침되는가? 문장: {s}",
            true="문장의 사실·수치·주장이 모두 근거 섹션에 있거나, 근거의 공식에 질문의 숫자를 넣어 계산한 결과다.",
            false="근거 섹션에 없는 사실·수치·주장이 들어 있다.",
        )
        for i, s in enumerate(sentences)
    }
