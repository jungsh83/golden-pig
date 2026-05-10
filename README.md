# 🐷 Golden Pig — 개인 자동매매 플랫폼

> **Personal Fork** of [koreainvestment/open-trading-api](https://github.com/koreainvestment/open-trading-api)
> 원본 코드 위에 자동매매·백테스팅·AI 에이전트를 추가한 개인 트레이딩 플랫폼입니다.

---

## 이 레포에 대해

한국투자증권(KIS) Open API 공식 샘플 코드를 기반으로, 실제 자동매매 운영에 필요한 기능들을 직접 구축하고 있습니다.

- **원본 출처**: [koreainvestment/open-trading-api](https://github.com/koreainvestment/open-trading-api) (한국투자증권)
- **라이선스**: 원본 라이선스를 따르며, 추가 코드는 개인 사용 목적입니다.
- **업스트림 동기화**: `git fetch upstream && git merge upstream/main`

---

## 개인적으로 추가한 것들

### 📊 자동매매 스크립트 (`scripts/`)

| 파일 | 역할 | 실행 주기 |
|------|------|-----------|
| `auto_trader.py` | 삼성전자·SK하이닉스 15분봉 자동매매 | 평일 09:00~15:30 (15분 간격) |
| `check_signal.py` | MACD+RSI 신호 확인 → Discord 전송 | 평일 09:10 / 12:10 / 15:00 |
| `run_screener.py` | 29개 종목 기술·센티먼트 스크리닝 | 평일 08:30 |
| `morning_briefing.py` | 반도체 섹터 뉴스 감성 분석 브리핑 | 평일 06:30 |
| `post_to_x.py` | 일일 매매 성과 X(트위터) 자동 게시 | 평일 15:40 |

### 📈 트레이딩 전략 (`strategies/`)

| 파일 | 전략 | 종목 |
|------|------|------|
| `samsung_macd_rsi.kis.yaml` | MACD(8/17/6) + RSI(14) 적극 전략 | 삼성전자 005930 |
| `hynix_macd_momentum.kis.yaml` | MACD + 모멘텀 복합 전략 | SK하이닉스 000660 |

### 🤖 Claude Code AI 에이전트 (`.claude/`)

KIS 인증·주문·백테스팅을 자연어로 제어하는 AI 에이전트 설정.

```
# 모의투자 인증
/auth vps

# 신호 확인 및 주문
/kis-order-executor

# 전략 백테스팅
/kis-backtester

# 새 전략 설계
/kis-strategy-builder
```

### ⏰ Cron 자동화

모든 스크립트는 macOS crontab에 등록되어 장중 자동 실행됩니다.
Discord 채널으로 신호·체결·브리핑 알림이 전송됩니다.

---

## 폴더 구조

```
golden-pig/
├── scripts/              # 자동매매·스크리너·브리핑 스크립트  ← 개인 추가
├── strategies/           # .kis.yaml 전략 파일               ← 개인 추가
├── .claude/              # Claude Code AI 에이전트 설정       ← 개인 추가
├── strategy_builder/     # 비주얼 전략 설계 UI
├── backtester/           # 백테스팅 엔진 + MCP 서버
├── MCP/                  # KIS Code Assistant MCP
├── examples_llm/         # LLM용 API 샘플 (원본)
├── examples_user/        # 사용자용 API 샘플 (원본)
├── legacy/               # 구버전 샘플 (원본)
└── stocks_info/          # 종목 참고 데이터 (원본)
```

---

## 빠른 시작

### 1. 환경 설정

```bash
# 클론
git clone https://github.com/jungsh83/golden-pig
cd golden-pig

# 의존성 설치
uv sync

# KIS 계정 설정 (gitignore됨 — 직접 작성)
cp kis_devlp.yaml.example kis_devlp.yaml
# kis_devlp.yaml에 앱키·앱시크릿·계좌번호 입력
```

### 2. KIS 인증

```bash
# 모의투자 인증
uv run .claude/scripts/do_auth.py vps

# 실전투자 인증
uv run .claude/scripts/do_auth.py prod
```

### 3. 신호 확인

```bash
# 삼성전자 매매 신호 즉시 확인
cd backtester
uv run python ../scripts/check_signal.py
```

### 4. 전략 빌더 / 백테스터

```bash
cd strategy_builder && ./start.sh   # 전략 설계
cd backtester && ./start.sh         # 백테스팅
```

---

## 전략 파이프라인

```
전략 설계 (.kis.yaml)
    → 백테스팅 (backtester)
        → 신호 확인 (check_signal.py)
            → 자동매매 (auto_trader.py)
                → Discord 알림 + X 게시
```

### 현재 운용 전략 성과

백테스트 결과는 `backtester/examples/output/reports/`에 저장됩니다.

---

## 업스트림 업데이트 받기

```bash
git fetch upstream
git merge upstream/main
git push origin main
```

충돌 발생 시 `scripts/`, `strategies/`, `.claude/` 폴더는 개인 추가 파일이므로 내 버전을 유지합니다.

---

## 참고

- [KIS Open API 포털](https://apiportal.koreainvestment.com/)
- [원본 레포 README](https://github.com/koreainvestment/open-trading-api#readme)
- [strategy_builder README](strategy_builder/README.md)
- [backtester README](backtester/README.md)

> ⚠️ 이 레포의 자동매매 코드는 개인 투자 목적으로 작성되었습니다.
> 투자 결과에 대한 책임은 전적으로 본인에게 있습니다.
