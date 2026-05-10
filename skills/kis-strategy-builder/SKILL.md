---
name: kis-strategy-builder
description: "KIS 트레이딩 전략을 설계하거나 .kis.yaml 파일을 만들 때 반드시 사용. '전략 만들어줘', '전략 설계', 'YAML 전략', '지표 조합', '매매 조건 짜줘', '전략 파일', 'RSI 전략 만들어줘', 'MACD+볼린저 전략', '골든크로스 전략', 'strategy builder'라고 할 때 자동 실행된다. strategy_builder 비주얼 빌더 안내, 10개 프리셋 전략 소개, 기술적 지표(RSI/MACD/BB/EMA 등) 기반 진입·청산 조건 설계, .kis.yaml 포맷 생성, DSL 조건식 작성을 수행한다. 완성된 YAML은 백테스팅(Step 2)이나 주문 실행(Step 3)에 바로 사용 가능하다."
user-invocable: true
metadata: {"openclaw": {"emoji": "📈", "requires": {"bins": ["uv"]}}}
---

# [Step 1] KIS 전략 설계

## Purpose

strategy_builder 비주얼 빌더를 활용해 기술적 지표 기반 트레이딩 전략을 설계하고 `.kis.yaml` 파일로 내보낸다.
완성된 YAML은 백테스팅(Step 2) 또는 실시간 신호 생성(Step 3)에 바로 사용한다.

## 서버 시작 (필요 시)

```bash
# Backend
cd $KIS_PROJECT_DIR/strategy_builder && uv run uvicorn backend.main:app --reload --port 8000

# Frontend
cd $KIS_PROJECT_DIR/strategy_builder/frontend && pnpm dev
# → http://localhost:3000/builder
```

## Workflow

### 1. 전략 유형 파악

- 10개 프리셋 중 선택 vs. 커스텀 설계
- 카테고리: `trend` / `momentum` / `mean_reversion` / `volatility` / `oscillator`

### 2. 지표 선택

83개 기술지표 (전체 활성화):

| 계열 | 지표 |
|------|------|
| 이동평균 | SMA, EMA, VWAP |
| 모멘텀 | RSI, MACD, ROC, Returns |
| 변동성 | BB, ATR, STD, Volatility, ZScore |
| 오실레이터 | Stoch, CCI, Williams%R, MFI, IBS |
| 추세 | ADX, Disparity |
| 거래량 | OBV |
| 기타 | Consecutive, Change, CustomCandle |

### 3. 진입·청산 조건 설계

**연산자**: `greater_than` / `less_than` / `cross_above` / `cross_below` / `equals` / `not_equal` / `breaks`

> `greater_than_or_equal` / `gte` / `lte` 는 **지원하지 않는다**.
> `>= 50` 조건은 `greater_than: 50` (정수 RSI에서 실질 동일) 으로 표현한다.

**로직 결합**: `AND` / `OR`

**캔들 패턴** (66종 예시):
`hammer`, `inverted_hammer`, `doji`, `engulfing`, `harami`,
`morning_star`, `evening_star`, `three_white_soldiers`, `three_black_crows`,
`shooting_star`, `hanging_man`, `piercing`

### 4. 리스크 관리

`risk`는 최상위 키 (`strategy` 블록 밖). `enabled: true`와 `percent` 필드가 필수다.

```yaml
risk:
  stop_loss:
    enabled: true
    percent: 3.0
  take_profit:
    enabled: true
    percent: 8.0
  trailing_stop:
    enabled: true
    percent: 2.0
```

> `risk: {}` 또는 `strategy` 안에 `risk:` 를 넣으면 백테스터 런타임 오류 발생.

### 5. 파라미터 확인

YAML 생성 전, 사용자에게 주요 파라미터를 표로 보여주고 확인받는다.

### 6. YAML 생성

조건의 `value` 필드에는 반드시 **숫자 리터럴**을 사용한다. `$param_name` 변수 참조 금지.

```yaml
version: "1.0"
metadata:
  name: RSI 과매도 전략
  description: RSI 30 이하 진입, 70 이상 청산
  category: momentum
  author: user

strategy:
  id: rsi_oversold
  indicators:
    - id: rsi
      alias: rsi
      params:
        period: 14

  entry:
    conditions:
      - indicator: rsi
        operator: less_than
        value: 30
    logic: AND

  exit:
    conditions:
      - indicator: rsi
        operator: greater_than
        value: 70
    logic: AND

risk:
  stop_loss:
    enabled: true
    percent: 3.0
  take_profit:
    enabled: true
    percent: 8.0
```

### 7. 다중 출력 지표 (MACD 골든크로스)

MACD는 **단일 alias**에서 `output`과 `compare_output`으로 두 출력을 비교한다.

```yaml
entry:
  logic: AND
  conditions:
    - indicator: macd
      output: value
      operator: cross_above
      compare_to: macd
      compare_output: signal
```

> 두 개 alias로 분리하면 크로스오버가 동작하지 않는다. 반드시 **단일 alias + compare_output** 패턴 사용.

## 10개 프리셋 전략

| ID | 이름 | 카테고리 | 주요 지표 |
|----|------|----------|----------|
| `golden_cross` | 골든크로스 | trend | SMA(50), SMA(200) |
| `adx_trend` | ADX 강한 추세 | trend | ADX(14) |
| `obv_divergence` | OBV 다이버전스 | volume | OBV |
| `mfi_oversold` | MFI 과매도 | oscillator | MFI(14) |
| `vwap_bounce` | VWAP 반등 | trend | VWAP |
| `cci_reversal` | CCI 반전 | oscillator | CCI(20) |
| `williams_reversal` | Williams %R 반전 | oscillator | Williams%R(14) |
| `atr_breakout` | ATR 변동성 돌파 | volatility | ATR(14) |
| `disparity_mean_revert` | 이격도 평균회귀 | mean_reversion | Disparity(20) |
| `consecutive_candle` | 연속 캔들 패턴 | momentum | Consecutive(3) |

## 다음 단계

- **[Step 2]** `/kis-backtester` — 완성된 YAML로 과거 성과 검증
- **[Step 3]** `/kis-order-executor` — 바로 신호 생성 후 주문
