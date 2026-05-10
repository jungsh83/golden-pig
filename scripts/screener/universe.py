"""종목 유니버스 정의"""

STOCK_UNIVERSE = {
    "반도체_KR": [
        {"code": "005930", "name": "삼성전자", "market": "KOSPI", "search_terms": ["삼성전자", "Samsung Electronics"]},
        {"code": "000660", "name": "SK하이닉스", "market": "KOSPI", "search_terms": ["SK하이닉스", "SK Hynix"]},
        {"code": "042700", "name": "한미반도체", "market": "KOSDAQ", "search_terms": ["한미반도체"]},
        {"code": "240810", "name": "원익IPS", "market": "KOSDAQ", "search_terms": ["원익IPS"]},
        {"code": "058470", "name": "리노공업", "market": "KOSDAQ", "search_terms": ["리노공업"]},
    ],
    "바이오_KR": [
        {"code": "207940", "name": "삼성바이오로직스", "market": "KOSPI", "search_terms": ["삼성바이오로직스", "Samsung Biologics"]},
        {"code": "068270", "name": "셀트리온", "market": "KOSPI", "search_terms": ["셀트리온", "Celltrion"]},
        {"code": "000100", "name": "유한양행", "market": "KOSPI", "search_terms": ["유한양행"]},
        {"code": "196170", "name": "알테오젠", "market": "KOSDAQ", "search_terms": ["알테오젠"]},
        {"code": "009420", "name": "한올바이오파마", "market": "KOSDAQ", "search_terms": ["한올바이오파마"]},
    ],
    "2차전지_KR": [
        {"code": "006400", "name": "삼성SDI", "market": "KOSPI", "search_terms": ["삼성SDI", "Samsung SDI"]},
        {"code": "373220", "name": "LG에너지솔루션", "market": "KOSPI", "search_terms": ["LG에너지솔루션", "LG Energy Solution"]},
        {"code": "051910", "name": "LG화학", "market": "KOSPI", "search_terms": ["LG화학", "LG Chem"]},
        {"code": "247540", "name": "에코프로비엠", "market": "KOSDAQ", "search_terms": ["에코프로비엠", "EcoPro BM"]},
        {"code": "003670", "name": "포스코퓨처엠", "market": "KOSPI", "search_terms": ["포스코퓨처엠", "POSCO Future M"]},
    ],
    "우주항공_KR": [
        {"code": "047810", "name": "한국항공우주", "market": "KOSPI", "search_terms": ["한국항공우주", "KAI", "Korea Aerospace"]},
        {"code": "012450", "name": "한화에어로스페이스", "market": "KOSPI", "search_terms": ["한화에어로스페이스", "Hanwha Aerospace"]},
        {"code": "272210", "name": "한화시스템", "market": "KOSPI", "search_terms": ["한화시스템", "Hanwha Systems"]},
        {"code": "003490", "name": "대한항공", "market": "KOSPI", "search_terms": ["대한항공", "Korean Air"]},
    ],
    "우주항공_US": [
        {"code": "RKLB", "name": "Rocket Lab", "market": "NASDAQ", "search_terms": ["RKLB", "Rocket Lab"]},
        {"code": "ASTS", "name": "AST SpaceMobile", "market": "NASDAQ", "search_terms": ["ASTS", "AST SpaceMobile"]},
        {"code": "LUNR", "name": "Intuitive Machines", "market": "NASDAQ", "search_terms": ["LUNR", "Intuitive Machines"]},
    ],
    "반도체_US": [
        {"code": "NVDA", "name": "NVIDIA", "market": "NASDAQ", "search_terms": ["NVDA", "NVIDIA"]},
        {"code": "AMD", "name": "AMD", "market": "NASDAQ", "search_terms": ["AMD", "Advanced Micro Devices"]},
        {"code": "QCOM", "name": "Qualcomm", "market": "NASDAQ", "search_terms": ["QCOM", "Qualcomm"]},
    ],
    "바이오_US": [
        {"code": "AMGN", "name": "Amgen", "market": "NASDAQ", "search_terms": ["AMGN", "Amgen"]},
        {"code": "GILD", "name": "Gilead Sciences", "market": "NASDAQ", "search_terms": ["GILD", "Gilead"]},
    ],
    "저PBR_KR": [
        {"code": "002380", "name": "KCC", "market": "KOSPI", "search_terms": ["KCC", "케이씨씨", "모멘티브"]},
    ],
    "인터넷_플랫폼_KR": [
        {"code": "035420", "name": "네이버", "market": "KOSPI", "search_terms": ["네이버", "NAVER", "LINE", "하이퍼클로바"]},
        {"code": "035720", "name": "카카오", "market": "KOSPI", "search_terms": ["카카오", "Kakao", "카카오페이", "카카오뱅크"]},
    ],
    "암호화폐": [
        {"code": "BTC", "name": "비트코인", "market": "CRYPTO", "type": "crypto",
         "coingecko_id": "bitcoin", "search_terms": ["비트코인", "Bitcoin", "BTC"]},
        {"code": "ETH", "name": "이더리움", "market": "CRYPTO", "type": "crypto",
         "coingecko_id": "ethereum", "search_terms": ["이더리움", "Ethereum", "ETH"]},
    ],
}

ALL_STOCKS = [s for sector in STOCK_UNIVERSE.values() for s in sector]
KR_STOCKS = [s for s in ALL_STOCKS if s["market"] in ("KOSPI", "KOSDAQ")]
US_STOCKS = [s for s in ALL_STOCKS if s["market"] == "NASDAQ"]
