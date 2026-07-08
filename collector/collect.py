# -*- coding: utf-8 -*-
"""
아라컴퍼니 교육기관 공고 알리미 - 수집기
나라장터(조달청) 입찰공고 API에서 교육 관련 공고를 수집해
docs/alerts.json 에 저장한다. (GitHub Actions가 매일 실행)
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

API_KEY = os.environ.get("NARA_API_KEY", "").strip()
BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"

# 업무구분별 조회 오퍼레이션 (용역 = 공연/교육 용역이 대부분 여기)
OPERATIONS = [
    ("용역", "getBidPblancListInfoServcPPSSrch"),
    ("물품", "getBidPblancListInfoThngPPSSrch"),
]

# ── 키워드 설정 ─────────────────────────────────────────────
# 🔴 즉시(핵심): 공고명에 있으면 무조건 수집 + 긴급 표시
KEYWORDS_URGENT = [
    "현장체험학습", "수학여행", "수련활동", "체험학습",
    "학교폭력 예방", "학교폭력예방", "흡연 예방", "흡연예방",
    "음주 예방", "도박 예방", "마약 예방", "약물 예방",
    "딥페이크", "디지털 성범죄", "사이버폭력",
    "인성교육", "생명존중", "자살예방", "성교육", "양성평등",
    "공연 관람", "관람 공연", "뮤지컬", "연극",
]

# 🟡 일반: 공고명에 있으면 수집 (일반 표시)
KEYWORDS_NORMAL = [
    "문화예술교육", "문화예술", "예술교육", "예술체험", "문화체험",
    "교육활동", "체험활동", "학교예술", "문화행사",
    "예방교육", "안전교육", "진로교육",
]

# 발주기관(수요기관) 이름에 이 단어가 있으면 교육기관으로 판단
EDU_ORG_WORDS = ["학교", "교육청", "교육지원청", "교육원", "교육연수원", "유치원", "교육심의"]

# 공고명에 이 단어가 있으면 제외 (공사/시설/컨설팅 잡음 제거)
EXCLUDE_WORDS = ["공사", "보수", "증축", "신축", "철거", "설비", "전기", "소방",
                 "급식", "식자재", "청소용역", "경비용역", "통학차량", "냉난방",
                 "ISO", "인증", "컨설팅", "타당성", "기술검토", "민간투자",
                 "감리", "설계", "실시설계", "유지관리", "시스템 구축", "구축 용역"]


def http_get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "edu-alert/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        print("[경고] JSON이 아닌 응답 수신. 앞부분 500자:")
        print(body[:500])
        return None


def fetch_by_keyword(op_name: str, keyword: str, bgn: str, end: str):
    """공고명(bidNtceNm)에 키워드가 들어간 공고 목록 조회"""
    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "100",
        "inqryDiv": "1",          # 1 = 공고게시일시 기준
        "inqryBgnDt": bgn,        # YYYYMMDDHHMM
        "inqryEndDt": end,
        "bidNtceNm": keyword,     # 공고명 검색
        "type": "json",
    }
    qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = f"{BASE_URL}/{op_name}?{qs}"
    data = http_get_json(url)
    if not data:
        return []
    try:
        header = data["response"]["header"]
        if header.get("resultCode") not in ("00", "0"):
            print(f"[API오류] {op_name} '{keyword}': {header}")
            return []
        items = data["response"]["body"].get("items", [])
        if isinstance(items, dict):  # 단건이면 dict로 옴
            items = items.get("item", [])
            if isinstance(items, dict):
                items = [items]
        return items or []
    except (KeyError, TypeError) as e:
        print(f"[구조오류] {op_name} '{keyword}': {e}")
        print(json.dumps(data, ensure_ascii=False)[:500])
        return []


def is_edu_org(item: dict) -> bool:
    org = (item.get("dminsttNm") or "") + " " + (item.get("ntceInsttNm") or "")
    return any(w in org for w in EDU_ORG_WORDS)


def is_excluded(name: str) -> bool:
    return any(w in name for w in EXCLUDE_WORDS)


def main():
    if not API_KEY:
        print("오류: NARA_API_KEY 환경변수(시크릿)가 비어 있습니다.")
        sys.exit(1)

    now = datetime.now(KST)
    bgn = (now - timedelta(days=2)).strftime("%Y%m%d0000")  # 최근 2일치
    end = now.strftime("%Y%m%d%H%M")

    collected = {}
    for label, op in OPERATIONS:
        for tier, keywords in (("urgent", KEYWORDS_URGENT), ("normal", KEYWORDS_NORMAL)):
            for kw in keywords:
                for it in fetch_by_keyword(op, kw, bgn, end):
                    name = it.get("bidNtceNm", "")
                    no = it.get("bidNtceNo", "") + "-" + it.get("bidNtceOrd", "0")
                    if not name or is_excluded(name):
                        continue
                    edu = is_edu_org(item=it)
                    # 교육기관 공고이거나, 긴급 키워드면 기관 무관 수집
                    if not edu and tier != "urgent":
                        continue
                    prev = collected.get(no)
                    entry = {
                        "id": no,
                        "title": name,
                        "org": it.get("dminsttNm") or it.get("ntceInsttNm", ""),
                        "region": it.get("prtcptLmtRgnNm", ""),
                        "amount": it.get("asignBdgtAmt") or it.get("presmptPrce", ""),
                        "posted": it.get("bidNtceDt", ""),
                        "deadline": it.get("bidClseDt", ""),
                        "url": it.get("bidNtceDtlUrl") or it.get("bidNtceUrl", ""),
                        "type": label,
                        "tier": "urgent" if tier == "urgent" else "normal",
                        "keyword": kw,
                        "edu_org": edu,
                    }
                    if prev is None or (prev["tier"] != "urgent" and entry["tier"] == "urgent"):
                        collected[no] = entry

    # 기존 데이터와 병합 (최근 30일 유지)
    out_path = os.path.join(os.path.dirname(__file__), "..", "docs", "alerts.json")
    out_path = os.path.abspath(out_path)
    old = {"items": [], "updated": ""}
    if os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            pass

    merged = {i["id"]: i for i in old.get("items", [])}
    new_count = sum(1 for k in collected if k not in merged)
    merged.update(collected)

    cutoff = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    items = [v for v in merged.values() if (v.get("posted") or "9999")[:10] >= cutoff]
    items.sort(key=lambda x: x.get("posted", ""), reverse=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"updated": now.strftime("%Y-%m-%d %H:%M"), "new_today": new_count, "items": items},
            f, ensure_ascii=False, indent=1,
        )

    print(f"완료: 신규 {new_count}건 / 전체 {len(items)}건 저장 → docs/alerts.json")


if __name__ == "__main__":
    main()
