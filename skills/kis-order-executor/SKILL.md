---
name: kis-order-executor
description: "KIS 전략의 실시간 신호를 확인하거나 주문을 실행할 때 반드시 사용. '전략 실행해줘', '신호 확인', '종목 돌려봐줘', '매수 신호 있어?', '매도 타이밍', '실시간 매매', '자동매매', '삼성전자 지금 들어가도 돼?', '이 전략으로 주문 넣어줘'라고 할 때 자동 실행된다. 종목 코드를 먼저 선택한 뒤 전략을 실행해 BUY·SELL·HOLD 신호와 강도(0~1)를 확인하고, 신호 강도에 따라 모의(vps)/실전(prod) 주문을 실행한다. 실전투자 주문 전 반드시 사용자 확인을 받는다."
user-invocable: true
metadata: {"openclaw": {"emoji": "🔔", "requires": {"bins": ["uv"]}}}
---

# [Step 3] KIS 전략 실행 & 신호 기반 주문

## Purpose

종목을 선택하고 전략을 실행해 BUY/SELL/HOLD 신호를 확인한다.
신호 강도에 따라 모의(vps) 또는 실전(prod) 주문으로 이어진다.

> **중요**: 직접 주문 요청("삼성전자 매수해줘")이 아니라,
> **종목 선택 → 전략 실행 → 신호 확인** 과정을 거친 뒤에만 주문이 발생한다.

## 안전 규칙

- **실전(prod) 주문**: 종목명·수량·예상금액 명시 후 반드시 사용자 확인
- **주문 전**: 현재 모드(vps/prod) 반드시 고지
- **신호 강도 < 0.5**: 자동으로 주문 건너뜀

## Prerequisites

- KIS 인증 완료: `/auth vps` (모의) 또는 `/auth prod` (실전)
- strategy_builder 백엔드 실행 중 (port 8000)

## 서버 시작

```bash
cd $KIS_PROJECT_DIR/strategy_builder && uv run uvicorn backend.main:app --reload --port 8000
cd $KIS_PROJECT_DIR/strategy_builder/frontend && pnpm dev  # → http://localhost:3000/execute
```

## 주문 가능 시간 (KST 기준, 한국 주식)

| 시간대 | 시간 | 주문 유형 |
|--------|------|----------|
| 장 전 시간외 | 08:00~09:00 | 지정가만 |
| 정규장 | 09:00~15:30 | 시장가·지정가 |
| 장 후 시간외 | 15:40~18:00 | 지정가만 |

## Workflow

### 1. 인증 확인

```bash
/auth   # 현재 모드(vps/prod) 및 토큰 만료 시간 확인
```

### 2. 종목 선택

```bash
GET /api/symbols/search?q=삼성
codes: ["005930", "000660", "035420"]
```

### 3. 전략 선택

```bash
GET /api/strategies          # 프리셋 목록
GET /api/strategies/custom   # 커스텀 YAML
```

### 4. 전략 실행 → 신호 생성

```bash
POST /api/strategies/execute
Body: {
  "strategy_id": "golden_cross",
  "codes": ["005930", "000660"],
  "params": { "fast_period": 50, "slow_period": 200 }
}
```

응답:
```json
[
  { "code": "005930", "name": "삼성전자", "action": "BUY", "strength": 0.85, "reason": "RSI 28.3 < 30" },
  { "code": "000660", "name": "SK하이닉스", "action": "HOLD", "strength": 0.3, "reason": "RSI 45.2 범위 내" }
]
```

### 5. 신호 해석

| 강도 | 의미 | 주문 유형 |
|------|------|----------|
| 0.8~1.0 | 강한 신호 | 시장가 |
| 0.5~0.8 | 보통 신호 | 지정가 |
| 0.0~0.5 미만 | 약한 신호 | 주문 안 함 |

### 6. 주문 실행

**실전(prod)** — 고지 후 사용자 확인 필수:
```
종목: 삼성전자 (005930) / 수량: 10주 / 예상금액: 약 730,000원 / 모드: 실전투자
→ 실행하시겠습니까?
```

```bash
POST /api/orders
Body: {
  "code": "005930",
  "action": "BUY",
  "quantity": 10,
  "order_type": "market"   # market | limit
}
```

### 7. 결과 모니터링

```bash
GET /api/account/holdings   # 보유종목
GET /api/orders/history     # 주문 내역
```

## Troubleshooting

- **인증 오류** → `/auth` 후 `/auth vps` 또는 `/auth prod` 재인증
- **주문 거부** → 잔고 부족 또는 거래 시간 외
- **신호 없음** → 전략 조건 미충족. 파라미터 조정 또는 다른 전략 시도
- **execute 오류** → `lsof -i :8000` 으로 백엔드 실행 확인

## 다음 단계

- **[Step 1]** `/kis-strategy-builder` — 신호가 기대와 다를 때 전략 수정
- **[Step 2]** `/kis-backtester` — 실행 전 성과 재검증
