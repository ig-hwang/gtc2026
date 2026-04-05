# NVIDIA GTC 2026 — BCG Intelligence Brief

> Jensen Huang 기조연설(2026.03.16) 및 GTC 2026 전체 세션을 분석한 BCG 스타일 인텔리전스 리포트.  
> **라이브 URL:** [https://ig-hwang.github.io/gtc2026/](https://ig-hwang.github.io/gtc2026/)

---

## 개요

YouTube에서 GTC 2026 세션 트랜스크립트를 자동 수집하고, Claude API로 분석한 뒤, 단일 HTML 파일로 배포하는 **3단계 파이프라인** 프로젝트다. 최종 결과물은 GitHub Pages를 통해 링크 하나로 공유된다.

```
YouTube 영상
    │
    ▼ yt-dlp (자막 수집)
data/transcripts/*.txt
    │
    ▼ Claude API claude-opus-4-6 (세션 분석)
data/analyses/*.json
    │
    ▼ generate_html.py (HTML 렌더링)
index.html
    │
    ▼ GitHub Pages
https://ig-hwang.github.io/gtc2026/
```

---

## 프로젝트 구조

```
gtc2026/
├── pipeline.py            # 메인 CLI — 전체 파이프라인 오케스트레이터
├── fetch_transcripts.py   # Step 1: YouTube 자막 수집 (yt-dlp)
├── analyze_sessions.py    # Step 2: Claude API 세션 분석
├── generate_html.py       # Step 3: BCG 스타일 HTML 리포트 생성
│
├── index.html             # 최종 결과물 (GitHub Pages 배포 대상)
│
├── data/
│   ├── sessions.json          # 수집 대상 영상 메타데이터
│   ├── transcripts/           # 수집된 자막 텍스트 (.txt) — gitignore
│   └── analyses/              # Claude 분석 결과 JSON — gitignore
│
├── requirements.txt       # Python 의존성
├── .env                   # API 키 (gitignore)
└── .env.example           # 환경변수 템플릿
```

---

## 파이프라인 상세

### Step 1 — YouTube 자막 수집 (`fetch_transcripts.py`)

`yt-dlp`를 사용해 YouTube 영상의 자막(Auto-generated caption)을 텍스트 파일로 저장한다.

- 큐레이션된 영상 목록(`CURATED_VIDEOS`)과 검색 쿼리(`GTC_SEARCH_QUERIES`) 두 가지 소스 사용
- 수집된 자막은 `data/transcripts/{video_id}.txt`로 저장
- 영상 메타데이터(제목, 카테고리, URL)는 `data/sessions.json`으로 관리

```bash
python pipeline.py fetch                          # 전체 수집
python pipeline.py fetch --ids twUJmYr33m8        # 특정 영상만
python pipeline.py fetch --search --limit 30      # NVIDIA 채널 추가 검색
```

### Step 2 — Claude API 분석 (`analyze_sessions.py`)

수집된 트랜스크립트를 Claude API(`claude-opus-4-6`)로 분석한다.

- 모델: `claude-opus-4-6` (Extended Thinking + Streaming 활성화)
- 시스템 프롬프트: BCG 스타일 분석 요청 — 한국어 출력, 기술 용어 원어 병기
- 분석 결과는 구조화된 JSON으로 `data/analyses/{video_id}.json`에 저장
- 트랜스크립트 최대 80,000자로 제한 (토큰 비용 최적화)
- `--force` 옵션으로 기존 분석 재실행 가능

```bash
python pipeline.py analyze                        # 전체 분석
python pipeline.py analyze --ids twUJmYr33m8      # 특정 세션만
python pipeline.py analyze --force                # 기존 분석 덮어쓰기
```

### Step 3 — HTML 리포트 생성 (`generate_html.py`)

JSON 분석 결과를 읽어 단일 `index.html` 파일로 렌더링한다.

- 순수 HTML/CSS/JS만 사용 (외부 프레임워크·CDN 의존성 없음)
- 사이드바 네비게이션 + 멀티페이지 SPA 구조
- BCG 스타일 다크 테마 (NVIDIA 그린 `#76b900` 기반 컬러 팔레트)

```bash
python pipeline.py generate                       # index.html 생성
python pipeline.py generate --out report.html     # 출력 파일 지정
```

### 전체 파이프라인 한 번에 실행

```bash
python pipeline.py all
python pipeline.py all --force --out index.html
```

---

## 설치 및 실행

### 요구사항

- Python 3.11+
- Anthropic API 키

### 설치

```bash
git clone https://github.com/ig-hwang/gtc2026.git
cd gtc2026

pip install -r requirements.txt

cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY=your_key_here 입력
```

### 의존성

| 패키지 | 용도 |
|---|---|
| `anthropic >= 0.50.0` | Claude API 클라이언트 |
| `yt-dlp >= 2024.12.0` | YouTube 자막 수집 |
| `python-dotenv >= 1.0.0` | 환경변수 관리 |
| `rich >= 13.0.0` | CLI 출력 포매팅 |
| `aiofiles >= 23.0.0` | 비동기 파일 I/O |

---

## 결과물 구조 (`index.html`)

단일 HTML 파일로 모든 콘텐츠가 포함된다. 총 **15개 페이지**, 사이드바 네비게이션으로 이동.

### 페이지 구성

| 섹션 | 페이지 | 내용 |
|---|---|---|
| **Jensen Huang 기조연설** | 기조연설 전체 개요 | Inference Inflection, 3대 스케일링 법칙, 검증된 인용구 |
| | 하드웨어 플랫폼 | Vera Rubin(7칩·5랙), Groq LPU, Blackwell Ultra, 로드맵 비교 |
| | AI 소프트웨어 스택 | Dynamo, OpenClaw, Nemotron Coalition 8개 파트너 |
| | 로보틱스 & Physical AI | GR00T N2, Disney Olaf 데모, Isaac Lab, 생태계 6레이어 |
| | 자율주행 | Alpamayo 1.5, Uber/BYD 파트너십, Cosmos 3 |
| | DLSS 5 & 뉴럴 렌더링 | 3D-Guided Neural Rendering, CloudXR |
| | 클라우드 & 엔터프라이즈 | AWS·Azure·GCP 파트너십, AI-RAN |
| **GTC 전문 트랙** | 헬스케어 & BioAI | BioNeMo, GR00T-H, Open-H 데이터셋 |
| | 우주 컴퓨팅 | Space-1 Vera Rubin Module, 궤도 AI |
| | 엔터프라이즈 & 산업 AI | 구조화 데이터, 금융·에너지·제조 적용 사례 |
| | 기술 로드맵 2026–2028 | Rubin Ultra, Feynman 아키텍처 |
| **Investment** | LG U+ 로봇 투자 유망 기업 10선 | 기술력·통신사 시너지·성장 가능성 3기준 평가 |
| **Analysis** | BCG Insights | 8개 전략 인사이트, 참고자료 19개 |
| | 관련 뉴스 & 논문 | 언론 보도, 학술 논문 큐레이션 |

### 주요 UI 컴포넌트

```
source-bar          출처 신뢰도 표시 (keynote / press / session / warn)
insight-box         BCG Insight — 3-pillar 구조 (전략 / 경쟁 / 리스크)
insight-refs        참고자료 뱃지 목록
spec-grid           스펙 수치 그리드
compare-table       BCG 스타일 비교 테이블
timeline            연대기 타임라인
badge               상태/카테고리 레이블
quote               검증된 원문 인용구
```

### 출처 신뢰도 시스템

모든 콘텐츠에 4단계 출처 레이블을 적용한다.

| 색상 | 의미 |
|---|---|
| 🟢 `keynote` | Jensen Huang 기조연설 원문 직접 확인 |
| 🔵 `press` | NVIDIA 공식 발표자료 / Press Release |
| 🟠 `session` | GTC 전문 트랙 세션 |
| 🔴 `warn` | 보도 기반 / 키노트 미확인 — ⚠ 표시 |

---

## 수동 편집 및 품질 관리

자동 생성된 HTML은 다음 항목에 대해 **트랜스크립트 원문 교차 검증** 후 수동 수정됐다.

- **사실 오류 수정**: "6개 칩" → "7개 칩 + 5개 랙 스케일 컴퓨터"
- **미확인 수치 경고 추가**: Groq 인수가($200억), Uber 10만 대, AWS 100만 GPU, Space-1 25배 등
- **검증된 원문 인용 추가**: `"Robotics is a $50 trillion industry"`, `"$1 trillion... going to be short"` 등
- **투자 분석 섹션 추가**: Physical AI 로봇 분야 10개사 — 기술력 / 통신사 시너지 / 성장 가능성 3기준

---

## 배포

GitHub Pages를 사용한 정적 사이트 배포. 별도 서버·빌드 과정 없이 `main` 브랜치의 `index.html`이 직접 서빙된다.

```bash
# 콘텐츠 수정 후 배포
git add index.html
git commit -m "Update content"
git push origin main
# → 약 1~2분 후 https://ig-hwang.github.io/gtc2026/ 자동 반영
```

### GitHub Pages 최초 활성화 (이미 완료)

```bash
gh api repos/ig-hwang/gtc2026/pages \
  --method POST \
  --input - <<'EOF'
{"source":{"branch":"main","path":"/"}}
EOF
```

---

## 데이터 보안

| 항목 | 처리 방식 |
|---|---|
| `ANTHROPIC_API_KEY` | `.env` 파일 — `.gitignore` 적용, 절대 커밋 금지 |
| `data/transcripts/` | YouTube 공개 자막 — 용량 이슈로 `.gitignore` 적용 |
| `data/analyses/` | Claude 분석 결과 — `.gitignore` 적용 |
| `index.html` | 민감 정보 없는 순수 HTML — 공개 배포 |

---

## 라이선스

이 프로젝트는 개인 학습 및 내부 공유 목적으로 제작됐습니다.  
NVIDIA GTC 발표 내용의 저작권은 NVIDIA Corporation에 귀속됩니다.
