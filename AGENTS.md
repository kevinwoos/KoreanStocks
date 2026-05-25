# Korean Stocks AI/ML Analysis System `v0.5.5`

KOSPI/KOSDAQ 종목을 기술적 지표, 머신러닝, 뉴스 감성 분석으로 자동 스크리닝하고 텔레그램 리포트를 발송하는 투자 보조 플랫폼입니다.

## Codex 작업 원칙

- 비즈니스 로직은 `src/koreanstocks/core/`에 유지하고 API/UI 계층과 분리합니다.
- API 서버 없이도 CLI 분석 엔진이 독립 동작해야 합니다.
- 전략, 점수 산식, ML 피처, 모델 가중치 변경은 백테스트 또는 기존 테스트 근거 없이 임의 수정하지 않습니다.
- LLM 호출은 비용을 통제합니다. GPT 호출에는 `max_tokens`를 유지하고, 프롬프트에는 필요한 데이터만 넣습니다.
- 데이터 수집, 외부 API 호출, DB 저장은 예외 처리와 로깅을 포함해야 합니다.
- 기존 사용자 변경을 되돌리지 않습니다. 관련 없는 변경은 그대로 둡니다.

## 기술 스택

- UI: FastAPI, Reveal.js, Vanilla JS
- CLI: Typer (`koreanstocks serve / recommend / analyze / train / outcomes / value / quality / init / sync / home`)
- AI/LLM: OpenAI GPT-4o-mini via `openai`
- ML: Scikit-learn, XGBoost Ranker, LightGBM, CatBoost, optional PyTorch TCN
- 기술 지표: `ta`, `finta`
- 데이터: FinanceDataReader, Naver News API, DART Open API
- DB: SQLite (`data/storage/stock_analysis.db`)
- 자동화: GitHub Actions, Telegram Bot API
- Python: 3.11 through 3.13

## 프로젝트 구조

```text
pyproject.toml
requirements.txt
train_models.py
src/koreanstocks/
  cli.py
  api/
    app.py
    dependencies.py
    routers/
  static/
    index.html
    dashboard.html
    js/
    css/
  core/
    config.py
    constants.py
    data/
      provider.py
      fundamental_provider.py
      database.py
    engine/
      indicators.py
      features.py
      strategy.py
      prediction_model.py
      tcn_model.py
      news_agent.py
      macro_news_agent.py
      analysis_agent.py
      recommendation_agent.py
      value_screener.py
      quality_screener.py
      trainer.py
      scheduler.py
    utils/
      backtester.py
      notifier.py
      outcome_tracker.py
models/saved/
data/storage/
tests/
.github/workflows/
```

## 분석 파이프라인

1. 기술적 지표에서 `tech_score`를 계산합니다.
2. ML 앙상블에서 `ml_score`를 계산합니다. 모델이 없으면 `tech_score`로 폴백합니다.
3. 뉴스와 DART 공시를 GPT로 분석해 `sentiment_score`를 계산합니다.
4. 거시 뉴스 감성과 레짐을 반영합니다.
5. GPT 종합 분석으로 `BUY`, `HOLD`, `SELL`, 요약, 목표가를 생성합니다.

종합 점수 산식은 `src/koreanstocks/core/constants.py`를 정본으로 봅니다. 산식이나 가중치 변경은 사용자 요청 또는 명확한 검증 근거가 있을 때만 수행합니다.

## 주요 명령어

```bash
pip install -e .
koreanstocks init
koreanstocks serve
koreanstocks recommend
koreanstocks analyze 005930
koreanstocks train
python train_models.py
koreanstocks outcomes
koreanstocks value
koreanstocks quality
pytest tests/
python tests/compat_check.py
```

## 환경 변수

```ini
OPENAI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
DART_API_KEY=...
DB_PATH=data/storage/stock_analysis.db
KOREANSTOCKS_BASE_DIR=...
KOREANSTOCKS_GITHUB_DB_URL=...
```

## 코딩 규칙

- 함수 시그니처에는 타입 힌트를 적극 사용합니다.
- 새 에이전트와 유틸리티 함수에는 간결한 docstring을 작성합니다.
- 모델 파일(`.pkl`)을 로드할 때는 대응하는 스케일러도 함께 로드합니다.
- 모델 경로는 하드코딩하지 말고 `pathlib.Path` 기반으로 계산합니다.
- `src/koreanstocks/core/`에서 UI 프레임워크를 import하지 않습니다.
- `src/koreanstocks/core/`가 `src/koreanstocks/api/`를 직접 import하지 않습니다.
- 테스트는 변경 범위에 맞춰 실행합니다. 핵심 점수 산식, 피처, 백테스트, API 계약을 건드리면 관련 테스트를 추가하거나 갱신합니다.

## 자동 수정 금지 대상

- 종합 점수 가중치
- ML 피처 목록
- GitHub Actions 스케줄
- 추천 버킷 비율
- 모델 파라미터 기본값

위 항목은 사용자의 명시 요청이나 검증 자료가 있을 때만 수정합니다.

## Codex 전환 메모

이 저장소의 런타임 AI 연동은 이미 OpenAI SDK(`OPENAI_API_KEY`, `config.DEFAULT_MODEL`)를 사용합니다. Codex 전환의 기준 파일은 이 `AGENTS.md`이며, 기존 `CLAUDE.md`는 과거 Claude Code용 지침으로 남아 있을 수 있습니다.
