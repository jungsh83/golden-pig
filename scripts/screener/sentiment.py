"""FinBERT 기반 금융 뉴스/소셜 감성 분석 (로컬, API 키 불필요)

모델: ProsusAI/finbert (금융 특화 BERT, HuggingFace)
라벨: positive / negative / neutral → -1.0 ~ +1.0 점수로 변환
"""

import re
from functools import lru_cache


@lru_cache(maxsize=1)
def _load_pipeline():
    from transformers import pipeline
    return pipeline(
        "text-classification",
        model="ProsusAI/finbert",
        tokenizer="ProsusAI/finbert",
        top_k=None,
        truncation=True,
        max_length=512,
    )


def _score_texts(texts: list[str]) -> tuple[float, str]:
    """텍스트 리스트를 FinBERT로 분석해 평균 점수 반환"""
    if not texts:
        return 0.0, "NEUTRAL"

    pipe = _load_pipeline()
    total_score = 0.0
    count = 0

    for text in texts[:8]:  # 최대 8개 분석
        text_clean = re.sub(r"\s+", " ", text).strip()[:400]
        if not text_clean:
            continue
        try:
            results = pipe(text_clean)[0]
            label_scores = {r["label"]: r["score"] for r in results}
            pos = label_scores.get("positive", 0)
            neg = label_scores.get("negative", 0)
            # -1(매우부정) ~ +1(매우긍정)
            total_score += pos - neg
            count += 1
        except Exception:
            continue

    if count == 0:
        return 0.0, "NEUTRAL"

    avg = total_score / count
    if avg > 0.15:
        label = "BULLISH"
    elif avg < -0.15:
        label = "BEARISH"
    else:
        label = "NEUTRAL"

    return round(avg, 3), label


def analyze_sentiment(stock_name: str, news_items: list, social_items: list) -> dict:
    """뉴스 + 소셜 텍스트를 FinBERT로 감성 분석 → -1.0 ~ +1.0 점수 반환"""
    texts = []

    for item in news_items:
        title = item.get("title", "")
        summary = item.get("summary", "")
        if title:
            texts.append(title + (" " + summary if summary else ""))

    for item in social_items:
        text = item.get("text") or item.get("title", "")
        if text:
            texts.append(text)

    if not texts:
        return {
            "score": 0.0,
            "label": "NEUTRAL",
            "reason": "수집된 텍스트 없음",
            "key_topics": [],
        }

    try:
        score, label = _score_texts(texts)

        # 주요 토픽: 자주 등장하는 핵심 단어 추출
        all_text = " ".join(texts[:5])
        topic_patterns = [
            "실적", "영업이익", "매출", "반도체", "AI", "HBM", "수출", "투자",
            "배당", "주가", "목표가", "상승", "하락", "신고가", "매수", "매도",
            "earnings", "revenue", "growth", "AI", "chip", "outlook",
        ]
        found_topics = [t for t in topic_patterns if t.lower() in all_text.lower()][:3]

        reason_map = {
            "BULLISH": f"긍정 뉴스 우세 (점수 {score:+.2f})",
            "BEARISH": f"부정 뉴스 우세 (점수 {score:+.2f})",
            "NEUTRAL": f"중립적 뉴스 흐름 (점수 {score:+.2f})",
        }

        return {
            "score": score,
            "label": label,
            "reason": reason_map[label],
            "key_topics": found_topics,
        }

    except Exception as e:
        return {
            "score": 0.0,
            "label": "NEUTRAL",
            "reason": f"분석 오류: {e}",
            "key_topics": [],
        }
