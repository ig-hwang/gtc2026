"""
pipeline.py
GTC 2026 분석 파이프라인 — 메인 CLI

사용법:
    python pipeline.py fetch              # 1단계: YouTube 자막 수집
    python pipeline.py analyze            # 2단계: Claude API 분석
    python pipeline.py generate           # 3단계: HTML 생성
    python pipeline.py all                # 전체 파이프라인 실행

옵션:
    python pipeline.py fetch --search     # NVIDIA 채널에서 추가 영상 검색
    python pipeline.py fetch --ids twUJmYr33m8   # 특정 영상만
    python pipeline.py analyze --force    # 기존 분석 재실행
    python pipeline.py generate --out report.html

환경설정:
    .env 파일에 ANTHROPIC_API_KEY=your_key_here
"""

import sys
import subprocess
import argparse
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

load_dotenv()
console = Console()


def run_step(script: str, extra_args: list[str] = None) -> int:
    cmd = [sys.executable, script] + (extra_args or [])
    console.print(f"\n[bold cyan]▶ {' '.join(cmd)}[/bold cyan]")
    result = subprocess.run(cmd)
    return result.returncode


def step_fetch(args) -> int:
    extra = []
    if args.ids:
        extra += ["--ids"] + args.ids
    if getattr(args, "search", False):
        extra.append("--search")
    if getattr(args, "limit", None):
        extra += ["--limit", str(args.limit)]
    return run_step("fetch_transcripts.py", extra)


def step_analyze(args) -> int:
    extra = []
    if args.ids:
        extra += ["--ids"] + args.ids
    if getattr(args, "force", False):
        extra.append("--force")
    if getattr(args, "dry_run", False):
        extra.append("--dry-run")
    return run_step("analyze_sessions.py", extra)


def step_generate(args) -> int:
    extra = []
    if getattr(args, "out", None):
        extra += ["--out", args.out]
    rc = run_step("generate_html.py", extra)
    if rc == 0:
        out_file = getattr(args, "out", "index.html")
        console.print(f"\n[bold green]파이프라인 완료![/bold green]")
        console.print(f"브라우저에서 열기: [cyan]open {out_file}[/cyan]")
    return rc


def main():
    parser = argparse.ArgumentParser(
        description="GTC 2026 분석 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # fetch 서브커맨드
    p_fetch = subparsers.add_parser("fetch", help="YouTube 자막 수집")
    p_fetch.add_argument("--ids", nargs="+", help="특정 YouTube 영상 ID")
    p_fetch.add_argument("--search", action="store_true", help="NVIDIA 채널 추가 검색")
    p_fetch.add_argument("--limit", type=int, default=30, help="최대 영상 수")

    # analyze 서브커맨드
    p_analyze = subparsers.add_parser("analyze", help="Claude API로 세션 분석")
    p_analyze.add_argument("--ids", nargs="+", help="특정 영상 ID만 분석")
    p_analyze.add_argument("--force", action="store_true", help="기존 분석 재실행")
    p_analyze.add_argument("--dry-run", action="store_true", help="시뮬레이션")

    # generate 서브커맨드
    p_generate = subparsers.add_parser("generate", help="HTML 리포트 생성")
    p_generate.add_argument("--out", default="index.html", help="출력 파일")

    # all 서브커맨드
    p_all = subparsers.add_parser("all", help="전체 파이프라인 실행")
    p_all.add_argument("--ids", nargs="+", help="특정 영상 ID만")
    p_all.add_argument("--search", action="store_true", help="추가 검색")
    p_all.add_argument("--force", action="store_true", help="분석 재실행")
    p_all.add_argument("--out", default="index.html", help="출력 파일")

    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold]NVIDIA GTC 2026 분석 파이프라인[/bold]\n"
        "YouTube → yt-dlp → 자막 → Claude API → BCG 스타일 HTML",
        border_style="cyan"
    ))

    if args.command == "fetch":
        sys.exit(step_fetch(args))

    elif args.command == "analyze":
        sys.exit(step_analyze(args))

    elif args.command == "generate":
        sys.exit(step_generate(args))

    elif args.command == "all":
        console.print(Rule("[cyan]Step 1/3 — YouTube 자막 수집[/cyan]"))
        rc = step_fetch(args)
        if rc != 0:
            console.print("[red]✗ 자막 수집 실패[/red]")
            sys.exit(rc)

        console.print(Rule("[cyan]Step 2/3 — Claude API 분석[/cyan]"))
        rc = step_analyze(args)
        if rc != 0:
            console.print("[red]✗ 분석 실패[/red]")
            sys.exit(rc)

        console.print(Rule("[cyan]Step 3/3 — HTML 생성[/cyan]"))
        rc = step_generate(args)
        sys.exit(rc)


if __name__ == "__main__":
    main()
