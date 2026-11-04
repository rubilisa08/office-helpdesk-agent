# 사내 문의 응대 라우팅 에이전트 (새솔컴퍼니 헬프데스크)

직원 문의를 **IT지원 · 인사 · 총무 · 경비정산 · 범위 밖**으로 분류하고, 그 분야의 **사내 규정에서만 근거를 찾아 답하며**, 분야가 모호하면 **되묻고**, 규정에 없으면 **지어내지 않고 담당 부서로 연결**하는 라우팅 에이전트.

```
입력 → ① 판정(신뢰도) → 신뢰도 점검(낮으면 되묻기) → ② 근거 조립(부족하면 담당자 연결) → ③ 근거만으로 답변 → ④ 검증
```

설계 판단과 측정 결과는 [REPORT.md](REPORT.md)에 있다. 재무·회계 학습 에이전트 [fin-routing-agent](https://github.com/rubilisa08/fin-routing-agent)와 같은 구조로 만들었다.

> 근거 문서는 과제용 **가상 회사 '새솔컴퍼니'의 가상 규정**이다. 실제 회사와 무관하다. 근로시간·연장근로·연차의 법정 기준만 실제 근로기준법 조항을 요약했다.

## 실행 (Windows PowerShell 기준)

```powershell
pip install -r requirements.txt
```

`.env.example`을 복사해 이름을 `.env`로 바꾸고 `OPENAI_API_KEY`를 넣는다. 키가 없으면 offline 모드로 동작한다.

```powershell
python -m streamlit run app.py
```

```powershell
python agent.py "연차는 며칠 전까지 신청해야 해요?"
```

```powershell
python evaluate.py --validate-grader
```

```powershell
python evaluate.py --label baseline
```

```powershell
python evaluate.py --data data/holdout.json --label holdout
```

손잡이 하나만 바꿔 다시 측정: `--conf 0.7`(신뢰도 임계값), `--top-k 6`, `--no-scope-rules`, `--no-term-coverage`, `--no-llm-gate`, `--provider offline`, `--grader keyword`, `--decider jev`.

## 구조

```
docs/                 사내 규정 4개 · 33개 섹션 (섹션마다 ID·출처 조항·버전)
data/goldenset.json   평가셋 50문항 (기대 도구 · 필수 사실 · 금지 표현 · 모범/오답 답안)
data/holdout.json     과적합 점검용 미공개 10문항
data/fewshot.json     프롬프트 예시 (평가셋과 분리)
prompts.py            분류 지침 · 근거 충분성 판단 · 답변 규칙 · 채점 지침
context.py            문서 쪼개기 · 카테고리↔섹션 매핑표 · 근거 조립과 담당자 연결 판단
agent.py              LangGraph 파이프라인
verify.py             기계적 검증 (출처·인용 범위·카테고리 일치·계산 재검산·수치·용어·임의 약속 금지)
llm.py / jev.py       OpenAI·Gemini·offline 백엔드, Jev 의사결정 모델(선택), 응답 캐시
evaluate.py           과제 지표 2개 + PRD 지표 5개, 채점기 검증, 오답 분석
app.py                Streamlit 데모
results/              측정 기록 (history.md = 개선 시도별 기록표)
```
