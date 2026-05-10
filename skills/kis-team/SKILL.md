---
name: kis-team
description: "Orchestrate full KIS pipeline from strategy design to backtest to execution. Use when user asks for end-to-end flow like '전략부터 주문까지', '다 해줘', or full pipeline automation with stage-by-stage confirmation."
user-invocable: true
metadata: {"openclaw": {"emoji": "🦁", "requires": {"bins": ["uv", "docker"]}}}
---

# KIS Team Orchestrator

전략 설계 → 백테스팅 → 주문 실행의 3단계 파이프라인을 단계별 사용자 확인과 함께 조율한다.

## Stages

1. **전략 설계** (`kis-strategy-builder`) — 지표 조합 + `.kis.yaml` 생성
2. **백테스트 검증** (`kis-backtester`) — 과거 성과 확인 + 파라미터 최적화
3. **신호 & 주문 실행** (`kis-order-executor`) — BUY/SELL/HOLD 신호 확인 후 주문

## Rules

- Stage 1 시작 전, 현재 인증 상태 확인.
- 각 Stage 종료 후 결과 요약 + 다음 Stage 진행 여부 사용자 확인.
- Stage 3에서 모드가 `prod`이면 명확한 경고와 함께 확인 요청.
- Stage 실패 시 원인 보고 후 재시도/수정 여부 질문. 자동 진행 금지.
