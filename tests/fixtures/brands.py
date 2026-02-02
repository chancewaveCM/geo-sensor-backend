"""Sample brand data for testing"""

from app.services.analysis.brand_matcher import Brand

SAMPLE_BRANDS = [
    Brand(
        id=1,
        name="Samsung",
        aliases=["삼성", "Samsung Electronics", "삼성전자"],
        keywords=["galaxy", "갤럭시", "s24", "s23"],
    ),
    Brand(
        id=2,
        name="Apple",
        aliases=["애플", "Apple Inc", "애플사"],
        keywords=["iphone", "아이폰", "macbook", "맥북"],
    ),
    Brand(
        id=3,
        name="Google",
        aliases=["구글", "Google LLC"],
        keywords=["pixel", "픽셀", "android"],
    ),
    Brand(
        id=4,
        name="Xiaomi",
        aliases=["샤오미", "小米", "Xiaomi Inc"],
        keywords=["redmi", "poco", "mi"],
    ),
    Brand(
        id=5,
        name="OnePlus",
        aliases=["원플러스", "一加"],
        keywords=["oneplus", "1+"],
    ),
]

SAMPLE_BRANDS_DICT = [
    {
        "id": 1,
        "name": "Samsung",
        "aliases": ["삼성", "Samsung Electronics"],
        "keywords": ["galaxy", "갤럭시"],
    },
    {
        "id": 2,
        "name": "Apple",
        "aliases": ["애플", "Apple Inc"],
        "keywords": ["iphone", "아이폰"],
    },
    {
        "id": 3,
        "name": "Google",
        "aliases": ["구글"],
        "keywords": ["pixel", "픽셀"],
    },
]

# Ground truth for evaluation testing
GROUND_TRUTH_DATA = [
    {
        "text_id": "sample_en_1",
        "brand_id": 1,
        "brand_name": "Samsung",
        "position_start": 27,
        "position_end": 34,
        "match_type": "exact",
    },
    {
        "text_id": "sample_en_1",
        "brand_id": 2,
        "brand_name": "Apple",
        "position_start": 112,
        "position_end": 117,
        "match_type": "exact",
    },
    {
        "text_id": "sample_en_1",
        "brand_id": 4,
        "brand_name": "Xiaomi",
        "position_start": 192,
        "position_end": 198,
        "match_type": "exact",
    },
]
