# 아라 교육공고 알리미 (edu-alert)

전국 학교·교육청의 나라장터 입찰공고(체험학습·공연·예방교육 등)를
매일 오전 9시에 자동 수집해 웹앱으로 보여주는 시스템.

- 수집: `collector/collect.py` (GitHub Actions, `.github/workflows/collect.yml`)
- 웹앱: `docs/index.html` (GitHub Pages, 홈 화면 추가 가능)
- 데이터: `docs/alerts.json` (최근 30일 유지)

## 필요한 설정
1. GitHub Secret `NARA_API_KEY` — 공공데이터포털 인증키
2. Settings > Pages — main 브랜치 /docs 폴더로 배포

## 키워드 수정 방법
`collector/collect.py` 상단의 `KEYWORDS_URGENT`(🔴 핵심) /
`KEYWORDS_NORMAL`(🟡 일반) 목록을 수정 후 커밋.
