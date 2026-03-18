"""
fetch_transcripts.py
NVIDIA GTC 2026 YouTube 영상에서 자막(트랜스크립트)을 수집합니다.

사용:
    python fetch_transcripts.py              # 전체 수집
    python fetch_transcripts.py --ids ID1 ID2  # 특정 영상만
    python fetch_transcripts.py --limit 10   # 최대 N개
"""

import os
import sys
import json
import re
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel

console = Console()

# ─────────────────────────────────────────────────────────
# GTC 2026 알려진 영상 목록 (큐레이션)
# ─────────────────────────────────────────────────────────
CURATED_VIDEOS = [
    {
        "id": "twUJmYr33m8",
        "title": "NVIDIA GTC 2026 Keynote — Jensen Huang",
        "category": "Keynote",
        "description": "Jensen Huang GTC 2026 기조연설 — Vera Rubin, Groq LPU, Feynman, Robotics, AV, DLSS 5",
        "duration_seconds": 7200,
    },
]

# NVIDIA 공식 채널에서 GTC 2026 검색 키워드
GTC_SEARCH_QUERIES = [
    "ytsearch50:NVIDIA GTC 2026 session",
    "ytsearch30:NVIDIA GTC 2026 keynote",
    "ytsearch30:GTC 2026 AI robotics",
    "ytsearch30:GTC 2026 autonomous vehicles",
]

NVIDIA_CHANNEL_URL = "https://www.youtube.com/@NVIDIA"
DATA_DIR = Path("data")
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
SESSIONS_FILE = DATA_DIR / "sessions.json"


def ensure_dirs():
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def run_yt_dlp(args: list[str], capture=True) -> tuple[int, str, str]:
    """yt-dlp 명령 실행"""
    cmd = ["yt-dlp"] + args
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        timeout=300,
    )
    return result.returncode, result.stdout, result.stderr


def check_yt_dlp():
    """yt-dlp 설치 확인"""
    try:
        rc, out, _ = run_yt_dlp(["--version"])
        if rc == 0:
            console.print(f"[green]✓[/green] yt-dlp {out.strip()}")
            return True
    except FileNotFoundError:
        pass
    console.print("[red]✗ yt-dlp가 설치되지 않았습니다.[/red]")
    console.print("  설치: [cyan]pip install yt-dlp[/cyan]")
    return False


def fetch_video_info(video_id: str) -> dict | None:
    """단일 영상 메타데이터 조회"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    rc, out, err = run_yt_dlp([
        "--dump-json",
        "--no-playlist",
        "--skip-download",
        url
    ])
    if rc != 0:
        console.print(f"[yellow]⚠ 메타데이터 조회 실패: {video_id}[/yellow]")
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def fetch_transcript(video_id: str, output_dir: Path) -> dict | None:
    """
    영상에서 자막을 추출합니다.
    1) 수동 자막(영어) 우선
    2) 자동 생성 자막(영어) 사용
    반환: {"text": ..., "segments": [...], "language": ..., "source": ...}
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    vtt_path = output_dir / f"{video_id}.vtt"
    srt_path = output_dir / f"{video_id}.srt"
    txt_path = output_dir / f"{video_id}.txt"

    # 이미 수집된 경우 스킵
    if txt_path.exists() and txt_path.stat().st_size > 1000:
        console.print(f"  [dim]→ 캐시 사용: {video_id}[/dim]")
        return {"text": txt_path.read_text(encoding="utf-8"), "source": "cache"}

    # 1단계: 수동 자막 시도
    for lang in ["en", "en-US", "en-GB"]:
        rc, out, err = run_yt_dlp([
            "--write-sub",
            "--sub-lang", lang,
            "--sub-format", "vtt/srt/best",
            "--convert-subs", "srt",
            "--skip-download",
            "--no-playlist",
            "-o", str(output_dir / f"{video_id}.%(ext)s"),
            url
        ])
        # srt 파일 찾기
        for f in output_dir.glob(f"{video_id}*.srt"):
            text = parse_srt_to_text(f)
            if len(text) > 500:
                txt_path.write_text(text, encoding="utf-8")
                console.print(f"  [green]✓[/green] 수동 자막 ({lang}): {len(text):,}자")
                return {"text": text, "source": "manual", "language": lang}

    # 2단계: 자동 생성 자막 시도
    rc, out, err = run_yt_dlp([
        "--write-auto-sub",
        "--sub-lang", "en",
        "--sub-format", "vtt/srt/best",
        "--convert-subs", "srt",
        "--skip-download",
        "--no-playlist",
        "-o", str(output_dir / f"{video_id}.%(ext)s"),
        url
    ])
    for f in output_dir.glob(f"{video_id}*.srt"):
        text = parse_srt_to_text(f)
        if len(text) > 500:
            txt_path.write_text(text, encoding="utf-8")
            console.print(f"  [green]✓[/green] 자동 자막: {len(text):,}자")
            return {"text": text, "source": "auto", "language": "en"}

    console.print(f"  [red]✗[/red] 자막 없음: {video_id}")
    return None


def parse_srt_to_text(srt_path: Path) -> str:
    """SRT 파일 → 깨끗한 텍스트 변환"""
    content = srt_path.read_text(encoding="utf-8", errors="replace")
    # 타임코드 및 번호 제거
    lines = content.split("\n")
    text_lines = []
    skip_next = False
    for line in lines:
        line = line.strip()
        if re.match(r"^\d+$", line):
            skip_next = True
            continue
        if skip_next and re.match(r"\d{2}:\d{2}:\d{2},\d{3}", line):
            skip_next = False
            continue
        if line and not re.match(r"\d{2}:\d{2}:\d{2}", line):
            # HTML 태그 제거
            line = re.sub(r"<[^>]+>", "", line)
            # 중복 공백 제거
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                text_lines.append(line)

    # 연속 중복 줄 제거
    deduped = []
    prev = ""
    for line in text_lines:
        if line != prev:
            deduped.append(line)
        prev = line

    return " ".join(deduped)


def search_nvidia_gtc_videos(max_results: int = 50) -> list[dict]:
    """NVIDIA 채널에서 GTC 2026 영상 검색"""
    console.print("\n[cyan]NVIDIA YouTube에서 GTC 2026 영상 검색 중...[/cyan]")
    found = []
    seen_ids = set()

    for query in GTC_SEARCH_QUERIES:
        console.print(f"  검색: {query}")
        rc, out, err = run_yt_dlp([
            "--flat-playlist",
            "--dump-json",
            "--no-playlist",
            query
        ])
        if rc != 0:
            continue
        for line in out.strip().split("\n"):
            if not line:
                continue
            try:
                info = json.loads(line)
                vid_id = info.get("id", "")
                if not vid_id or vid_id in seen_ids:
                    continue
                title = info.get("title", "")
                # GTC 2026 관련 영상만 필터
                if not is_gtc_2026_video(title, info.get("description", "")):
                    continue
                seen_ids.add(vid_id)
                found.append({
                    "id": vid_id,
                    "title": title,
                    "category": infer_category(title),
                    "description": info.get("description", "")[:200],
                    "duration_seconds": info.get("duration", 0),
                    "view_count": info.get("view_count", 0),
                    "upload_date": info.get("upload_date", ""),
                    "channel": info.get("channel", ""),
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                })
                if len(found) >= max_results:
                    break
            except (json.JSONDecodeError, KeyError):
                continue
        if len(found) >= max_results:
            break

    console.print(f"  → {len(found)}개 영상 발견")
    return found


def is_gtc_2026_video(title: str, description: str) -> bool:
    """GTC 2026 관련 영상인지 확인"""
    text = (title + " " + description).lower()
    has_gtc = "gtc" in text or "gpu technology" in text
    has_2026 = "2026" in text
    has_nvidia = "nvidia" in text or "jensen" in text
    # 적어도 (GTC AND 2026) 또는 (GTC AND NVIDIA AND 최근 날짜)
    return (has_gtc and has_2026) or (has_gtc and has_nvidia and "2026" in text)


def infer_category(title: str) -> str:
    """영상 제목에서 카테고리 추론"""
    title_lower = title.lower()
    if any(k in title_lower for k in ["keynote", "jensen"]):
        return "Keynote"
    if any(k in title_lower for k in ["robot", "gr00t", "isaac", "physical ai"]):
        return "Robotics"
    if any(k in title_lower for k in ["autonom", "self-driv", "vehicle", "drive"]):
        return "Autonomous Vehicles"
    if any(k in title_lower for k in ["dlss", "gaming", "geforce", "rtx"]):
        return "Gaming"
    if any(k in title_lower for k in ["cloud", "aws", "azure", "enterprise"]):
        return "Cloud & Enterprise"
    if any(k in title_lower for k in ["hardware", "gpu", "rubin", "blackwell", "chip"]):
        return "Hardware"
    if any(k in title_lower for k in ["software", "dynamo", "cuda", "model", "llm", "ai stack"]):
        return "AI Software"
    if any(k in title_lower for k in ["bio", "health", "medical", "drug"]):
        return "Healthcare"
    if any(k in title_lower for k in ["space", "orbital", "satellite"]):
        return "Space"
    return "General"


def load_sessions() -> dict:
    """sessions.json 로드"""
    if SESSIONS_FILE.exists():
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    return {"sessions": [], "last_updated": None}


def save_sessions(data: dict):
    """sessions.json 저장"""
    data["last_updated"] = datetime.now().isoformat()
    SESSIONS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def print_sessions_table(sessions: list[dict]):
    """세션 목록 테이블 출력"""
    table = Table(title="수집된 GTC 2026 세션", show_header=True)
    table.add_column("No.", width=4)
    table.add_column("영상 ID", width=14)
    table.add_column("제목", max_width=50)
    table.add_column("카테고리", width=18)
    table.add_column("자막", width=6)
    for i, s in enumerate(sessions, 1):
        has_transcript = (TRANSCRIPTS_DIR / f"{s['id']}.txt").exists()
        table.add_row(
            str(i),
            s["id"],
            s["title"][:50],
            s.get("category", "-"),
            "[green]✓[/green]" if has_transcript else "[red]✗[/red]",
        )
    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="GTC 2026 YouTube 자막 수집기")
    parser.add_argument("--ids", nargs="+", help="특정 YouTube 영상 ID 지정")
    parser.add_argument("--limit", type=int, default=30, help="최대 수집 영상 수 (기본: 30)")
    parser.add_argument("--search", action="store_true", help="NVIDIA 채널에서 추가 영상 검색")
    parser.add_argument("--no-fetch", action="store_true", help="자막 다운로드 생략 (메타데이터만)")
    parser.add_argument("--list", action="store_true", help="수집된 세션 목록만 표시")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]GTC 2026 — YouTube 자막 수집기[/bold cyan]\n"
        "NVIDIA @NVIDIA 채널 → yt-dlp → data/transcripts/",
        border_style="cyan"
    ))

    ensure_dirs()

    # 목록만 보기
    if args.list:
        data = load_sessions()
        if data["sessions"]:
            print_sessions_table(data["sessions"])
        else:
            console.print("[yellow]수집된 세션 없음. python fetch_transcripts.py 실행[/yellow]")
        return

    # yt-dlp 확인
    if not check_yt_dlp():
        sys.exit(1)

    # 영상 목록 구성
    data = load_sessions()
    existing_ids = {s["id"] for s in data["sessions"]}

    videos_to_process = []

    if args.ids:
        # 특정 ID 지정
        for vid_id in args.ids:
            if vid_id not in existing_ids:
                videos_to_process.append({"id": vid_id, "title": f"Video {vid_id}", "category": "Unknown"})
            else:
                videos_to_process.append(next(s for s in data["sessions"] if s["id"] == vid_id))
    else:
        # 큐레이션 목록부터 시작
        for v in CURATED_VIDEOS:
            if v["id"] not in existing_ids:
                videos_to_process.append(v)
                existing_ids.add(v["id"])

        # 추가 검색
        if args.search:
            found = search_nvidia_gtc_videos(max_results=args.limit)
            for v in found:
                if v["id"] not in existing_ids:
                    videos_to_process.append(v)
                    existing_ids.add(v["id"])

    if not videos_to_process:
        console.print("[yellow]수집할 새 영상이 없습니다.[/yellow]")
        data = load_sessions()
        print_sessions_table(data["sessions"])
        return

    console.print(f"\n[bold]처리할 영상: {len(videos_to_process)}개[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("자막 수집 중...", total=len(videos_to_process))

        for video in videos_to_process:
            vid_id = video["id"]
            progress.update(task, description=f"[cyan]{vid_id}[/cyan] — {video['title'][:40]}")

            # 메타데이터 보강
            if not video.get("url"):
                video["url"] = f"https://www.youtube.com/watch?v={vid_id}"
            if not video.get("upload_date"):
                info = fetch_video_info(vid_id)
                if info:
                    video["title"] = info.get("title", video["title"])
                    video["description"] = info.get("description", "")[:500]
                    video["duration_seconds"] = info.get("duration", 0)
                    video["upload_date"] = info.get("upload_date", "")
                    video["view_count"] = info.get("view_count", 0)
                    video["category"] = infer_category(video["title"])

            # 자막 수집
            if not args.no_fetch:
                transcript_result = fetch_transcript(vid_id, TRANSCRIPTS_DIR)
                if transcript_result:
                    video["has_transcript"] = True
                    video["transcript_chars"] = len(transcript_result["text"])
                    video["transcript_source"] = transcript_result["source"]
                else:
                    video["has_transcript"] = False

            # sessions.json 업데이트
            existing_session = next((s for s in data["sessions"] if s["id"] == vid_id), None)
            if existing_session:
                existing_session.update(video)
            else:
                data["sessions"].append(video)

            save_sessions(data)
            progress.advance(task)

    console.print("\n[bold green]✓ 수집 완료[/bold green]")
    print_sessions_table(data["sessions"])
    console.print(f"\n[dim]저장 위치: {SESSIONS_FILE}[/dim]")
    console.print("[dim]다음 단계: python analyze_sessions.py[/dim]")


if __name__ == "__main__":
    main()
