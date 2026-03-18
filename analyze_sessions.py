"""
analyze_sessions.py
Claude API (claude-opus-4-6, adaptive thinking + streaming)로 GTC 2026 세션을 분석합니다.

사용:
    python analyze_sessions.py              # 전체 분석
    python analyze_sessions.py --ids ID1    # 특정 세션만
    python analyze_sessions.py --force      # 기존 분석 덮어쓰기
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown

load_dotenv()

console = Console()

DATA_DIR = Path("data")
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
ANALYSES_DIR = DATA_DIR / "analyses"
SESSIONS_FILE = DATA_DIR / "sessions.json"

# 분석 청크 최대 크기 (토큰 절약을 위해 트랜스크립트 앞부분 우선)
MAX_TRANSCRIPT_CHARS = 80_000  # ~20K tokens

ANALYSIS_SYSTEM_PROMPT = """당신은 NVIDIA GTC 2026 컨퍼런스 세션을 분석하는 전문 기술 애널리스트입니다.
BCG(Boston Consulting Group) 스타일의 명확하고 인사이트 있는 분석을 제공합니다.

분석 원칙:
- 정확성 최우선: 트랜스크립트에 명시된 내용만 사용. 추측 금지.
- 비전문가도 이해할 수 있도록 기술 개념을 평이하게 설명.
- 전략적 의미와 비즈니스 임팩트를 중심으로 인사이트 도출.
- 핵심 수치/사양/발표 내용을 정확하게 인용.
- 한국어로 출력하되, 기술 용어의 원어를 병기.

출력 형식: 유효한 JSON만 출력 (마크다운 코드블록 없이)."""

ANALYSIS_PROMPT_TEMPLATE = """다음은 NVIDIA GTC 2026 세션 트랜스크립트입니다.

세션 정보:
- 제목: {title}
- 카테고리: {category}
- URL: {url}

트랜스크립트:
---
{transcript}
---

위 트랜스크립트를 분석하여 다음 JSON 형식으로 출력하세요:

{{
  "session_id": "{video_id}",
  "title": "세션 공식 제목 (트랜스크립트 기반)",
  "subtitle": "부제목 또는 핵심 메시지 한 줄",
  "category": "{category}",
  "speakers": ["발표자 이름 목록"],
  "duration_note": "세션 길이/범위 메모",
  "executive_summary": "경영진 요약 (3-4문장, 핵심 발표 내용과 의미)",
  "key_announcements": [
    {{
      "title": "발표 항목 제목",
      "detail": "상세 내용 (수치/사양 포함)",
      "significance": "전략적 의미"
    }}
  ],
  "technical_specs": [
    {{
      "name": "스펙 항목명",
      "value": "값",
      "context": "맥락 (기존 대비 등)"
    }}
  ],
  "key_quotes": [
    {{
      "speaker": "발언자",
      "quote": "정확한 인용 (영어 원문)",
      "significance": "이 발언의 의미"
    }}
  ],
  "demo_highlights": [
    "주요 데모 또는 시연 내용"
  ],
  "partnerships_announced": [
    {{
      "partner": "파트너사",
      "detail": "파트너십 내용"
    }}
  ],
  "bcg_insights": [
    {{
      "title": "인사이트 제목",
      "insight": "상세 전략적 인사이트 (3-5문장)",
      "implication": "산업/비즈니스 함의"
    }}
  ],
  "tags": ["태그1", "태그2"],
  "related_topics": ["관련 기술/트렌드"],
  "confidence": "high|medium|low (트랜스크립트 품질 기반)"
}}"""


def load_sessions() -> dict:
    if not SESSIONS_FILE.exists():
        console.print("[red]sessions.json 없음. 먼저 python fetch_transcripts.py 실행[/red]")
        sys.exit(1)
    return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))


def load_transcript(video_id: str) -> str | None:
    txt_path = TRANSCRIPTS_DIR / f"{video_id}.txt"
    if not txt_path.exists():
        return None
    text = txt_path.read_text(encoding="utf-8")
    # 너무 길면 자름 (앞부분 + 중간 + 뒷부분 균등 추출)
    if len(text) > MAX_TRANSCRIPT_CHARS:
        chunk = MAX_TRANSCRIPT_CHARS // 3
        text = (
            text[:chunk] +
            f"\n\n[... 중간 생략 ({len(text) - MAX_TRANSCRIPT_CHARS:,}자) ...]\n\n" +
            text[len(text) // 2 - chunk // 2: len(text) // 2 + chunk // 2] +
            f"\n\n[... 후반부 ...]\n\n" +
            text[-chunk:]
        )
    return text


def analyze_session_with_claude(
    client: anthropic.Anthropic,
    session: dict,
    transcript: str,
) -> dict | None:
    """Claude API로 단일 세션 분석 (streaming + adaptive thinking)"""

    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        video_id=session["id"],
        title=session.get("title", ""),
        category=session.get("category", "General"),
        url=session.get("url", f"https://www.youtube.com/watch?v={session['id']}"),
        transcript=transcript,
    )

    console.print(f"  [cyan]→ Claude API 스트리밍 분석...[/cyan]")

    collected_text = []

    try:
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": ANALYSIS_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},  # 시스템 프롬프트 캐시
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        collected_text.append(event.delta.text)
                        # 진행 표시
                        if len(collected_text) % 50 == 0:
                            console.print(".", end="", style="dim")

            final = stream.get_final_message()
            console.print()  # 줄바꿈

        # 사용량 출력
        usage = final.usage
        console.print(
            f"  [dim]토큰: 입력 {usage.input_tokens:,} / 출력 {usage.output_tokens:,}[/dim]"
        )
        if hasattr(usage, "cache_read_input_tokens") and usage.cache_read_input_tokens:
            console.print(f"  [dim]캐시 절약: {usage.cache_read_input_tokens:,} 토큰[/dim]")

        # JSON 파싱
        raw = "".join(collected_text).strip()
        # 마크다운 코드블록 제거 (혹시 포함된 경우)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        analysis = json.loads(raw)
        analysis["_meta"] = {
            "analyzed_at": datetime.now().isoformat(),
            "model": "claude-opus-4-6",
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "transcript_chars": len(transcript),
        }
        return analysis

    except json.JSONDecodeError as e:
        console.print(f"  [red]JSON 파싱 오류: {e}[/red]")
        console.print(f"  [dim]원본: {raw[:200]}...[/dim]")
        # raw 저장
        (ANALYSES_DIR / f"{session['id']}_raw.txt").write_text(
            "".join(collected_text), encoding="utf-8"
        )
        return None
    except anthropic.APIError as e:
        console.print(f"  [red]Claude API 오류: {e}[/red]")
        return None


def save_analysis(video_id: str, analysis: dict):
    path = ANALYSES_DIR / f"{video_id}.json"
    path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_analysis(video_id: str) -> dict | None:
    path = ANALYSES_DIR / f"{video_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def print_analysis_preview(analysis: dict):
    """분석 결과 미리보기 출력"""
    console.print(f"\n  [bold]{analysis.get('title', '')}[/bold]")
    console.print(f"  [dim]{analysis.get('executive_summary', '')[:200]}[/dim]")
    announcements = analysis.get("key_announcements", [])
    if announcements:
        console.print(f"  [green]주요 발표 {len(announcements)}건[/green]")
    insights = analysis.get("bcg_insights", [])
    if insights:
        console.print(f"  [cyan]BCG 인사이트 {len(insights)}건[/cyan]")


def main():
    parser = argparse.ArgumentParser(description="GTC 2026 세션 분석기 (Claude API)")
    parser.add_argument("--ids", nargs="+", help="특정 YouTube 영상 ID만 분석")
    parser.add_argument("--force", action="store_true", help="기존 분석 결과 덮어쓰기")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 시뮬레이션")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]GTC 2026 — Claude API 세션 분석기[/bold cyan]\n"
        "claude-opus-4-6 · adaptive thinking · streaming · prompt caching",
        border_style="cyan"
    ))

    # API 키 확인
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        console.print("[red]ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.[/red]")
        console.print("  .env 파일에 ANTHROPIC_API_KEY=your_key_here 추가")
        sys.exit(1)

    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)

    # 세션 로드
    data = load_sessions()
    sessions = data["sessions"]

    if args.ids:
        sessions = [s for s in sessions if s["id"] in args.ids]
        if not sessions:
            console.print(f"[red]지정한 ID를 찾을 수 없습니다: {args.ids}[/red]")
            sys.exit(1)

    # 분석 대상 필터
    to_analyze = []
    skipped = 0
    for session in sessions:
        vid_id = session["id"]
        # 자막 확인
        if not session.get("has_transcript") and not (TRANSCRIPTS_DIR / f"{vid_id}.txt").exists():
            console.print(f"[yellow]⚠ 자막 없음, 건너뜀: {vid_id} — {session.get('title', '')[:40]}[/yellow]")
            skipped += 1
            continue
        # 기존 분석 확인
        if not args.force and load_analysis(vid_id):
            console.print(f"[dim]→ 이미 분석됨: {vid_id}[/dim]")
            skipped += 1
            continue
        to_analyze.append(session)

    console.print(f"\n분석 대상: [bold]{len(to_analyze)}개[/bold]  건너뜀: [dim]{skipped}개[/dim]")

    if not to_analyze:
        console.print("[green]모든 세션이 이미 분석되었습니다.[/green]")
        console.print("[dim]--force 플래그로 재분석 가능[/dim]")
        return

    if args.dry_run:
        console.print("[yellow]Dry-run 모드: 실제 API 호출 없음[/yellow]")
        for s in to_analyze:
            console.print(f"  [{s.get('category', '-')}] {s['id']} — {s.get('title', '')[:50]}")
        return

    # Claude 클라이언트 초기화
    client = anthropic.Anthropic(api_key=api_key)

    # 분석 실행
    results = {"success": 0, "failed": 0, "analyses": []}

    for i, session in enumerate(to_analyze, 1):
        vid_id = session["id"]
        console.print(
            f"\n[bold]({i}/{len(to_analyze)}) {session.get('category', '-')} — "
            f"{session.get('title', vid_id)[:60]}[/bold]"
        )

        # 트랜스크립트 로드
        transcript = load_transcript(vid_id)
        if not transcript:
            console.print(f"  [red]✗ 트랜스크립트 파일 없음[/red]")
            results["failed"] += 1
            continue

        console.print(f"  트랜스크립트: {len(transcript):,}자")

        # 분석
        analysis = analyze_session_with_claude(client, session, transcript)

        if analysis:
            save_analysis(vid_id, analysis)
            print_analysis_preview(analysis)
            results["success"] += 1
            results["analyses"].append({
                "id": vid_id,
                "title": analysis.get("title", ""),
                "category": analysis.get("category", ""),
                "status": "success",
            })
            console.print(f"  [green]✓ 저장: {ANALYSES_DIR / f'{vid_id}.json'}[/green]")
        else:
            results["failed"] += 1
            results["analyses"].append({
                "id": vid_id,
                "status": "failed",
            })

    # 최종 요약
    console.print(Panel(
        f"[bold green]완료: {results['success']}개[/bold green]  "
        f"[red]실패: {results['failed']}개[/red]\n\n"
        f"다음 단계: [cyan]python generate_html.py[/cyan]",
        title="분석 완료",
        border_style="green" if results["failed"] == 0 else "yellow"
    ))


if __name__ == "__main__":
    main()
