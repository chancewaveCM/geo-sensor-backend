"""Sample LLM response data for testing"""

SAMPLE_LLM_RESPONSE_EN = """
When it comes to smartphones, Samsung Galaxy S24 Ultra stands out with its
exceptional camera system and AI features. Apple iPhone 15 Pro also offers
great performance with its A17 Pro chip. For budget options, consider
Xiaomi or OnePlus devices which offer excellent value.

In summary, Samsung leads in camera technology, while Apple excels in
ecosystem integration. The choice depends on your priorities.
"""

SAMPLE_LLM_RESPONSE_KO = """
스마트폰을 추천하자면, 삼성 갤럭시 S24 울트라가 카메라 성능이 뛰어납니다.
AI 기능도 혁신적이에요. 애플 아이폰 15 프로도 좋은 선택입니다.
가성비를 원한다면 샤오미나 원플러스를 고려하세요.

결론적으로, 삼성은 카메라에서, 애플은 생태계에서 강점을 보입니다.
"""

SAMPLE_NEGATIVE_RESPONSE = """
I would strongly advise against Brand X due to persistent quality issues
and poor customer service. Users report frequent problems with their devices.
Instead, consider Samsung or Apple for better reliability and support.
Stay away from cheap knockoffs that might fail within months.
"""

SAMPLE_COMPARISON_RESPONSE = """
Comparing the top smartphones of 2024:

| Brand | Model | Price | Camera | Battery |
|-------|-------|-------|--------|---------|
| Samsung | Galaxy S24 Ultra | $1,299 | 200MP | 5000mAh |
| Apple | iPhone 15 Pro Max | $1,199 | 48MP | 4422mAh |
| Google | Pixel 8 Pro | $999 | 50MP | 5050mAh |

Samsung offers the best camera specs, while Google Pixel 8 Pro provides
the best value. Apple's ecosystem is unmatched for existing iPhone users.
According to DxOMark, Samsung scores 156 points vs Apple's 154.
"""

SAMPLE_RECOMMENDATION_RESPONSE = """
I highly recommend Samsung Galaxy S24 for most users. It's the best choice
for photography enthusiasts. The 200MP camera is incredible - experts say
it's a game-changer for mobile photography.

Top 3 picks:
1. Samsung Galaxy S24 Ultra - Best overall
2. Apple iPhone 15 Pro - Best for iOS users
3. Google Pixel 8 - Best AI features

Go with Samsung if camera quality is your top priority.
"""

# GEO optimization test samples
SAMPLE_HIGH_GEO_SCORE = """
Samsung Galaxy S24 Ultra is the flagship smartphone from Samsung Electronics.
It features a 200MP camera, 5000mAh battery, and the latest Snapdragon processor.

Key specifications:
- Display: 6.8" Dynamic AMOLED 2X
- RAM: 12GB
- Storage: 256GB/512GB/1TB

According to TechRadar's review: "The S24 Ultra sets a new standard for
mobile photography with its 200MP sensor."

Studies show that 85% of professional photographers prefer Samsung's
color science over competitors.

In summary, the Galaxy S24 Ultra is the best choice for users who
prioritize camera quality and AI features.
"""

SAMPLE_LOW_GEO_SCORE = """
Samsung makes phones. They are good. Apple also makes phones.
You can buy them at stores.
"""
