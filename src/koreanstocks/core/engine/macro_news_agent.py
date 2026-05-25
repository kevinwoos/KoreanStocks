"""거시경제 뉴스 감성 분석 + 시장 레짐 감지 (Phase 2 & 3)

MacroNewsAgent
  - Naver 뉴스 API로 거시 키워드 뉴스 수집 → GPT 감성 점수화 (하루 1회 캐시)
  - 시장 데이터(VIX·장단기 스프레드·S&P500·CSI300) 기반 레짐 자동 분류

레짐 3단계
  risk_on   (위험선호): VIX < 15, 스프레드 양수, 시장 상승
  uncertain (불확실)  : 중립 구간
  risk_off  (위험회피): VIX > 25, 스프레드 역전, 시장 하락
"""
import html
import json
import logging
import time
from datetime import date
from typing import Any, Dict, List, Tuple

import openai
import requests
from openai import RateLimitError as _OpenAIRateLimitError

from koreanstocks.core.config import config

logger = logging.getLogger(__name__)

# 거시 뉴스 검색 키워드 (Naver 뉴스 API, 키워드당 최신 5건)
_MACRO_KEYWORDS = [
    "연준 금리",
    "미국 증시",
    "유가 원유",
    "달러 환율",
    "중국 경기",
    "반도체 수출",
]

# 레짐 판정 임계값
_VIX_RISK_OFF  = 25.0   # VIX > 25  → risk_off 가중
_VIX_RISK_ON   = 15.0   # VIX < 15  → risk_on  가중
_SPREAD_INVERT = -0.3   # 10Y-3M 스프레드 < -0.3%p → 역전 경보


class MacroNewsAgent:
    """거시경제 뉴스 감성 분석(Phase 2) + 시장 레짐 감지(Phase 3) 에이전트.

    Public API
    ----------
    get_macro_context() → Dict
        macro_sentiment_score : int   (-100~100)
        macro_regime          : str   ("risk_on" | "uncertain" | "risk_off")
        macro_regime_label    : str   ("위험선호" | "불확실" | "위험회피")
        macro_summary         : str   (거시 한 줄 요약)
    """

    def __init__(self) -> None:
        self.client = config.create_openai_client(openai)
        self._cache: Dict[str, Any] = {}   # {"date": str, "result": dict}

    # ── 퍼블릭 ────────────────────────────────────────────────────────────────

    def get_macro_context(self) -> Dict[str, Any]:
        """오늘의 거시경제 컨텍스트 반환 (일별 캐시, GPT 호출 1회).

        캐시 히트 시 네트워크 호출 없음.
        GPT / Naver API 실패 시 중립 기본값으로 graceful fallback.
        """
        today = date.today().isoformat()
        if self._cache.get("date") == today and self._cache.get("result"):
            return self._cache["result"]

        # 1. Naver 뉴스 수집 → GPT 감성 분석
        news = self._fetch_macro_news()
        result = self._analyze(news) if news else {
            "macro_sentiment_score": 0,
            "macro_summary": "거시 뉴스 수집 실패",
        }

        # 2. 퀀트 레짐 감지 (시장 데이터 기반 — GPT 무관)
        regime, regime_label = self._detect_regime()
        result["macro_regime"]       = regime
        result["macro_regime_label"] = regime_label

        self._cache = {"date": today, "result": result}
        logger.info(
            f"[MacroContext] 레짐={regime_label} "
            f"거시감성={result.get('macro_sentiment_score', 0):+d} "
            f"요약={result.get('macro_summary', '')[:40]}"
        )
        return result

    # ── 뉴스 수집 ─────────────────────────────────────────────────────────────

    def _fetch_macro_news(self) -> List[Dict[str, str]]:
        """거시 키워드별 Naver 뉴스 최신 5건 수집 (중복 제목 제거)."""
        if not config.NAVER_CLIENT_ID or not config.NAVER_CLIENT_SECRET:
            logger.debug("[MacroNews] Naver API 키 미설정 — 수집 건너뜀")
            return []

        headers = {
            "X-Naver-Client-Id":     config.NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
        }
        seen: Dict[str, str] = {}   # title → keyword
        for kw in _MACRO_KEYWORDS:
            try:
                resp = requests.get(
                    "https://openapi.naver.com/v1/search/news.json",
                    headers=headers,
                    params={"query": kw, "display": 5, "sort": "date"},
                    timeout=8,
                )
                if resp.status_code != 200:
                    continue
                for item in resp.json().get("items", []):
                    # html.unescape 로 모든 HTML 엔티티(&lt; &gt; &#39; 등) + <b> 태그 제거
                    raw_title = item.get("title", "")
                    title = html.unescape(raw_title).replace("<b>", "").replace("</b>", "").strip()
                    if title and title not in seen:
                        seen[title] = kw
            except Exception as e:
                logger.debug(f"[MacroNews] 뉴스 수집 실패 ({kw}): {e}")

        items = [{"title": t, "keyword": k} for t, k in seen.items()]
        logger.debug(f"[MacroNews] 거시 뉴스 {len(items)}건 수집")
        return items

    # ── GPT 감성 분석 ────────────────────────────────────────────────────────

    def _analyze(self, news: List[Dict[str, str]]) -> Dict[str, Any]:
        """GPT-4o-mini로 거시 뉴스 감성 점수 + 한 줄 요약 산출."""
        lines = "\n".join(
            f"- [{item['keyword']}] {item['title']}"
            for item in news[:30]
        )
        prompt = f"""다음은 오늘의 거시경제 뉴스 헤드라인입니다.

{lines}

위 뉴스를 바탕으로 향후 1~2주 한국 주식시장(KOSPI·KOSDAQ) 전반에 미칠
거시경제적 영향을 평가해주세요.

채점 기준:
- +50~+100: 연준 금리 인하 확정, 강력한 중국 부양책, 유가 급락
- +20~+50 : 금리 동결 기대, 달러 안정, 중국 PMI 회복
- -20~+20 : 중립/혼조, 방향 불명확
- -50~-20 : 금리 인상 우려, 달러 강세, 유가 급등
- -100~-50: 금리 급등, 글로벌 침체 신호, 금융 위기

반드시 JSON 형식으로만 응답:
{{
    "macro_sentiment_score": 숫자(-100~100),
    "macro_summary": "한 줄 요약 (50자 이내, 핵심 거시 이슈 위주)"
}}"""

        for attempt in range(2):
            try:
                resp = self.client.chat.completions.create(
                    model=config.DEFAULT_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "당신은 거시경제 전문 퀀트 애널리스트입니다. "
                                "반드시 JSON 형식으로만 답변하세요."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_completion_tokens=120,
                )
                data = json.loads(resp.choices[0].message.content)
                score = max(-100, min(100, int(float(data.get("macro_sentiment_score", 0)))))
                return {
                    "macro_sentiment_score": score,
                    "macro_summary":         str(data.get("macro_summary", "")),
                }
            except _OpenAIRateLimitError:
                if attempt == 0:
                    logger.warning("[MacroNews] GPT Rate limit — 10초 후 재시도")
                    time.sleep(10)
            except Exception as e:
                logger.warning(f"[MacroNews] GPT 분석 실패: {e}")
                break

        return {"macro_sentiment_score": 0, "macro_summary": "거시 분석 실패"}

    # ── 퀀트 레짐 감지 (Phase 3) ───────────────────────────────────────────────

    def _detect_regime(self) -> Tuple[str, str]:
        """VIX·장단기 스프레드·글로벌 증시 기반 레짐 자동 분류.

        prediction_model의 캐시된 macro_df 재사용 → 추가 API 호출 없음.

        Returns
        -------
        (regime_key, regime_label)
          ("risk_on",   "위험선호")
          ("uncertain", "불확실")
          ("risk_off",  "위험회피")
        """
        try:
            # 순환 임포트 방지: 함수 내 지연 임포트
            from koreanstocks.core.engine.prediction_model import prediction_model
            macro_df = prediction_model._get_macro_df()
            if macro_df.empty:
                return "uncertain", "불확실"

            latest = macro_df.iloc[-1]
            vix     = float(latest.get("vix_level",    20.0))
            vix_chg = float(latest.get("vix_change_5d", 0.0))
            spread  = float(latest.get("yield_spread",  1.0))
            sp500   = float(latest.get("sp500_1m",      0.0))
            csi300  = float(latest.get("csi300_1m",     0.0))

            # 위험회피 점수 (클수록 risk_off)
            off = 0
            if vix > _VIX_RISK_OFF:    off += 2
            elif vix > 20:             off += 1
            if vix_chg > 0.20:         off += 1   # VIX 5일 +20% 급등
            if spread < _SPREAD_INVERT: off += 2  # 장단기 역전
            elif spread < 0.5:         off += 1
            if sp500  < -0.05:         off += 1   # S&P 1개월 -5%
            if csi300 < -0.05:         off += 1   # CSI300 1개월 -5%

            # 위험선호 점수 (클수록 risk_on)
            on = 0
            if vix < _VIX_RISK_ON:     on += 2
            elif vix < 18:             on += 1
            if spread > 1.5:           on += 1
            if sp500  > 0.03:          on += 1
            if csi300 > 0.03:          on += 1

            logger.debug(
                f"[MacroRegime] VIX={vix:.1f} chg={vix_chg:.1%} "
                f"spread={spread:.2f}pp sp500={sp500:.1%} csi300={csi300:.1%} "
                f"off={off} on={on}"
            )

            if off >= 3:  return "risk_off",  "위험회피"
            if on  >= 3:  return "risk_on",   "위험선호"
            return "uncertain", "불확실"

        except Exception as e:
            logger.warning(f"[MacroRegime] 레짐 감지 실패: {e}")
            return "uncertain", "불확실"


macro_news_agent = MacroNewsAgent()
