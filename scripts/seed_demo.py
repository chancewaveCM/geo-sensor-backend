#!/usr/bin/env python3
"""
GEO Sensor MVP - Demo Seed Script
==================================
Generates realistic Korean AI search market analysis demo data.

Usage:
    cd geo-sensor-backend
    python scripts/seed_demo.py

Notes:
    - Uses sqlite3 directly (no async SQLAlchemy)
    - Idempotent: deletes existing demo data first
    - All IDs are INTEGER autoincrement (omit id, use lastrowid)
"""

import json
import random
import sqlite3
import sys
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

from passlib.context import CryptContext

warnings.filterwarnings("ignore")

DB_PATH = Path(__file__).resolve().parent.parent / "geo_sensor.db"
DEMO_EMAIL = "demo@geosensor.ai"
DEMO_PASSWORD = "Demo1234!"

# Generate hash dynamically to avoid stale hardcoded hash issues
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
PASSWORD_HASH = _pwd_ctx.hash(DEMO_PASSWORD)

NOW = datetime.now(UTC)
random.seed(42)


def ts(
    offset_days: float = 0,
    offset_hours: float = 0,
    offset_minutes: float = 0,
) -> str:
    """ISO timestamp with offset from NOW."""
    dt = NOW + timedelta(
        days=offset_days,
        hours=offset_hours,
        minutes=offset_minutes,
    )
    return dt.isoformat()


# ------------------------------------------------------------------
# Korean AI search market response templates (12 total)
# ------------------------------------------------------------------

RESPONSE_TEMPLATES = [
    (
        "한국의 AI 검색 시장은 네이버를 중심으로 빠르게 "
        "변화하고 있습니다. 네이버의 AI 검색 서비스 "
        "'Cue:'는 자연어 처리 기술을 활용하여 사용자 "
        "질문에 대한 종합적인 답변을 제공합니다. "
        "구글코리아 역시 Gemini 기반의 AI Overview를 "
        "한국 시장에 도입하며 경쟁을 강화하고 있습니다. "
        "카카오는 자체 AI 모델 'KoGPT'를 활용한 검색 "
        "기능 개선에 주력하고 있으며, 다음 포털과의 "
        "통합을 통해 사용자 경험을 혁신하고 있습니다. "
        "빙은 마이크로소프트의 Copilot 기술을 앞세워 "
        "한국 시장 점유율 확대를 시도하고 있으나, "
        "아직 네이버와 구글에 비해 인지도가 낮은 "
        "상황입니다. 전문가들은 2026년 한국 AI 검색 "
        "시장이 약 3조 원 규모로 성장할 것으로 "
        "전망하고 있으며, 네이버가 국내 시장에서 "
        "여전히 강력한 입지를 유지할 것으로 예상합니다."
    ),
    (
        "AI 검색 기술의 발전으로 한국 검색 시장의 "
        "지형이 재편되고 있습니다. 네이버는 "
        "하이퍼클로바X 기반의 AI 검색을 통해 "
        "사용자 만족도를 크게 향상시켰습니다. "
        "특히 네이버의 강점은 한국어 이해도에 있으며, "
        "한국 문화와 맥락을 반영한 검색 결과를 "
        "제공합니다. 구글코리아는 글로벌 AI 기술력을 "
        "바탕으로 한국어 지원을 강화하고 있지만, "
        "로컬 콘텐츠 측면에서는 네이버에 뒤처지는 "
        "모습입니다. 카카오는 다음 검색과 카카오톡을 "
        "연계한 AI 검색 생태계를 구축하고 있으며, "
        "모바일 중심의 사용자 경험을 차별화 포인트로 "
        "내세우고 있습니다. 빙은 기업용 시장에서 "
        "Microsoft 365 통합을 통해 경쟁력을 확보하려는 "
        "전략을 펼치고 있습니다."
    ),
    (
        "2026년 한국 AI 검색 시장의 핵심 트렌드는 "
        "'대화형 검색'입니다. 네이버의 Cue: 서비스는 "
        "멀티턴 대화를 지원하며, 사용자의 후속 질문에도 "
        "맥락을 유지한 채 답변을 제공합니다. "
        "구글은 AI Overview를 통해 검색 결과 상단에 "
        "AI 요약을 표시하고 있으며, 한국어 품질이 "
        "크게 개선되었습니다. 카카오는 챗봇 기반 검색 "
        "경험을 제공하며, 특히 쇼핑과 로컬 서비스 "
        "검색에서 강점을 보이고 있습니다. 다음은 "
        "뉴스 큐레이션과 AI를 결합한 서비스로 "
        "차별화를 시도하고 있으며, 빙은 Copilot을 "
        "활용한 창작 지원 검색으로 틈새 시장을 "
        "공략하고 있습니다. 전반적으로 네이버가 "
        "한국어 AI 검색에서 가장 앞선 기술력을 "
        "보유하고 있다는 평가입니다."
    ),
    (
        "한국 소비자들의 AI 검색 이용 패턴을 분석한 "
        "결과, 네이버 AI 검색의 일일 활성 사용자 수는 "
        "약 1,500만 명으로 추정됩니다. 구글코리아의 "
        "AI 검색 사용자는 약 800만 명 수준이며, "
        "카카오(다음 포함)는 약 600만 명으로 3위를 "
        "차지하고 있습니다. 빙은 약 150만 명의 "
        "사용자를 확보하고 있습니다. 흥미로운 점은 "
        "네이버 사용자들의 AI 검색 만족도가 82%로 "
        "가장 높았으며, 구글코리아가 78%, 카카오가 "
        "71%를 기록했습니다. 네이버의 높은 만족도는 "
        "한국어 이해력과 로컬 정보의 정확성에 "
        "기인하는 것으로 분석됩니다. 다만 기술적 "
        "정확성 측면에서는 구글이 네이버를 약간 "
        "앞서는 것으로 나타났습니다."
    ),
    (
        "한국 AI 검색 시장에서 브랜드 신뢰도 조사 "
        "결과를 살펴보면, 네이버가 전체 응답자의 "
        "45%에서 '가장 신뢰하는 AI 검색'으로 "
        "선정되었습니다. 구글코리아는 32%, 카카오는 "
        "15%, 빙은 5%, 기타 3%를 차지했습니다. "
        "네이버는 특히 쇼핑 검색과 지역 정보 검색에서 "
        "압도적인 신뢰도를 보였으며, 구글은 학술 "
        "정보와 글로벌 트렌드 검색에서 높은 평가를 "
        "받았습니다. 카카오는 실시간 트렌드와 소셜 "
        "연계 검색에서, 다음은 뉴스 검색에서 각각 "
        "강점을 보여주었습니다. 빙은 업무용 검색에서 "
        "일정 수준의 신뢰도를 확보하고 있으나, "
        "일반 소비자 시장에서의 인지도는 여전히 "
        "제한적입니다."
    ),
    (
        "AI 검색 기술 투자 규모를 비교하면, 네이버는 "
        "2025년 한 해 동안 AI 연구개발에 약 "
        "1조 2천억 원을 투자했으며, 이는 전년 대비 "
        "40% 증가한 수치입니다. 구글코리아는 한국 내 "
        "AI 연구센터 확장에 약 5천억 원을 투입했습니다. "
        "카카오는 AI 분야에 3천억 원을 투자하며 검색 "
        "품질 개선과 새로운 AI 서비스 개발에 집중하고 "
        "있습니다. 다음은 카카오 그룹의 투자 일환으로 "
        "콘텐츠 AI에 약 800억 원을 배정받았습니다. "
        "이러한 대규모 투자는 한국 AI 검색 시장의 "
        "기술 격차를 더욱 벌리고 있으며, 네이버와 "
        "구글의 양강 구도가 당분간 지속될 것으로 "
        "전망됩니다. 빙은 글로벌 차원의 투자를 "
        "한국에도 적용하고 있지만, 현지화에는 "
        "한계가 있습니다."
    ),
    (
        "한국 AI 검색의 정확도 벤치마크 테스트 결과, "
        "네이버의 하이퍼클로바X 기반 검색은 한국어 "
        "질의응답 정확도에서 87.3%를 기록하며 1위를 "
        "차지했습니다. 구글의 Gemini 기반 검색은 "
        "84.1%로 2위, 카카오의 KoGPT 기반 검색은 "
        "79.8%로 3위를 기록했습니다. 다음은 카카오 "
        "인프라를 활용해 78.2%의 정확도를 보였으며, "
        "빙의 Copilot 기반 검색은 75.5%를 기록했습니다. "
        "특히 한국 문화, 역사, 시사 관련 질문에서 "
        "네이버의 정확도가 두드러졌으며, 이는 방대한 "
        "한국어 학습 데이터와 지식백과 연동의 결과로 "
        "분석됩니다. 반면 영어 혼합 검색이나 "
        "코드 검색에서는 구글이 더 높은 성능을 "
        "보여주었습니다."
    ),
    (
        "한국의 주요 AI 검색 서비스별 차별화 전략을 "
        "분석하겠습니다. 네이버는 '스마트블록'과 "
        "'AI 브리핑' 기능을 통해 검색 결과를 시각적으로 "
        "정리하여 제공하는 데 강점이 있습니다. "
        "구글코리아는 'AI Overview'와 'Circle to Search' "
        "기능으로 멀티모달 검색 경험을 선도하고 "
        "있습니다. 카카오는 카카오톡 내 AI 검색 통합으로 "
        "메신저 기반의 자연스러운 검색 경험을 제공하며, "
        "다음 포털에서는 뉴스 AI 요약 서비스를 "
        "차별화 포인트로 내세우고 있습니다. 빙은 "
        "이미지 생성과 문서 작성 등 생산성 도구와의 "
        "연계를 강조하고 있습니다. 전체적으로 한국 "
        "시장에서는 네이버의 포괄적인 AI 검색 "
        "생태계가 가장 높은 평가를 받고 있으며, "
        "구글이 기술 혁신 측면에서 근접한 경쟁을 "
        "펼치고 있습니다."
    ),
    (
        "모바일 AI 검색 시장에서의 경쟁 양상을 "
        "살펴보면, 네이버 앱의 AI 검색 기능 사용률이 "
        "전체 모바일 검색의 58%를 차지하며 "
        "압도적 1위를 기록하고 있습니다. 구글 검색 "
        "앱과 크롬 브라우저를 통한 AI 검색은 25%를 "
        "차지하고 있으며, 카카오톡 내 AI 검색이 12%, "
        "기타(다음 앱, 빙 앱 등)가 5%를 차지합니다. "
        "네이버의 모바일 강세는 네이버 앱의 높은 "
        "설치율과 다양한 부가 서비스(쇼핑, 지도, "
        "예약 등)와의 연계에 기인합니다. 카카오는 "
        "메신저 플랫폼의 강점을 활용해 대화형 "
        "검색에서 차별화를 시도하고 있으며, 구글은 "
        "안드로이드 기본 검색엔진이라는 이점을 "
        "활용하고 있습니다. 빙은 모바일에서의 "
        "존재감이 미미한 상황이나, Edge 브라우저 "
        "사전 설치 전략으로 점유율 확대를 "
        "노리고 있습니다."
    ),
    (
        "AI 검색 광고 시장 전망에 따르면, 한국의 "
        "AI 검색 광고 시장은 2026년 약 1조 5천억 원 "
        "규모로 예상됩니다. 네이버는 AI 검색 결과 내 "
        "자연스러운 광고 통합으로 광고주들의 높은 "
        "관심을 받고 있으며, 클릭률이 기존 검색 광고 "
        "대비 35% 높은 것으로 나타났습니다. "
        "구글코리아는 AI Overview 내 광고 도입을 "
        "시작하며, Performance Max 캠페인과의 "
        "연계를 강화하고 있습니다. 카카오는 "
        "카카오 비즈보드와 AI 검색을 연동한 새로운 "
        "광고 상품을 출시했으며, 다음 뉴스 AI 요약 "
        "서비스에도 네이티브 광고를 도입했습니다. "
        "빙은 Microsoft Advertising 플랫폼을 통해 "
        "B2B 중심의 AI 검색 광고를 제공하고 있습니다. "
        "광고 효과 측면에서 네이버 AI 검색 광고의 "
        "ROI가 가장 높은 것으로 조사되었습니다."
    ),
    (
        "한국 AI 검색 서비스의 개인정보 보호 정책을 "
        "비교 분석합니다. 네이버는 검색 데이터의 "
        "익명화 처리와 사용자 동의 기반 데이터 활용 "
        "정책을 운영하고 있으며, 국내 개인정보 보호법 "
        "준수에 있어 가장 적극적인 태도를 보이고 "
        "있습니다. 구글코리아는 글로벌 프라이버시 "
        "정책을 적용하면서도 한국 법규에 맞는 추가 "
        "보호 조치를 시행하고 있습니다. 카카오는 "
        "AI 검색 데이터와 카카오톡 대화 데이터의 "
        "분리 저장 원칙을 강조하며, 다음 검색 기록의 "
        "자동 삭제 기능을 제공하고 있습니다. 빙은 "
        "Microsoft의 Responsible AI 원칙에 따라 "
        "투명한 데이터 처리를 표방하고 있으나, "
        "한국 사용자 특화 정책은 상대적으로 "
        "부족한 상황입니다. 전반적으로 네이버와 "
        "카카오가 한국 규제 환경에 더 잘 적응하고 "
        "있다는 평가를 받고 있습니다."
    ),
    (
        "AI 검색 기반 콘텐츠 추천 시스템의 성능을 "
        "비교하면, 네이버의 AiTEMS 추천 엔진은 "
        "사용자 행동 데이터와 AI 검색 이력을 결합하여 "
        "개인화된 콘텐츠를 제공합니다. 추천 정확도는 "
        "업계 최고 수준인 91.2%를 기록하고 있습니다. "
        "구글의 Discover 피드는 AI 검색 쿼리를 활용한 "
        "관심사 예측에서 88.7%의 정확도를 보여주고 "
        "있으며, 카카오의 추천 시스템은 카카오톡, "
        "다음, 카카오스토리 등 자사 플랫폼 데이터를 "
        "통합 활용하여 85.3%의 정확도를 달성했습니다. "
        "빙은 LinkedIn과 Microsoft 365 데이터를 "
        "활용한 비즈니스 콘텐츠 추천에서 차별화를 "
        "시도하고 있으며, 82.1%의 정확도를 "
        "기록했습니다. 다음은 뉴스 콘텐츠 추천에 "
        "특화되어 있으며, 뉴스 추천 정확도는 89.5%로 "
        "높은 수준을 유지하고 있습니다."
    ),
]

# Brand distribution weights for citations
BRAND_WEIGHTS = {
    "네이버": 0.35,
    "구글": 0.28,
    "카카오": 0.18,
    "다음": 0.12,
    "빙": 0.07,
}

BRAND_LIST = list(BRAND_WEIGHTS.keys())
BRAND_CUMULATIVE: list[tuple[str, float]] = []
_cum = 0.0
for _b, _wt in BRAND_WEIGHTS.items():
    _cum += _wt
    BRAND_CUMULATIVE.append((_b, _cum))


def pick_brand() -> str:
    """Pick a brand based on weighted distribution."""
    r = random.random()
    for brand, threshold in BRAND_CUMULATIVE:
        if r <= threshold:
            return brand
    return BRAND_LIST[0]


def find_brand_span(
    content: str, brand: str,
) -> tuple[str, int]:
    """Find a citation span containing the brand."""
    idx = content.find(brand)
    if idx == -1:
        return brand, 0
    start = max(0, idx - 20)
    end = min(len(content), idx + len(brand) + 30)
    span = content[start:end]
    return span, idx


def _insert(cur, table: str, data: dict) -> int:
    """Insert a row and return its autoincrement id."""
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"  # noqa: S608
    cur.execute(sql, list(data.values()))
    return cur.lastrowid


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def seed_demo():  # noqa: C901, PLR0912, PLR0915
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = OFF")
    cur = conn.cursor()

    print("=" * 60)
    print("  GEO Sensor Demo Seed Script")
    print("=" * 60)

    # ---------------------------------------------------------------
    # Phase 0: Clean existing demo data
    # ---------------------------------------------------------------
    print("\n[Phase 0] Cleaning existing demo data...")

    cur.execute(
        "SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,),
    )
    row = cur.fetchone()
    old_demo_id = row[0] if row else None

    if old_demo_id:
        # Find workspace
        cur.execute(
            "SELECT w.id FROM workspaces w "
            "JOIN workspace_members wm ON wm.workspace_id = w.id "
            "WHERE wm.user_id = ? AND wm.role = 'admin'",
            (old_demo_id,),
        )
        ws_row = cur.fetchone()
        ws_id = ws_row[0] if ws_row else None

        # Gather member IDs
        member_ids = [old_demo_id]
        if ws_id:
            cur.execute(
                "SELECT user_id FROM workspace_members "
                "WHERE workspace_id = ?",
                (ws_id,),
            )
            member_ids = [r[0] for r in cur.fetchall()]

        # Cascade delete via simple approach: delete everything
        # that references demo-owned entities
        _clean_demo_data(cur, old_demo_id, ws_id, member_ids)
        conn.commit()
        print("  Cleaned existing demo data.")
    else:
        print("  No existing demo data found.")

    # ---------------------------------------------------------------
    # Phase 1: Users + Workspace
    # ---------------------------------------------------------------
    print("\n[Phase 1] Creating users and workspace...")

    demo_uid = _insert(cur, "users", {
        "email": DEMO_EMAIL,
        "hashed_password": PASSWORD_HASH,
        "full_name": "김지현",
        "is_active": 1,
        "is_superuser": 0,
        "created_at": ts(-30),
        "updated_at": ts(-1),
        "avatar_url": None,
        "notification_preferences": json.dumps(
            {"email": True, "push": True},
        ),
    })

    park_uid = _insert(cur, "users", {
        "email": "park@geosensor.ai",
        "hashed_password": PASSWORD_HASH,
        "full_name": "박서준",
        "is_active": 1,
        "is_superuser": 0,
        "created_at": ts(-28),
        "updated_at": ts(-2),
        "avatar_url": None,
        "notification_preferences": json.dumps(
            {"email": True, "push": False},
        ),
    })

    lee_uid = _insert(cur, "users", {
        "email": "lee@geosensor.ai",
        "hashed_password": PASSWORD_HASH,
        "full_name": "이수민",
        "is_active": 1,
        "is_superuser": 0,
        "created_at": ts(-25),
        "updated_at": ts(-1),
        "avatar_url": None,
        "notification_preferences": json.dumps(
            {"email": False, "push": True},
        ),
    })

    choi_uid = _insert(cur, "users", {
        "email": "choi@geosensor.ai",
        "hashed_password": PASSWORD_HASH,
        "full_name": "최하늘",
        "is_active": 1,
        "is_superuser": 0,
        "created_at": ts(-20),
        "updated_at": ts(-3),
        "avatar_url": None,
        "notification_preferences": json.dumps(
            {"email": True, "push": True},
        ),
    })

    all_user_ids = [demo_uid, park_uid, lee_uid, choi_uid]
    print(f"  Created {len(all_user_ids)} users")

    ws_id = _insert(cur, "workspaces", {
        "name": "GEO Sensor Demo",
        "slug": "geo-sensor-demo",
        "description": "AI 검색 시장 분석 데모 워크스페이스",
        "created_at": ts(-30),
        "updated_at": ts(-1),
    })

    _insert(cur, "workspace_members", {
        "workspace_id": ws_id, "user_id": demo_uid,
        "role": "admin", "invited_by": None,
        "created_at": ts(-30), "updated_at": ts(-30),
        "joined_at": ts(-30),
    })
    for uid, offset in [(park_uid, -28), (lee_uid, -25), (choi_uid, -20)]:
        _insert(cur, "workspace_members", {
            "workspace_id": ws_id, "user_id": uid,
            "role": "member", "invited_by": demo_uid,
            "created_at": ts(offset),
            "updated_at": ts(offset),
            "joined_at": ts(offset),
        })
    print("  Created workspace + 4 members")

    # ---------------------------------------------------------------
    # Phase 2: Company Profiles + Project + Brands
    # ---------------------------------------------------------------
    print("\n[Phase 2] Creating company profiles, project, brands...")

    project_id = _insert(cur, "projects", {
        "name": "AI 검색 시장 분석 2026",
        "description": "한국 AI 검색 시장의 주요 플레이어 분석",
        "owner_id": demo_uid,
        "created_at": ts(-28),
        "updated_at": ts(-1),
    })

    cp_naver = _insert(cur, "company_profiles", {
        "name": "네이버", "industry": "IT/검색엔진",
        "description": "한국 최대 검색 포털 및 AI 기술 기업",
        "target_audience": "한국 인터넷 사용자, 20-50대",
        "main_products": "네이버 검색, Cue:, 네이버 쇼핑",
        "competitors": "구글코리아, 카카오, 다음",
        "unique_value": "한국어 AI 검색 기술력",
        "website_url": "https://www.naver.com",
        "project_id": project_id, "owner_id": demo_uid,
        "created_at": ts(-28), "updated_at": ts(-1),
        "is_active": 1,
    })
    cp_google = _insert(cur, "company_profiles", {
        "name": "구글코리아", "industry": "IT/검색엔진",
        "description": "글로벌 검색 엔진 구글의 한국 법인",
        "target_audience": "글로벌 정보 검색 사용자",
        "main_products": "Google 검색, AI Overview, YouTube",
        "competitors": "네이버, 카카오",
        "unique_value": "글로벌 AI 기술력, 멀티모달 검색",
        "website_url": "https://www.google.co.kr",
        "project_id": project_id, "owner_id": demo_uid,
        "created_at": ts(-28), "updated_at": ts(-1),
        "is_active": 1,
    })
    cp_kakao = _insert(cur, "company_profiles", {
        "name": "카카오", "industry": "IT/플랫폼",
        "description": "카카오톡 기반 종합 IT 플랫폼",
        "target_audience": "모바일 중심 사용자, MZ세대",
        "main_products": "카카오톡, 다음 검색, 카카오맵",
        "competitors": "네이버, 구글코리아",
        "unique_value": "메신저 플랫폼 기반 AI 검색 통합",
        "website_url": "https://www.kakaocorp.com",
        "project_id": project_id, "owner_id": demo_uid,
        "created_at": ts(-27), "updated_at": ts(-2),
        "is_active": 1,
    })
    cp_daum = _insert(cur, "company_profiles", {
        "name": "다음", "industry": "IT/포털",
        "description": "카카오 산하 포털 서비스",
        "target_audience": "뉴스 소비자, 30-60대",
        "main_products": "다음 뉴스, 다음 검색",
        "competitors": "네이버, 구글코리아",
        "unique_value": "뉴스 큐레이션 AI",
        "website_url": "https://www.daum.net",
        "project_id": project_id, "owner_id": demo_uid,
        "created_at": ts(-27), "updated_at": ts(-2),
        "is_active": 1,
    })
    all_cp_ids = [cp_naver, cp_google, cp_kakao, cp_daum]
    print(f"  Created {len(all_cp_ids)} company profiles")

    # Brands
    brand_naver = _insert(cur, "brands", {
        "name": "네이버",
        "aliases": json.dumps(
            ["Naver", "NAVER", "네이버검색", "naver.com"],
        ),
        "keywords": json.dumps(
            ["AI검색", "하이퍼클로바", "Cue:", "네이버AI"],
        ),
        "description": "한국 최대 검색 포털",
        "project_id": project_id,
        "created_at": ts(-28), "updated_at": ts(-1),
    })
    brand_google = _insert(cur, "brands", {
        "name": "구글",
        "aliases": json.dumps(
            ["Google", "구글코리아", "google.co.kr"],
        ),
        "keywords": json.dumps(
            ["Gemini", "AI Overview", "구글검색"],
        ),
        "description": "글로벌 검색 엔진",
        "project_id": project_id,
        "created_at": ts(-28), "updated_at": ts(-1),
    })
    brand_kakao = _insert(cur, "brands", {
        "name": "카카오",
        "aliases": json.dumps(
            ["Kakao", "카카오검색", "KoGPT"],
        ),
        "keywords": json.dumps(
            ["카카오톡", "AI챗봇", "카카오검색"],
        ),
        "description": "한국 메신저 기반 플랫폼",
        "project_id": project_id,
        "created_at": ts(-27), "updated_at": ts(-2),
    })
    brand_daum = _insert(cur, "brands", {
        "name": "다음",
        "aliases": json.dumps(
            ["Daum", "다음검색", "다음뉴스", "daum.net"],
        ),
        "keywords": json.dumps(["뉴스큐레이션", "다음카페"]),
        "description": "카카오 산하 포털",
        "project_id": project_id,
        "created_at": ts(-27), "updated_at": ts(-2),
    })
    brand_bing = _insert(cur, "brands", {
        "name": "빙",
        "aliases": json.dumps(
            ["Bing", "Microsoft Bing", "빙검색"],
        ),
        "keywords": json.dumps(
            ["Copilot", "Microsoft", "빙AI"],
        ),
        "description": "마이크로소프트 검색 엔진",
        "project_id": project_id,
        "created_at": ts(-26), "updated_at": ts(-3),
    })
    brand_id_map = {
        "네이버": brand_naver, "구글": brand_google,
        "카카오": brand_kakao, "다음": brand_daum,
        "빙": brand_bing,
    }
    print("  Created 5 brands")

    # ---------------------------------------------------------------
    # Phase 3: Campaigns
    # ---------------------------------------------------------------
    print("\n[Phase 3] Creating campaigns, clusters, queries...")

    camp1 = _insert(cur, "campaigns", {
        "workspace_id": ws_id, "name": "Q1 AI 검색 브랜드 분석",
        "description": "2026년 1분기 브랜드 인용 현황 분석",
        "owner_id": demo_uid,
        "schedule_interval_hours": 24,
        "schedule_enabled": 1,
        "schedule_next_run_at": ts(1),
        "status": "active",
        "created_at": ts(-21), "updated_at": ts(-1),
    })
    camp2 = _insert(cur, "campaigns", {
        "workspace_id": ws_id, "name": "경쟁사 비교 리포트",
        "description": "네이버 vs 구글 AI 검색 상세 비교",
        "owner_id": park_uid,
        "schedule_interval_hours": 168,
        "schedule_enabled": 0,
        "schedule_next_run_at": None,
        "status": "active",
        "created_at": ts(-14), "updated_at": ts(-2),
    })
    camp3 = _insert(cur, "campaigns", {
        "workspace_id": ws_id, "name": "테스트 캠페인",
        "description": "새로운 프롬프트 템플릿 테스트용",
        "owner_id": lee_uid,
        "schedule_interval_hours": 0,
        "schedule_enabled": 0,
        "schedule_next_run_at": None,
        "status": "paused",
        "created_at": ts(-7), "updated_at": ts(-5),
    })
    campaign_ids = [camp1, camp2, camp3]
    print(f"  Created {len(campaign_ids)} campaigns")

    # Campaign Companies
    cc_count = 0
    for cid in campaign_ids:
        for order, cpid in enumerate(all_cp_ids):
            is_target = 1 if cpid == cp_naver else 0
            _insert(cur, "campaign_companies", {
                "campaign_id": cid,
                "company_profile_id": cpid,
                "is_target_brand": is_target,
                "display_order": order,
                "added_by": demo_uid,
                "notes": None,
                "created_at": ts(-20),
                "updated_at": ts(-1),
            })
            cc_count += 1
    print(f"  Created {cc_count} campaign-company mappings")

    # Intent Clusters (8 per campaign)
    cluster_defs = [
        ("브랜드 인지도", "AI 검색 브랜드 인지도 분석"),
        ("기능 비교", "AI 검색 서비스 기능 비교"),
        ("사용자 경험", "AI 검색 사용자 경험 평가"),
        ("가격 및 요금제", "AI 검색 가격 정책 분석"),
        ("기술 혁신", "AI 검색 기술 혁신 추세"),
        ("시장 점유율", "AI 검색 시장 점유율 현황"),
        ("고객 지원", "AI 검색 고객 지원 품질"),
        ("데이터 보안", "AI 검색 데이터 보안 및 개인정보 보호"),
    ]
    all_cluster_ids: dict[int, list[int]] = {}
    for cid in campaign_ids:
        clist: list[int] = []
        for order, (cname, cdesc) in enumerate(cluster_defs):
            clid = _insert(cur, "intent_clusters", {
                "name": cname, "description": cdesc,
                "campaign_id": cid, "order_index": order,
                "created_at": ts(-20), "updated_at": ts(-1),
            })
            clist.append(clid)
        all_cluster_ids[cid] = clist
    print(f"  Created {len(campaign_ids) * 8} intent clusters")

    # Query Definitions (2 per cluster) + Versions
    query_texts_by_cluster = {
        "브랜드 인지도": [
            ("한국에서 가장 인지도 높은 AI 검색은?", "anchor"),
            ("AI 검색 브랜드별 인지도 순위", "exploration"),
        ],
        "기능 비교": [
            ("네이버 vs 구글 AI 검색 차이점?", "anchor"),
            ("한국 AI 검색 서비스 기능 비교", "exploration"),
        ],
        "사용자 경험": [
            ("AI 검색 만족도가 가장 높은 서비스?", "anchor"),
            ("AI 검색 사용자 경험 평가", "exploration"),
        ],
        "가격 및 요금제": [
            ("카카오 AI 검색 가격 정책은?", "anchor"),
            ("AI 검색 서비스 요금제 비교", "exploration"),
        ],
        "기술 혁신": [
            ("네이버 AI 검색 정확도는 어떤가요?", "anchor"),
            ("AI 검색 기술 혁신 트렌드 분석", "exploration"),
        ],
        "시장 점유율": [
            ("구글 vs 네이버 검색 품질 비교", "anchor"),
            ("한국 AI 검색 시장 점유율 현황", "exploration"),
        ],
        "고객 지원": [
            ("네이버 AI 검색 고객 지원 품질은?", "anchor"),
            ("AI 검색 고객 서비스 만족도 비교", "exploration"),
        ],
        "데이터 보안": [
            ("AI 검색 개인정보 보호 정책 비교", "anchor"),
            ("네이버 AI 검색 데이터 보안 수준은?", "exploration"),
        ],
    }

    all_qd_ids: list[int] = []
    all_qv_ids: list[int] = []

    for cid in campaign_ids:
        for ci, (cname, _) in enumerate(cluster_defs):
            cluster_id = all_cluster_ids[cid][ci]
            for qtext, qtype in query_texts_by_cluster[cname]:
                num_ver = random.choice([1, 2, 3])
                qd_id = _insert(cur, "query_definitions", {
                    "campaign_id": cid,
                    "intent_cluster_id": cluster_id,
                    "query_type": qtype,
                    "current_version": num_ver,
                    "is_active": 1, "is_retired": 0,
                    "created_by": demo_uid,
                    "created_at": ts(-19),
                    "updated_at": ts(-1),
                })
                all_qd_ids.append(qd_id)

                for v in range(1, num_ver + 1):
                    is_cur = 1 if v == num_ver else 0
                    vtxt = (
                        qtext if v == 1
                        else f"{qtext} (v{v} 개선)"
                    )
                    persona = (
                        "consumer"
                        if random.random() < 0.7
                        else "investor"
                    )
                    reason = (
                        None if v == 1
                        else "질문 명확성 개선"
                    )
                    eff_from = ts(-19 + v)
                    eff_until = (
                        None if is_cur
                        else ts(-19 + v + 1)
                    )
                    qv_id = _insert(cur, "query_versions", {
                        "query_definition_id": qd_id,
                        "version": v, "text": vtxt,
                        "persona_type": persona,
                        "change_reason": reason,
                        "changed_by": demo_uid,
                        "is_current": is_cur,
                        "effective_from": eff_from,
                        "effective_until": eff_until,
                        "created_at": ts(-19 + v),
                        "updated_at": ts(-1),
                    })
                    all_qv_ids.append(qv_id)

    print(
        f"  Created {len(all_qd_ids)} query definitions, "
        f"{len(all_qv_ids)} query versions",
    )

    # Prompt Templates (1 per campaign)
    prompt_text = (
        "다음 질문에 대해 한국 AI 검색 시장의 "
        "전문가로서 답변해 주세요.\n\n"
        "질문: {{query}}\n\n"
        "답변 시 다음을 포함해 주세요:\n"
        "1. 관련 브랜드/서비스 구체적 언급\n"
        "2. 시장 점유율 등 정량적 데이터\n"
        "3. 각 서비스의 강점과 약점\n"
        "4. 최근 트렌드와 전망\n\n"
        "500자 이상 상세하게 작성해 주세요."
    )
    prompt_ids: list[int] = []
    for cid in campaign_ids:
        pt_id = _insert(cur, "prompt_templates", {
            "campaign_id": cid, "version": 1,
            "template_text": prompt_text,
            "output_schema_version": "1.0",
            "change_reason": "초기 생성",
            "changed_by": demo_uid, "is_current": 1,
            "created_at": ts(-19), "updated_at": ts(-1),
        })
        prompt_ids.append(pt_id)
    print(f"  Created {len(prompt_ids)} prompt templates")

    # ---------------------------------------------------------------
    # Phase 4: Campaign Runs + Responses + Citations
    # ---------------------------------------------------------------
    print("\n[Phase 4] Creating runs, responses, citations...")

    run_configs = [
        (camp1, 1, "manual", "completed", -18, -17.5),
        (camp1, 2, "scheduled", "completed", -14, -13.5),
        (camp1, 3, "scheduled", "completed", -10, -9.5),
        (camp1, 4, "scheduled", "completed", -6, -5.5),
        (camp1, 5, "scheduled", "executing", -1, None),
        (camp2, 1, "manual", "completed", -12, -11.5),
        (camp2, 2, "manual", "completed", -8, -7.5),
        (camp2, 3, "manual", "completed", -4, -3.5),
    ]

    all_run_ids: list[int] = []
    all_resp_ids: list[int] = []
    all_cit_ids: list[int] = []
    total_resp = 0
    total_cit = 0

    for (
        cid, run_num, trigger, status,
        start_off, end_off,
    ) in run_configs:
        prompt_id = (
            prompt_ids[0] if cid == camp1 else prompt_ids[1]
        )
        is_done = status == "completed"
        run_id = _insert(cur, "campaign_runs", {
            "campaign_id": cid,
            "run_number": run_num,
            "trigger_type": trigger,
            "llm_providers": json.dumps(
                ["openai", "gemini"],
            ),
            "status": status,
            "prompt_version_id": prompt_id,
            "total_queries": 10,
            "completed_queries": 10 if is_done else 3,
            "failed_queries": 0,
            "started_at": ts(start_off),
            "completed_at": (
                ts(end_off) if end_off else None
            ),
            "error_message": None,
            "created_at": ts(start_off),
            "updated_at": ts(
                end_off if end_off else start_off + 0.1,
            ),
        })
        all_run_ids.append(run_id)

        if not is_done:
            continue

        # 10 responses per run: 5 openai + 5 gemini
        providers = (
            [("openai", "gpt-5-nano")] * 5
            + [("gemini", "gemini-2.5-flash")] * 5
        )
        random.shuffle(providers)

        # Get query version IDs for this campaign
        cur.execute(
            "SELECT qv.id FROM query_versions qv "
            "JOIN query_definitions qd "
            "ON qv.query_definition_id = qd.id "
            "WHERE qd.campaign_id = ? "
            "AND qv.is_current = 1 LIMIT 10",
            (cid,),
        )
        avail_qvs = [r[0] for r in cur.fetchall()]

        for ri, (prov, model) in enumerate(providers):
            tmpl_i = (
                (run_num * 3 + ri) % len(RESPONSE_TEMPLATES)
            )
            content = RESPONSE_TEMPLATES[tmpl_i]
            if ri % 3 == 1:
                content += " 이러한 추세는 지속될 전망입니다."
            elif ri % 3 == 2:
                content = "최근 조사에 따르면, " + content

            tokens = random.randint(500, 2000)
            latency = round(random.uniform(800, 3000), 1)
            words = len(content.split())
            n_cits = random.randint(2, 4)
            qv_ref = (
                avail_qvs[ri % len(avail_qvs)]
                if avail_qvs else 1
            )
            rhash = str(
                hash(content + str(run_num) + str(ri)),
            )[:16]

            resp_id = _insert(cur, "run_responses", {
                "campaign_run_id": run_id,
                "query_version_id": qv_ref,
                "llm_provider": prov,
                "llm_model": model,
                "llm_model_version": "latest",
                "content": content,
                "tokens_used": tokens,
                "latency_ms": latency,
                "raw_response_json": None,
                "error_message": None,
                "response_hash": rhash,
                "word_count": words,
                "citation_count": n_cits,
                "created_at": ts(
                    start_off + 0.01 * ri,
                ),
                "updated_at": ts(
                    start_off + 0.01 * ri,
                ),
            })
            all_resp_ids.append(resp_id)
            total_resp += 1

            for ci in range(n_cits):
                brand = pick_brand()
                is_tgt = 1 if brand == "네이버" else 0
                span, pos = find_brand_span(
                    content, brand,
                )
                conf = round(random.uniform(0.85, 0.99), 3)
                method = random.choice(["regex", "ml"])
                ctx_s = max(0, pos - 50)
                ctx_e = min(
                    len(content), pos + len(brand) + 50,
                )
                ctx_before = (
                    content[ctx_s:pos] if pos > 0 else ""
                )
                ctx_after = (
                    content[pos + len(brand):ctx_e]
                    if pos > 0 else ""
                )

                cit_id = _insert(cur, "run_citations", {
                    "run_response_id": resp_id,
                    "cited_brand": brand,
                    "citation_url": None,
                    "citation_domain": None,
                    "citation_span": span,
                    "context_before": ctx_before,
                    "context_after": ctx_after,
                    "position_in_response": ci,
                    "is_target_brand": is_tgt,
                    "confidence_score": conf,
                    "extraction_method": method,
                    "is_verified": 0,
                    "verified_by": None,
                    "verified_at": None,
                    "created_at": ts(
                        start_off + 0.01 * ri,
                    ),
                    "updated_at": ts(
                        start_off + 0.01 * ri,
                    ),
                })
                all_cit_ids.append(cit_id)
                total_cit += 1

    print(f"  Created {len(all_run_ids)} campaign runs")
    print(f"  Created {total_resp} run responses")
    print(f"  Created {total_cit} run citations")

    # ---------------------------------------------------------------
    # Phase 5: Gallery Data
    # ---------------------------------------------------------------
    print("\n[Phase 5] Creating gallery data...")

    # Response Labels (~30)
    label_keys_map = {
        "flag": [
            "hallucination", "outdated_info",
            "missing_brand",
        ],
        "quality": ["high", "medium", "low"],
        "category": [
            "market_analysis", "tech_comparison",
        ],
        "custom": ["needs_review", "highlighted"],
    }
    label_types = list(label_keys_map.keys())
    severities = ["info", "warning", "critical"]
    label_ct = 0

    for i in range(min(30, len(all_resp_ids))):
        rid = all_resp_ids[i % len(all_resp_ids)]
        lt = random.choice(label_types)
        lk = random.choice(label_keys_map[lt])
        sev = random.choice(severities)
        creator = random.choice(
            [demo_uid, park_uid, lee_uid],
        )
        resolved = (
            ts(-random.randint(1, 10))
            if random.random() < 0.3 else None
        )
        _insert(cur, "response_labels", {
            "workspace_id": ws_id,
            "run_response_id": rid,
            "label_type": lt,
            "label_key": lk,
            "label_value": lk,
            "severity": sev,
            "created_by": creator,
            "resolved_at": resolved,
            "resolved_by": creator if resolved else None,
            "created_at": ts(-random.randint(1, 15)),
            "updated_at": ts(-1),
        })
        label_ct += 1
    print(f"  Created {label_ct} response labels")

    # Citation Reviews (~20)
    rev_types = [
        "correct", "false_positive",
        "false_negative", "uncertain",
    ]
    rev_weights = [0.5, 0.2, 0.1, 0.2]
    rev_comments = {
        "correct": "정확한 인용입니다.",
        "false_positive": "직접 인용이 아닙니다.",
        "false_negative": "추가 인용이 누락되었습니다.",
        "uncertain": "추가 검토 필요.",
    }
    rev_ct = 0
    for i in range(min(20, len(all_cit_ids))):
        cid = all_cit_ids[i]
        rt = random.choices(
            rev_types, weights=rev_weights, k=1,
        )[0]
        creator = random.choice(
            [demo_uid, park_uid, lee_uid],
        )
        _insert(cur, "citation_reviews", {
            "run_citation_id": cid,
            "review_type": rt,
            "reviewer_comment": rev_comments[rt],
            "created_by": creator,
            "created_at": ts(-random.randint(1, 10)),
            "updated_at": ts(-1),
        })
        rev_ct += 1
    print(f"  Created {rev_ct} citation reviews")

    # Comparison Snapshots (3)
    snap_cfgs = [
        (
            "OpenAI vs Gemini 인용률 비교",
            "llm_vs_llm",
            json.dumps({
                "providers": ["openai", "gemini"],
                "metric": "citation_share",
                "period": "Q1 2026",
            }),
        ),
        (
            "1월 vs 2월 브랜드 인용 추이",
            "date_vs_date",
            json.dumps({
                "date_from": "2026-01-01",
                "date_to": "2026-02-01",
                "brands": ["네이버", "구글"],
            }),
        ),
        (
            "프롬프트 v1 vs v2 비교",
            "version_vs_version",
            json.dumps({
                "prompt_v1": 1, "prompt_v2": 2,
                "campaign_id": camp1,
            }),
        ),
    ]
    for sname, stype, scfg in snap_cfgs:
        _insert(cur, "comparison_snapshots", {
            "workspace_id": ws_id,
            "name": sname,
            "comparison_type": stype,
            "config": scfg,
            "notes": "데모 비교 스냅샷",
            "created_by": demo_uid,
            "created_at": ts(-random.randint(1, 10)),
            "updated_at": ts(-1),
        })
    print(f"  Created {len(snap_cfgs)} comparison snapshots")

    # Operation Logs (10) - realistic operations
    realistic_ops = [
        {
            "type": "campaign_status_change",
            "target_type": "campaign",
            "target_id": str(camp1),
            "status": "approved",
            "payload": {
                "type": "campaign_status_change",
                "action": "캠페인 상태 변경",
                "detail": "Q1 AI 검색 브랜드 분석: active → paused",
                "reason": "프롬프트 템플릿 업데이트를 위한 일시 중지",
            },
        },
        {
            "type": "prompt_update",
            "target_type": "prompt_template",
            "target_id": str(prompt_ids[0]),
            "status": "approved",
            "payload": {
                "type": "prompt_update",
                "action": "프롬프트 템플릿 수정",
                "detail": "v1.0 → v2.0: 인용 정확도 개선을 위한 프롬프트 재설계",
                "changed_by": "김지현",
            },
        },
        {
            "type": "query_add",
            "target_type": "intent_cluster",
            "target_id": str(all_cluster_ids[camp1][0]),
            "status": "approved",
            "payload": {
                "type": "query_add",
                "action": "쿼리 추가",
                "detail": "인텐트 클러스터 '브랜드 인지도'에 신규 쿼리 3개 추가",
                "queries": ["네이버 AI 검색 신뢰도", "구글 검색 vs 네이버 검색"],
            },
        },
        {
            "type": "brand_update",
            "target_type": "brand",
            "target_id": str(brand_bing),
            "status": "approved",
            "payload": {
                "type": "brand_update",
                "action": "경쟁사 브랜드 추가",
                "detail": "빙(Bing)을 경쟁사 목록에 추가",
                "brand": "빙",
            },
        },
        {
            "type": "run_trigger",
            "target_type": "campaign_run",
            "target_id": str(all_run_ids[4]) if len(all_run_ids) > 4 else "5",
            "status": "approved",
            "payload": {
                "type": "run_trigger",
                "action": "수동 실행 트리거",
                "detail": "Run #5 수동 실행 - 프롬프트 변경 후 검증 목적",
                "run_id": 5,
            },
        },
        {
            "type": "citation_review",
            "target_type": "campaign_run",
            "target_id": str(all_run_ids[3]) if len(all_run_ids) > 3 else "4",
            "status": "pending",
            "payload": {
                "type": "citation_review",
                "action": "인용 리뷰 일괄 처리",
                "detail": "Run #4 응답 20개에 대한 인용 정확도 리뷰 완료",
                "reviewed_count": 20,
            },
        },
        {
            "type": "export",
            "target_type": "campaign",
            "target_id": str(camp1),
            "status": "pending",
            "payload": {
                "type": "export_request",
                "action": "데이터 내보내기 요청",
                "detail": "Q1 AI 검색 브랜드 분석 - 전체 인용 데이터 CSV 내보내기",
                "format": "csv",
            },
        },
        {
            "type": "label_action",
            "target_type": "response_label",
            "target_id": None,
            "status": "pending",
            "payload": {
                "type": "label_batch",
                "action": "응답 라벨 일괄 적용",
                "detail": "갤러리 응답 15개에 'high_quality' 라벨 적용",
                "count": 15,
            },
        },
        {
            "type": "schedule_change",
            "target_type": "campaign",
            "target_id": str(camp1),
            "status": "rejected",
            "reject_reason": "주 3회 실행 시 데이터 갭 발생 우려",
            "payload": {
                "type": "schedule_change",
                "action": "스케줄 설정 변경",
                "detail": "일일 실행 → 주 3회(월/수/금) 실행으로 변경",
                "old_schedule": "daily",
                "new_schedule": "3x/week",
            },
        },
        {
            "type": "archive",
            "target_type": "campaign",
            "target_id": str(camp3),
            "status": "rejected",
            "reject_reason": "히스토리 데이터 보존 필요",
            "payload": {
                "type": "campaign_delete",
                "action": "캠페인 삭제 요청",
                "detail": "테스트 캠페인 삭제 요청 - 더 이상 사용하지 않음",
                "campaign": "테스트 캠페인",
            },
        },
    ]

    for i, op_def in enumerate(realistic_ops):
        reviewer = (
            park_uid if op_def["status"] != "pending" else None
        )
        rev_at = (
            ts(-random.randint(1, 5))
            if reviewer else None
        )
        rev_comment = (
            "승인합니다." if op_def["status"] == "approved"
            else (
                op_def.get("reject_reason")
                if op_def["status"] == "rejected"
                else None
            )
        )
        _insert(cur, "operation_logs", {
            "workspace_id": ws_id,
            "operation_type": op_def["type"],
            "status": op_def["status"],
            "target_type": op_def["target_type"],
            "target_id": op_def["target_id"],
            "payload": json.dumps(op_def["payload"]),
            "created_by": random.choice(
                [demo_uid, park_uid, lee_uid],
            ),
            "reviewed_by": reviewer,
            "reviewed_at": rev_at,
            "review_comment": rev_comment,
            "created_at": ts(-random.randint(1, 15)),
            "updated_at": ts(-1),
        })
    print(f"  Created {len(realistic_ops)} operation logs")

    # Campaign Annotations (5)
    annot_data = [
        ("프롬프트 템플릿 v1 적용", "초기 프롬프트 설정"),
        ("경쟁사 전략 업데이트", "구글 AI Overview 반영"),
        ("인용 추출 개선", "정확도 92%→95% 향상"),
        ("분석 대상 확장", "빙 검색 추가"),
        ("주간 리포트 자동화", "월요일 자동 생성"),
    ]
    for idx, (title, desc) in enumerate(annot_data):
        _insert(cur, "campaign_annotations", {
            "campaign_id": camp1,
            "date": ts(-18 + idx * 3)[:10],
            "title": title,
            "description": desc,
            "annotation_type": "manual",
            "created_by_id": demo_uid,
            "created_at": ts(-18 + idx * 3),
            "updated_at": ts(-1),
        })
    print(f"  Created {len(annot_data)} annotations")

    # ---------------------------------------------------------------
    # Phase 6: Pipeline Data
    # ---------------------------------------------------------------
    print("\n[Phase 6] Creating pipeline data...")

    qs1 = _insert(cur, "query_sets", {
        "name": "AI 검색 분석 세트",
        "description": "한국 AI 검색 시장 분석용 쿼리 세트",
        "category_count": 3,
        "queries_per_category": 5,
        "company_profile_id": cp_naver,
        "owner_id": demo_uid,
        "created_at": ts(-15), "updated_at": ts(-1),
    })
    qs2 = _insert(cur, "query_sets", {
        "name": "경쟁사 벤치마크 세트",
        "description": "경쟁사 대비 분석용 쿼리 세트",
        "category_count": 3,
        "queries_per_category": 5,
        "company_profile_id": cp_google,
        "owner_id": demo_uid,
        "created_at": ts(-12), "updated_at": ts(-2),
    })

    pipeline_cat_defs = [
        ("시장 점유율 분석", "점유율 관련 쿼리", "consumer"),
        ("기술 비교 분석", "기술력 비교 쿼리", "investor"),
        ("사용자 만족도 조사", "사용자 경험 쿼리", "consumer"),
    ]

    all_pc_ids: list[int] = []
    all_eq_ids: list[int] = []

    for qs_id in [qs1, qs2]:
        cp_ref = cp_naver if qs_id == qs1 else cp_google
        for order, (pn, pd, persona) in enumerate(
            pipeline_cat_defs,
        ):
            pc_id = _insert(cur, "pipeline_categories", {
                "name": pn, "description": pd,
                "persona_type": persona,
                "order_index": order,
                "query_set_id": qs_id,
                "company_profile_id": cp_ref,
                "created_at": ts(-15),
                "updated_at": ts(-1),
                "llm_provider": random.choice(
                    ["openai", "gemini"],
                ),
            })
            all_pc_ids.append(pc_id)

            brands_pick = ["네이버", "구글", "카카오"]
            attrs = ["장점", "단점", "특징", "전망", "경쟁력"]
            for ei in range(5):
                eq_text = (
                    f"한국 AI 검색 {pn} 질문 "
                    f"{ei+1}: "
                    f"{random.choice(brands_pick)} "
                    f"서비스의 "
                    f"{random.choice(attrs)}은?"
                )
                eq_id = _insert(cur, "expanded_queries", {
                    "text": eq_text,
                    "order_index": ei,
                    "status": "completed",
                    "category_id": pc_id,
                    "created_at": ts(-14),
                    "updated_at": ts(-1),
                })
                all_eq_ids.append(eq_id)

    print(
        f"  Created 2 query sets, {len(all_pc_ids)} categories, "
        f"{len(all_eq_ids)} expanded queries",
    )

    # Pipeline Jobs (3: 2 completed, 1 failed)
    pj1 = _insert(cur, "pipeline_jobs", {
        "status": "completed",
        "llm_providers": json.dumps(
            ["openai", "gemini"],
        ),
        "total_queries": 30, "completed_queries": 30,
        "failed_queries": 0,
        "started_at": ts(-14),
        "completed_at": ts(-13.5),
        "error_message": None,
        "query_set_id": qs1,
        "company_profile_id": cp_naver,
        "owner_id": demo_uid,
        "created_at": ts(-14), "updated_at": ts(-13.5),
        "mode": "full",
    })
    pj2 = _insert(cur, "pipeline_jobs", {
        "status": "completed",
        "llm_providers": json.dumps(["openai"]),
        "total_queries": 15, "completed_queries": 15,
        "failed_queries": 0,
        "started_at": ts(-10),
        "completed_at": ts(-9.8),
        "error_message": None,
        "query_set_id": qs2,
        "company_profile_id": cp_google,
        "owner_id": demo_uid,
        "created_at": ts(-10), "updated_at": ts(-9.8),
        "mode": "full",
    })
    _insert(cur, "pipeline_jobs", {
        "status": "failed",
        "llm_providers": json.dumps(["gemini"]),
        "total_queries": 15, "completed_queries": 8,
        "failed_queries": 7,
        "started_at": ts(-5),
        "completed_at": ts(-4.9),
        "error_message": "Rate limit exceeded",
        "query_set_id": qs1,
        "company_profile_id": cp_naver,
        "owner_id": park_uid,
        "created_at": ts(-5), "updated_at": ts(-4.9),
        "mode": "full",
    })
    print("  Created 3 pipeline jobs")

    # Raw LLM Responses (2 per expanded query)
    raw_ct = 0
    for eq_id in all_eq_ids:
        for prov, model in [
            ("openai", "gpt-5-nano"),
            ("gemini", "gemini-2.5-flash"),
        ]:
            ti = raw_ct % len(RESPONSE_TEMPLATES)
            content = RESPONSE_TEMPLATES[ti]
            pj_ref = pj1 if raw_ct < 30 else pj2
            _insert(cur, "raw_llm_responses", {
                "content": content,
                "llm_provider": prov,
                "llm_model": model,
                "tokens_used": random.randint(400, 1800),
                "latency_ms": random.randint(600, 2500),
                "raw_response_json": None,
                "error_message": None,
                "retry_count": 0,
                "query_id": eq_id,
                "pipeline_job_id": pj_ref,
                "created_at": ts(-14 + raw_ct * 0.01),
                "updated_at": ts(-1),
            })
            raw_ct += 1
    print(f"  Created {raw_ct} raw LLM responses")

    # Schedule Config
    _insert(cur, "schedule_configs", {
        "interval_minutes": 1440,
        "is_active": 1,
        "last_run_at": ts(-1),
        "next_run_at": ts(0, offset_hours=24),
        "llm_providers": json.dumps(
            ["openai", "gemini"],
        ),
        "failure_count": 0,
        "query_set_id": qs1,
        "owner_id": demo_uid,
        "created_at": ts(-15), "updated_at": ts(-1),
    })
    print("  Created 1 schedule config")

    # ---------------------------------------------------------------
    # Phase 7: Insights
    # ---------------------------------------------------------------
    print("\n[Phase 7] Creating insights...")

    insights = [
        (
            "provider_gap", "warning",
            "OpenAI-Gemini 인용률 격차 감지",
            "OpenAI와 Gemini 간 네이버 인용률 차이가 "
            "15%p로 측정되었습니다.",
            json.dumps({
                "openai_rate": 0.42,
                "gemini_rate": 0.27,
                "gap": 0.15,
            }),
        ),
        (
            "citation_drop", "critical",
            "네이버 인용률 하락 경고",
            "네이버 인용률이 전주 대비 8% 하락했습니다.",
            json.dumps({
                "current_rate": 0.35,
                "previous_rate": 0.43,
                "drop": 0.08,
            }),
        ),
        (
            "positive_trend", "info",
            "카카오 인용률 상승 추세",
            "카카오 인용률이 3주 연속 상승세입니다.",
            json.dumps({
                "week1": 0.12, "week2": 0.15,
                "week3": 0.18,
            }),
        ),
        (
            "query_performance", "info",
            "앵커 쿼리 성능 분석",
            "앵커 쿼리의 인용 추출률이 탐색 쿼리 "
            "대비 23% 높습니다.",
            json.dumps({
                "anchor_avg": 3.2,
                "exploration_avg": 2.6,
            }),
        ),
        (
            "anomaly_detected", "warning",
            "비정상 응답 패턴 감지",
            "Run #4에서 토큰 사용량이 평균 대비 "
            "2배 이상 높게 나타났습니다.",
            json.dumps({
                "avg_tokens": 1200,
                "anomaly_tokens": 2800,
            }),
        ),
    ]
    for itype, isev, ititle, idesc, idata in insights:
        _insert(cur, "insights", {
            "workspace_id": ws_id,
            "campaign_id": camp1,
            "insight_type": itype,
            "severity": isev,
            "title": ititle,
            "description": idesc,
            "data_json": idata,
            "is_dismissed": 0,
            "created_at": ts(-random.randint(1, 10)),
            "updated_at": ts(-1),
        })
    print(f"  Created {len(insights)} insights")

    # ---------------------------------------------------------------
    # Phase 8: Legacy Data
    # ---------------------------------------------------------------
    print("\n[Phase 8] Creating legacy data...")

    legacy_qtexts = [
        "네이버 AI 검색의 시장 점유율은?",
        "구글코리아 vs 네이버 AI 검색 비교",
        "카카오 AI 검색 서비스 현황",
        "한국 AI 검색 시장 전망 2026",
        "네이버 하이퍼클로바X 성능 분석",
        "AI 검색 광고 시장 규모",
        "다음 뉴스 AI 큐레이션 평가",
        "빙 Copilot 한국 시장 진출",
        "AI 검색 사용자 만족도 조사",
        "네이버 Cue: 서비스 리뷰",
    ]
    leg_statuses = (
        ["completed"] * 7 + ["processing"] * 2
        + ["pending"]
    )

    legacy_qids: list[int] = []
    for i, (qt, qs) in enumerate(
        zip(legacy_qtexts, leg_statuses),
    ):
        lqid = _insert(cur, "queries", {
            "text": qt, "status": qs,
            "project_id": project_id,
            "created_at": ts(-25 + i),
            "updated_at": ts(-1),
        })
        legacy_qids.append(lqid)
    print(f"  Created {len(legacy_qids)} legacy queries")

    # Legacy Responses (3 per query)
    leg_provs = [
        ("openai", "gpt-5-nano"),
        ("gemini", "gemini-2.5-flash"),
        ("openai", "gpt-5-nano"),
    ]
    legacy_rids: list[int] = []

    for qi, lqid in enumerate(legacy_qids):
        for pi, (prov, mod) in enumerate(leg_provs):
            ti = (qi * 3 + pi) % len(RESPONSE_TEMPLATES)
            content = RESPONSE_TEMPLATES[ti]
            geo_score = round(random.uniform(60, 95), 1)
            if geo_score >= 90:
                grade = "S"
            elif geo_score >= 80:
                grade = "A"
            elif geo_score >= 70:
                grade = "B"
            elif geo_score >= 60:
                grade = "C"
            else:
                grade = "D"
            sentiment = round(random.uniform(0.3, 0.9), 2)
            if sentiment > 0.6:
                sent_label = "positive"
            elif sentiment > 0.4:
                sent_label = "neutral"
            else:
                sent_label = "negative"

            trig_opts = [
                "brand_mention", "market_data",
                "comparison", "recommendation",
                "feature_highlight",
            ]
            triggers = random.sample(
                trig_opts, k=random.randint(2, 4),
            )

            lrid = _insert(cur, "responses", {
                "content": content,
                "llm_provider": prov,
                "llm_model": mod,
                "sentiment_score": sentiment,
                "sentiment_label": sent_label,
                "context_type": "market_analysis",
                "geo_score": geo_score,
                "geo_grade": grade,
                "geo_triggers": json.dumps(triggers),
                "query_id": lqid,
                "created_at": ts(-25 + qi),
                "updated_at": ts(-1),
            })
            legacy_rids.append(lrid)
    print(f"  Created {len(legacy_rids)} legacy responses")

    # Legacy Citations (2 per response)
    match_types = ["exact", "alias", "fuzzy", "keyword"]
    leg_cit_ct = 0
    for lrid in legacy_rids:
        cur.execute(
            "SELECT content FROM responses WHERE id = ?",
            (lrid,),
        )
        row = cur.fetchone()
        content = row[0] if row else ""

        for _ in range(2):
            brand = pick_brand()
            bid = brand_id_map.get(brand, brand_naver)
            idx = content.find(brand)
            if idx == -1:
                idx = 0
            end_idx = idx + len(brand)
            sp_start = max(0, idx - 20)
            sp_end = min(len(content), end_idx + 30)
            matched = content[sp_start:sp_end][:500]

            _insert(cur, "citations", {
                "matched_text": matched,
                "match_type": random.choice(match_types),
                "confidence": round(
                    random.uniform(0.75, 0.99), 3,
                ),
                "position_start": idx,
                "position_end": end_idx,
                "brand_id": bid,
                "response_id": lrid,
                "created_at": ts(-20),
                "updated_at": ts(-1),
            })
            leg_cit_ct += 1
    print(f"  Created {leg_cit_ct} legacy citations")

    # Generated Queries (10 per company profile, 3 profiles)
    gq_cats = ["introductory", "comparative", "critical"]
    gq_sts = [
        "generated", "edited", "selected", "excluded",
    ]
    gq_templates = {
        cp_naver: [
            "네이버 AI 검색의 주요 특징은?",
            "네이버 하이퍼클로바X 한국어 능력은?",
            "네이버 Cue: 사용자 평가는?",
            "네이버 AI vs 기존 검색 차이점",
            "네이버 AI 검색 광고 전략",
            "네이버 AI 검색의 시장 영향",
            "네이버 검색 AI 활용 현황",
            "네이버 AI 검색 개인정보 보호",
            "네이버 AI 검색 모바일 최적화",
            "네이버 AI 검색 향후 로드맵",
        ],
        cp_google: [
            "구글 AI Overview 한국어 지원 현황",
            "구글 Gemini 검색 정확도 분석",
            "구글 vs 네이버 AI 검색 비교",
            "구글의 한국 AI 검색 전략",
            "구글 AI 검색 멀티모달 평가",
            "구글 로컬 콘텐츠 AI 처리",
            "구글 AI 검색 광고 ROI 분석",
            "구글 Circle to Search 한국 도입",
            "구글 AI 검색 학술 정보 정확도",
            "구글 AI 검색 시장 점유율 추이",
        ],
        cp_kakao: [
            "카카오 KoGPT 검색 적용 현황",
            "카카오톡 AI 검색 통합 분석",
            "카카오 vs 네이버 AI 검색 비교",
            "카카오 대화형 AI 검색 전략",
            "다음 검색과 카카오 AI 시너지",
            "카카오 AI 검색 쇼핑 연계",
            "카카오 AI 검색 모바일 경험",
            "카카오 플랫폼 AI 검색 통합",
            "카카오 AI 검색 소셜 데이터 활용",
            "카카오 AI 검색 경쟁력 분석",
        ],
    }

    gq_ct = 0
    for cpid, texts in gq_templates.items():
        for i, text in enumerate(texts):
            cat = gq_cats[i % 3]
            status = gq_sts[i % 4]
            is_sel = 1 if status == "selected" else 0
            orig = text if status != "edited" else None
            _insert(cur, "generated_queries", {
                "text": text,
                "order_index": i,
                "category": cat,
                "status": status,
                "is_selected": is_sel,
                "original_text": orig,
                "company_profile_id": cpid,
                "created_at": ts(-20),
                "updated_at": ts(-1),
            })
            gq_ct += 1
    print(f"  Created {gq_ct} generated queries")

    # ---------------------------------------------------------------
    # Commit & Summary
    # ---------------------------------------------------------------
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")

    print("\n" + "=" * 60)
    print("  SEED COMPLETE - Summary")
    print("=" * 60)

    tables = [
        "users", "workspaces", "workspace_members",
        "company_profiles", "projects", "brands",
        "campaigns", "campaign_companies",
        "intent_clusters", "query_definitions",
        "query_versions", "prompt_templates",
        "campaign_runs", "run_responses", "run_citations",
        "response_labels", "citation_reviews",
        "comparison_snapshots", "operation_logs",
        "campaign_annotations",
        "query_sets", "pipeline_categories",
        "expanded_queries", "pipeline_jobs",
        "raw_llm_responses", "schedule_configs",
        "insights",
        "queries", "responses", "citations",
        "generated_queries",
    ]

    print(f"\n  {'Table':<30} {'Count':>8}")
    print(f"  {'-'*30} {'-'*8}")
    total = 0
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        count = cur.fetchone()[0]
        total += count
        print(f"  {table:<30} {count:>8}")

    print(f"  {'-'*30} {'-'*8}")
    print(f"  {'TOTAL':<30} {total:>8}")
    print(f"\n  Demo login: {DEMO_EMAIL} / Demo1234!")
    print("=" * 60)

    conn.close()


def _clean_demo_data(
    cur, demo_id: int, ws_id: int | None,
    member_ids: list[int],
) -> None:
    """Delete all data owned by the demo user."""
    # Find campaigns
    camp_ids: list[int] = []
    if ws_id:
        cur.execute(
            "SELECT id FROM campaigns "
            "WHERE workspace_id = ?", (ws_id,),
        )
        camp_ids = [r[0] for r in cur.fetchall()]

    # Find runs
    run_ids: list[int] = []
    for cid in camp_ids:
        cur.execute(
            "SELECT id FROM campaign_runs "
            "WHERE campaign_id = ?", (cid,),
        )
        run_ids.extend(r[0] for r in cur.fetchall())

    # Find run responses
    resp_ids: list[int] = []
    for rid in run_ids:
        cur.execute(
            "SELECT id FROM run_responses "
            "WHERE campaign_run_id = ?", (rid,),
        )
        resp_ids.extend(r[0] for r in cur.fetchall())

    # Delete citations + reviews for responses
    for rid in resp_ids:
        cur.execute(
            "DELETE FROM citation_reviews "
            "WHERE run_citation_id IN "
            "(SELECT id FROM run_citations "
            "WHERE run_response_id = ?)", (rid,),
        )
        cur.execute(
            "DELETE FROM run_citations "
            "WHERE run_response_id = ?", (rid,),
        )
        cur.execute(
            "DELETE FROM response_labels "
            "WHERE run_response_id = ?", (rid,),
        )

    for rid in run_ids:
        cur.execute(
            "DELETE FROM run_responses "
            "WHERE campaign_run_id = ?", (rid,),
        )

    for cid in camp_ids:
        for tbl in [
            "campaign_runs", "campaign_companies",
            "intent_clusters", "prompt_templates",
            "campaign_annotations", "insights",
        ]:
            cur.execute(
                f"DELETE FROM {tbl} WHERE campaign_id = ?",  # noqa: S608
                (cid,),
            )
        # query_definitions -> query_versions
        cur.execute(
            "SELECT id FROM query_definitions "
            "WHERE campaign_id = ?", (cid,),
        )
        qd_ids = [r[0] for r in cur.fetchall()]
        for qdid in qd_ids:
            cur.execute(
                "DELETE FROM query_versions "
                "WHERE query_definition_id = ?", (qdid,),
            )
        cur.execute(
            "DELETE FROM query_definitions "
            "WHERE campaign_id = ?", (cid,),
        )

    if ws_id:
        for tbl in [
            "campaigns", "comparison_snapshots",
            "operation_logs", "response_labels",
            "insights",
        ]:
            cur.execute(
                f"DELETE FROM {tbl} WHERE workspace_id = ?",  # noqa: S608
                (ws_id,),
            )

    # Projects, brands, legacy data
    cur.execute(
        "SELECT id FROM projects WHERE owner_id = ?",
        (demo_id,),
    )
    proj_ids = [r[0] for r in cur.fetchall()]
    for pid in proj_ids:
        cur.execute(
            "DELETE FROM brands WHERE project_id = ?",
            (pid,),
        )
        cur.execute(
            "SELECT id FROM queries "
            "WHERE project_id = ?", (pid,),
        )
        qids = [r[0] for r in cur.fetchall()]
        for qid in qids:
            cur.execute(
                "SELECT id FROM responses "
                "WHERE query_id = ?", (qid,),
            )
            rids = [r[0] for r in cur.fetchall()]
            for rid in rids:
                cur.execute(
                    "DELETE FROM citations "
                    "WHERE response_id = ?", (rid,),
                )
            cur.execute(
                "DELETE FROM responses "
                "WHERE query_id = ?", (qid,),
            )
        cur.execute(
            "DELETE FROM queries WHERE project_id = ?",
            (pid,),
        )

    cur.execute(
        "DELETE FROM projects WHERE owner_id = ?",
        (demo_id,),
    )

    # Company profiles + generated queries
    cur.execute(
        "SELECT id FROM company_profiles "
        "WHERE owner_id = ?", (demo_id,),
    )
    cp_ids = [r[0] for r in cur.fetchall()]
    for cpid in cp_ids:
        cur.execute(
            "DELETE FROM generated_queries "
            "WHERE company_profile_id = ?", (cpid,),
        )
    cur.execute(
        "DELETE FROM company_profiles "
        "WHERE owner_id = ?", (demo_id,),
    )

    # Pipeline data
    cur.execute(
        "SELECT id FROM query_sets WHERE owner_id = ?",
        (demo_id,),
    )
    qs_ids = [r[0] for r in cur.fetchall()]
    for qsid in qs_ids:
        cur.execute(
            "SELECT id FROM pipeline_categories "
            "WHERE query_set_id = ?", (qsid,),
        )
        cat_ids = [r[0] for r in cur.fetchall()]
        for catid in cat_ids:
            cur.execute(
                "SELECT id FROM expanded_queries "
                "WHERE category_id = ?", (catid,),
            )
            eq_ids = [r[0] for r in cur.fetchall()]
            for eqid in eq_ids:
                cur.execute(
                    "DELETE FROM raw_llm_responses "
                    "WHERE query_id = ?", (eqid,),
                )
            cur.execute(
                "DELETE FROM expanded_queries "
                "WHERE category_id = ?", (catid,),
            )
        cur.execute(
            "DELETE FROM pipeline_categories "
            "WHERE query_set_id = ?", (qsid,),
        )
        cur.execute(
            "DELETE FROM pipeline_jobs "
            "WHERE query_set_id = ?", (qsid,),
        )
        cur.execute(
            "DELETE FROM schedule_configs "
            "WHERE query_set_id = ?", (qsid,),
        )
    cur.execute(
        "DELETE FROM query_sets WHERE owner_id = ?",
        (demo_id,),
    )

    # Workspace + members + users
    if ws_id:
        cur.execute(
            "DELETE FROM workspace_members "
            "WHERE workspace_id = ?", (ws_id,),
        )
        cur.execute(
            "DELETE FROM workspaces WHERE id = ?",
            (ws_id,),
        )

    for mid in member_ids:
        cur.execute(
            "DELETE FROM users WHERE id = ?", (mid,),
        )


if __name__ == "__main__":
    seed_demo()
