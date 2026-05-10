---
name: kis-backtester
description: "KIS 전략을 과거 데이터로 검증하거나 성과를 확인할 때 반드시 사용. '백테스팅', '백테스트 해줘', '전략 검증', '성과 분석', '파라미터 최적화', '수익률 확인', '과거 검증', '샤프 확인', '최대낙폭 보고 싶어', '이 전략 수익률이 어떻게 돼?'라고 할 때 자동 실행된다. backtester MCP 서버를 통해 10개 프리셋(sma_crossover, momentum 등) 또는 .kis.yaml 전략 실행, BacktestResult(총수익률·CAGR·최대낙폭·샤프) 해석, Grid/Random 파라미터 최적화, 배치 전략 비교, 포트폴리오 분석, HTML 리포트 생성을 수행한다."
user-invocable: true
metadata: {"openclaw": {"emoji": "📊", "requires": {"bins": ["uv", "docker"]}}}
---

# [Step 2] KIS 백테스팅

## Purpose

backtester 백테스팅 시스템으로 전략의 과거 성과를 검증한다.
10개 프리셋 또는 Step 1에서 만든 `.kis.yaml`을 실행해 수익률·샤프·최대낙폭을 확인하고,
파라미터 최적화와 HTML 리포트 생성까지 지원한다.
날짜 관련 사용자의 요청이 없으면 end_date는 오늘, start_date는 1년 전을 기본으로 한다.

## Prerequisites (필수)

- **Docker 실행 중** (`quantconnect/lean:latest`) — 백테스트 엔진이 Docker 컨테이너로 동작
- KIS 인증 완료 (`/auth vps` 또는 `/auth prod`)
- MCP 서버 실행 중 (`http://127.0.0.1:3846/mcp`)

```bash
docker ps
docker pull quantconnect/lean:latest   # 이미지 없으면
```

## 서버 시작

```bash
# MCP 서버 (port 3846)
cd $KIS_PROJECT_DIR/backtester && bash scripts/start_mcp.sh

# (선택) Backend REST API (port 8002)
cd $KIS_PROJECT_DIR/backtester && uv run uvicorn backend.main:app --reload --port 8002

# (선택) Frontend
cd $KIS_PROJECT_DIR/backtester/frontend && pnpm dev  # → http://localhost:3001
```

## Workflow

### 0. 백테스트 조건 확인 (커스텀 YAML인 경우)

커스텀 YAML 실행 전, 사용자에게 조건 확인 후 진행:

```
📋 백테스트 조건 확인
| 항목 | 값 |
| 전략 | ... | 기간 | ... | 초기자금 | ... |
이 조건으로 백테스트를 실행할까요?
```

**YAML 사전 검증**: `validate_yaml_tool`로 문법 검증. `value`에 `$param_name` 변수가 있으면 default 값으로 치환.

### 1. 전략 선택

```
Tool: list_presets_tool          # 프리셋 목록 확인
Tool: get_preset_yaml_tool       # { "strategy_id": "sma_crossover" }
Tool: validate_yaml_tool         # { "yaml_content": "..." } — 커스텀 YAML 반드시 먼저 검증
Tool: list_indicators_tool       # 80개 지표 + 57개 캔들스틱 파라미터
```

### 2. 실행

**프리셋**:
```
Tool: run_preset_backtest_tool {
  "strategy_id": "sma_crossover",
  "symbols": ["005930", "000660"],
  "initial_capital": 10000000,
  "param_overrides": { "fast_period": 5, "slow_period": 20 }
}
→ { job_id, status: "running" }
```

**커스텀 YAML**:
```
Tool: run_backtest_tool { "yaml_content": "...", "symbols": ["005930"] }
→ { job_id, status: "running" }
```

**결과 조회** (완료까지 자동 대기):
```
Tool: get_backtest_result_tool { "job_id": "<job_id>" }
→ 완료 시: { status: "completed", result: { metrics, equity_curve, ... } }
→ 실패 시: { status: "failed", error: "..." }

# 즉시 상태만 확인:
Tool: get_backtest_result_tool { "job_id": "<job_id>", "wait": false }
```

### 3. 결과 필드

| 필드 | 의미 |
|------|------|
| `total_return_pct` | 총 수익률 (%) |
| `cagr` | 연평균 복리 수익률 |
| `sharpe_ratio` | 위험 대비 수익 (1.0+ 양호) |
| `max_drawdown` | 최대 낙폭 |
| `win_rate` | 승률 (%) |
| `profit_factor` | 총이익/총손실 비율 |

### 4. 실패 재시도

```
Tool: retry_backtest_tool { "job_id": "<실패한 job_id>" }
→ { new_job_id, status: "running" }
```

### 5. 파라미터 최적화 (선택)

```
Tool: optimize_strategy_tool {
  "strategy_id": "sma_crossover",
  "symbols": ["005930"],
  "parameters": [
    {"name": "fast_period", "min": 2, "max": 20, "step": 3},
    {"name": "slow_period", "min": 10, "max": 60, "step": 10}
  ],
  "search_type": "grid",
  "target": "sharpe_ratio"
}
```

### 6. HTML 리포트

```
Tool: get_report_tool { "job_id": "<job_id>", "format": "html" }
Tool: get_report_tool { "job_id": "<job_id>", "format": "json" }
```

## 10개 프리셋 ID

| ID | 이름 | 카테고리 |
|----|------|----------|
| `sma_crossover` | SMA 골든/데드 크로스 | trend |
| `momentum` | 모멘텀 | momentum |
| `trend_filter_signal` | 추세 필터 + 시그널 | composite |
| `week52_high` | 52주 신고가 돌파 | trend |
| `ma_divergence` | 이동평균 이격도 | mean_reversion |
| `false_breakout` | 추세 돌파 후 이탈 | trend |
| `short_term_reversal` | 단기 반전 | mean_reversion |
| `strong_close` | 강한 종가 | momentum |
| `volatility_breakout` | 변동성 축소 후 확장 | volatility |
| `consecutive_moves` | 연속 상승·하락 | momentum |

## 결과 평가 기준

| 지표 | 기준 |
|------|------|
| Sharpe Ratio | > 1.5 우수 / 1.0~1.5 양호 / < 1.0 개선 필요 |
| Max Drawdown | < 10% 우수 / < 20% 권장 / > 20% 위험 |
| Win Rate | > 55% 양호 |
| Profit Factor | > 1.5 양호 / > 2.0 우수 |

## Troubleshooting

- **MCP 미실행** → `curl http://127.0.0.1:3846/health` 후 `bash $KIS_PROJECT_DIR/backtester/scripts/start_mcp.sh`
- **Docker 미실행** → `docker ps` 후 Docker Desktop 시작
- **인증 오류** → `/auth vps` 또는 `/auth prod`

## 다음 단계

- **[Step 3]** `/kis-order-executor` — 검증된 전략으로 실전/모의 매매
- **[Step 1]** `/kis-strategy-builder` — 성과 부족 시 전략 수정
