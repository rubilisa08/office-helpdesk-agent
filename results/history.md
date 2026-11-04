| 시각 | 라벨 | 데이터 | 모델 | 채점기 | 설정 | 도구 호출 | 답변 적절성 | 분류 | 근거 적합 | 답변 정확 | 근거 없는 생성 | 보류 정확 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-04 09:27 | offline-baseline | goldenset.json | offline/rule-based | keyword | decider=llm, top_k=4, conf=0.75, scope=1, term=1, gate=1 | 42/50 (84%) | 25/50 (50%) | 42/50 (84%) | 29/32 (91%) | 12/32 (38%) | 0/33 (0%) | 42/50 (84%) |
| 2026-11-04 11:22 | gemma-holdout | holdout.json | gemini/gemma-4-26b-a4b-it | keyword | decider=llm, top_k=4, conf=0.75, scope=1, term=1, gate=1 | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 8/8 (100%) | 8/8 (100%) | 0/8 (0%) | 10/10 (100%) |
| 2026-11-04 11:35 | gemma-baseline | goldenset.json | gemini/gemma-4-26b-a4b-it | keyword | decider=llm, top_k=4, conf=0.75, scope=1, term=1, gate=1 | 46/50 (92%) | 43/50 (86%) | 47/50 (94%) | 30/32 (94%) | 27/32 (84%) | 0/30 (0%) | 46/50 (92%) |
| 2026-11-04 11:54 | gemma+desc | goldenset.json | gemini/gemma-4-26b-a4b-it | keyword | decider=llm, top_k=4, conf=0.75, scope=1, term=1, gate=1 | 48/50 (96%) | 45/50 (90%) | 49/50 (98%) | 32/32 (100%) | 29/32 (91%) | 0/32 (0%) | 48/50 (96%) |
| 2026-11-04 11:56 | gemma-holdout-final | holdout.json | gemini/gemma-4-26b-a4b-it | keyword | decider=llm, top_k=4, conf=0.75, scope=1, term=1, gate=1 | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 8/8 (100%) | 8/8 (100%) | 0/8 (0%) | 10/10 (100%) |
