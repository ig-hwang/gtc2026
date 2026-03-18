"""
generate_html.py
분석 결과(data/analyses/)에서 BCG 스타일 HTML 리포트를 생성합니다.

사용:
    python generate_html.py              # index.html 생성
    python generate_html.py --out report.html  # 출력 파일 지정
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

from rich.console import Console

console = Console()

DATA_DIR = Path("data")
ANALYSES_DIR = DATA_DIR / "analyses"
SESSIONS_FILE = DATA_DIR / "sessions.json"


def load_all_analyses() -> list[dict]:
    analyses = []
    if not ANALYSES_DIR.exists():
        return analyses
    for f in sorted(ANALYSES_DIR.glob("*.json")):
        if f.stem.endswith("_raw"):
            continue
        try:
            a = json.loads(f.read_text(encoding="utf-8"))
            analyses.append(a)
        except json.JSONDecodeError:
            console.print(f"[yellow]⚠ JSON 파싱 실패: {f}[/yellow]")
    return analyses


def load_sessions() -> list[dict]:
    if SESSIONS_FILE.exists():
        data = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
        return data.get("sessions", [])
    return []


def category_icon(category: str) -> str:
    icons = {
        "Keynote": "🎤",
        "Hardware": "⚡",
        "AI Software": "🧠",
        "Robotics": "🤖",
        "Autonomous Vehicles": "🚗",
        "Gaming": "🎮",
        "Cloud & Enterprise": "☁️",
        "Healthcare": "🏥",
        "Space": "🛸",
        "General": "📋",
    }
    return icons.get(category, "📋")


def badge_class(category: str) -> str:
    classes = {
        "Keynote": "badge-gold",
        "Hardware": "badge-orange",
        "AI Software": "badge-blue",
        "Robotics": "badge-green",
        "Autonomous Vehicles": "badge-green",
        "Gaming": "badge-blue",
        "Cloud & Enterprise": "badge-blue",
        "Healthcare": "badge-red",
        "Space": "badge-gold",
        "General": "badge-blue",
    }
    return classes.get(category, "badge-blue")


def escape_html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def render_nav_items(analyses: list[dict]) -> str:
    html = ""
    # 카테고리별 그룹
    categories = {}
    for a in analyses:
        cat = a.get("category", "General")
        categories.setdefault(cat, []).append(a)

    for cat, items in categories.items():
        icon = category_icon(cat)
        html += f'<div class="nav-section">{escape_html(cat)}</div>\n'
        for a in items:
            sid = escape_html(a.get("session_id", ""))
            title = escape_html(a.get("title", sid)[:40])
            html += (
                f'<a class="nav-item" onclick="showPage(\'{sid}\')">'
                f'<span class="nav-icon">{icon}</span> {title}</a>\n'
            )
    return html


def render_announcement_card(ann: dict) -> str:
    title = escape_html(ann.get("title", ""))
    detail = escape_html(ann.get("detail", ""))
    significance = escape_html(ann.get("significance", ""))
    return f"""
<div class="announcement-item">
  <div class="ann-title">{title}</div>
  <div class="ann-detail">{detail}</div>
  {'<div class="ann-sig">→ ' + significance + '</div>' if significance else ''}
</div>"""


def render_spec_grid(specs: list[dict]) -> str:
    if not specs:
        return ""
    items = ""
    for s in specs:
        name = escape_html(s.get("name", ""))
        value = escape_html(s.get("value", ""))
        context = escape_html(s.get("context", ""))
        items += f"""
<div class="spec-item">
  <div class="spec-label">{name}</div>
  <div class="spec-value">{value}</div>
  {'<div class="spec-note">' + context + '</div>' if context else ''}
</div>"""
    return f'<div class="spec-grid">{items}</div>'


def render_quote(q: dict) -> str:
    quote = escape_html(q.get("quote", ""))
    speaker = escape_html(q.get("speaker", ""))
    significance = escape_html(q.get("significance", ""))
    return f"""
<div class="quote">
  <div class="quote-text">"{quote}"</div>
  <div class="quote-author">— {speaker}</div>
  {'<div class="quote-sig">' + significance + '</div>' if significance else ''}
</div>"""


def render_insight_box(ins: dict) -> str:
    title = escape_html(ins.get("title", ""))
    insight = escape_html(ins.get("insight", ""))
    implication = escape_html(ins.get("implication", ""))
    return f"""
<div class="insight-box">
  <div class="insight-label">{title}</div>
  <div class="insight-text">{insight}</div>
  {'<div class="insight-impl">💡 ' + implication + '</div>' if implication else ''}
</div>"""


def render_session_page(analysis: dict, session_meta: dict) -> str:
    sid = analysis.get("session_id", "")
    title = escape_html(analysis.get("title", sid))
    subtitle = escape_html(analysis.get("subtitle", ""))
    category = escape_html(analysis.get("category", "General"))
    icon = category_icon(analysis.get("category", "General"))
    badge = badge_class(analysis.get("category", "General"))
    exec_summary = escape_html(analysis.get("executive_summary", ""))
    url = escape_html(session_meta.get("url", f"https://www.youtube.com/watch?v={sid}"))

    speakers_html = ""
    for sp in analysis.get("speakers", []):
        speakers_html += f'<span class="tag">{escape_html(sp)}</span> '

    # 주요 발표
    ann_html = ""
    for ann in analysis.get("key_announcements", []):
        ann_html += render_announcement_card(ann)

    # 스펙
    spec_html = render_spec_grid(analysis.get("technical_specs", []))

    # 인용구
    quotes_html = ""
    for q in analysis.get("key_quotes", []):
        quotes_html += render_quote(q)

    # 데모
    demos_html = ""
    for d in analysis.get("demo_highlights", []):
        demos_html += f'<div class="demo-item">▶ {escape_html(d)}</div>\n'

    # 파트너십
    partners_html = ""
    for p in analysis.get("partnerships_announced", []):
        partner = escape_html(p.get("partner", ""))
        detail = escape_html(p.get("detail", ""))
        partners_html += f'<div class="partner-item"><strong>{partner}</strong> — {detail}</div>\n'

    # BCG 인사이트
    insights_html = ""
    for ins in analysis.get("bcg_insights", []):
        insights_html += render_insight_box(ins)

    # 태그
    tags_html = ""
    for t in analysis.get("tags", []):
        tags_html += f'<span class="tag">{escape_html(t)}</span> '

    # 분석 메타
    meta = analysis.get("_meta", {})
    analyzed_at = meta.get("analyzed_at", "")[:10]
    input_tokens = f"{meta.get('input_tokens', 0):,}"
    output_tokens = f"{meta.get('output_tokens', 0):,}"

    return f"""
<div id="page-{escape_html(sid)}" class="page">
  <div class="section-eyebrow">{icon} {category}</div>
  <div class="section-title">{title}</div>
  <div class="section-desc">{subtitle}</div>

  <div style="display:flex;gap:12px;align-items:center;margin-bottom:24px;flex-wrap:wrap">
    <span class="badge {badge}">{icon} {category}</span>
    {speakers_html}
    <a href="{url}" target="_blank" style="color:var(--accent2);font-size:12px;text-decoration:none">▶ YouTube 영상 →</a>
  </div>

  {'<div class="card"><div class="card-title">Executive Summary</div><div class="content-body" style="margin-top:12px"><p>' + exec_summary + '</p></div></div>' if exec_summary else ''}

  {('<div class="card"><div class="card-title">주요 발표 사항</div><div style="margin-top:12px">' + ann_html + '</div></div>') if ann_html else ''}

  {('<div class="card"><div class="card-title">기술 사양</div>' + spec_html + '</div>') if spec_html else ''}

  {('<div class="card"><div class="card-title">주요 인용구</div><div style="margin-top:12px">' + quotes_html + '</div></div>') if quotes_html else ''}

  {('<div class="card"><div class="card-title">데모 하이라이트</div><div style="margin-top:12px">' + demos_html + '</div></div>') if demos_html else ''}

  {('<div class="card"><div class="card-title">파트너십 발표</div><div style="margin-top:12px">' + partners_html + '</div></div>') if partners_html else ''}

  {('<div style="margin-top:4px">' + insights_html + '</div>') if insights_html else ''}

  {'<div class="tags" style="margin-top:20px">' + tags_html + '</div>' if tags_html else ''}

  <div style="margin-top:24px;padding:12px 16px;background:var(--surface2);border-radius:8px;font-size:11px;color:var(--text-dim)">
    분석: claude-opus-4-6 · 입력 {input_tokens} 토큰 / 출력 {output_tokens} 토큰 · {analyzed_at}
  </div>
</div>"""


def render_overview_page(analyses: list[dict]) -> str:
    total = len(analyses)
    categories = {}
    for a in analyses:
        cat = a.get("category", "General")
        categories[cat] = categories.get(cat, 0) + 1

    # 카테고리 배지들
    cat_badges = ""
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        icon = category_icon(cat)
        badge = badge_class(cat)
        cat_badges += f'<span class="badge {badge}">{icon} {cat} ({count})</span> '

    # 세션 카드들
    session_cards = ""
    for a in analyses:
        sid = escape_html(a.get("session_id", ""))
        title = escape_html(a.get("title", sid)[:55])
        subtitle = escape_html(a.get("subtitle", "")[:80])
        cat = a.get("category", "General")
        icon = category_icon(cat)
        badge = badge_class(cat)
        exec_sum = escape_html(a.get("executive_summary", "")[:150])

        # 주요 발표 수
        ann_count = len(a.get("key_announcements", []))
        ins_count = len(a.get("bcg_insights", []))

        session_cards += f"""
<div class="card" style="cursor:pointer" onclick="showPageById('{sid}')">
  <div class="card-header">
    <div>
      <div class="card-title">{icon} {title}</div>
      <div class="card-subtitle">{subtitle}</div>
    </div>
    <span class="badge {badge}">{escape_html(cat)}</span>
  </div>
  <div class="content-body"><p>{exec_sum}...</p></div>
  <div style="margin-top:12px;display:flex;gap:12px">
    {'<span style="font-size:11px;color:var(--accent)">■ 주요 발표 ' + str(ann_count) + '건</span>' if ann_count else ''}
    {'<span style="font-size:11px;color:var(--accent2)">● 인사이트 ' + str(ins_count) + '건</span>' if ins_count else ''}
  </div>
</div>"""

    now = datetime.now().strftime("%Y년 %m월 %d일")

    return f"""
<div id="page-overview" class="page active">
  <div class="hero">
    <div class="hero-eyebrow">BCG Intelligence Brief · AI 기반 자동 분석</div>
    <div class="hero-title">NVIDIA GTC 2026:<br>The Inference Inflection Point</div>
    <div class="hero-sub">
      Claude API(claude-opus-4-6)가 NVIDIA 공식 YouTube 영상 트랜스크립트를 직접 분석한 결과입니다.
      행사에 참석하지 않은 분도 핵심 내용을 이해할 수 있도록 구성했습니다.
    </div>
    <div class="hero-stats">
      <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">분석된 세션</div></div>
      <div class="stat"><div class="stat-num">{len(categories)}</div><div class="stat-label">카테고리</div></div>
      <div class="stat"><div class="stat-num">GPT-4o</div><div class="stat-label">→ Inference Era</div></div>
      <div class="stat"><div class="stat-num">{now}</div><div class="stat-label">분석 일자</div></div>
    </div>
  </div>

  <div style="margin-bottom:24px;display:flex;flex-wrap:wrap;gap:8px">
    {cat_badges}
  </div>

  <div class="section-eyebrow">세션별 분석 요약</div>
  <div class="section-title">모든 세션</div>
  <div class="grid-2" style="margin-top:20px">
    {session_cards}
  </div>
</div>"""


def build_html(analyses: list[dict], sessions: list[dict]) -> str:
    session_map = {s["id"]: s for s in sessions}

    nav_html = render_nav_items(analyses)
    overview_html = render_overview_page(analyses)

    session_pages_html = ""
    for a in analyses:
        sid = a.get("session_id", "")
        meta = session_map.get(sid, {})
        session_pages_html += render_session_page(a, meta)

    # JavaScript: nav 클릭 핸들러
    nav_items_js = ""
    for a in analyses:
        sid = a.get("session_id", "")
        nav_items_js += f'  pageToNavMap["{escape_html(sid)}"] = null;\n'

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NVIDIA GTC 2026 — BCG Intelligence Brief</title>
<style>
  :root {{
    --bg: #0a0a0f;
    --surface: #12121a;
    --surface2: #1a1a26;
    --border: #2a2a3a;
    --accent: #76b900;
    --accent2: #00a3e0;
    --accent3: #ff6b35;
    --text: #e8e8f0;
    --text-dim: #8888aa;
    --text-bright: #ffffff;
    --red: #ff4757;
    --gold: #ffd700;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--text); font-family:'Segoe UI',system-ui,sans-serif; display:flex; min-height:100vh; }}
  #sidebar {{
    width:280px; min-width:280px; background:var(--surface); border-right:1px solid var(--border);
    position:fixed; top:0; left:0; height:100vh; overflow-y:auto; z-index:100; display:flex; flex-direction:column;
  }}
  .sidebar-header {{ padding:24px 20px 16px; border-bottom:1px solid var(--border); }}
  .sidebar-logo {{ font-size:11px; font-weight:700; letter-spacing:3px; color:var(--accent); text-transform:uppercase; margin-bottom:6px; }}
  .sidebar-title {{ font-size:17px; font-weight:700; color:var(--text-bright); }}
  .sidebar-date {{ font-size:11px; color:var(--text-dim); margin-top:4px; }}
  .sidebar-nav {{ padding:12px 0; flex:1; }}
  .nav-section {{ padding:8px 20px 4px; font-size:10px; font-weight:700; letter-spacing:2px; color:var(--text-dim); text-transform:uppercase; }}
  .nav-item {{
    display:flex; align-items:center; gap:10px; padding:10px 20px; cursor:pointer;
    border-left:3px solid transparent; transition:all 0.15s; font-size:13px; color:var(--text-dim); text-decoration:none;
  }}
  .nav-item:hover {{ background:var(--surface2); color:var(--text); border-left-color:var(--border); }}
  .nav-item.active {{ background:var(--surface2); color:var(--accent); border-left-color:var(--accent); }}
  .nav-icon {{ font-size:15px; min-width:20px; text-align:center; }}
  .sidebar-footer {{ padding:16px 20px; border-top:1px solid var(--border); font-size:11px; color:var(--text-dim); }}
  #main {{ margin-left:280px; flex:1; }}
  .page {{ display:none; padding:40px 48px; max-width:1200px; }}
  .page.active {{ display:block; }}
  .hero {{ background:linear-gradient(135deg,#0d1f0d 0%,#0a0a1f 50%,#1a0a00 100%); border:1px solid var(--border); border-radius:12px; padding:48px; margin-bottom:32px; position:relative; overflow:hidden; }}
  .hero::before {{ content:''; position:absolute; top:-50%; right:-10%; width:500px; height:500px; background:radial-gradient(circle,rgba(118,185,0,0.08) 0%,transparent 70%); }}
  .hero-eyebrow {{ font-size:11px; font-weight:700; letter-spacing:3px; color:var(--accent); text-transform:uppercase; margin-bottom:12px; }}
  .hero-title {{ font-size:36px; font-weight:800; color:var(--text-bright); line-height:1.2; margin-bottom:12px; }}
  .hero-sub {{ font-size:15px; color:var(--text-dim); max-width:600px; line-height:1.7; }}
  .hero-stats {{ display:flex; gap:32px; margin-top:32px; flex-wrap:wrap; }}
  .stat-num {{ font-size:26px; font-weight:800; color:var(--accent); }}
  .stat-label {{ font-size:11px; color:var(--text-dim); margin-top:2px; }}
  .section-eyebrow {{ font-size:10px; font-weight:700; letter-spacing:3px; color:var(--accent); text-transform:uppercase; margin-bottom:8px; }}
  .section-title {{ font-size:24px; font-weight:800; color:var(--text-bright); margin-bottom:6px; }}
  .section-desc {{ font-size:14px; color:var(--text-dim); line-height:1.6; margin-bottom:28px; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:28px; margin-bottom:20px; transition:border-color 0.2s; }}
  .card:hover {{ border-color:rgba(118,185,0,0.4); }}
  .card-header {{ display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:16px; gap:16px; }}
  .card-title {{ font-size:17px; font-weight:700; color:var(--text-bright); line-height:1.3; }}
  .card-subtitle {{ font-size:12px; color:var(--text-dim); margin-top:4px; }}
  .badge {{ display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; white-space:nowrap; }}
  .badge-green {{ background:rgba(118,185,0,0.15); color:var(--accent); border:1px solid rgba(118,185,0,0.3); }}
  .badge-blue {{ background:rgba(0,163,224,0.15); color:var(--accent2); border:1px solid rgba(0,163,224,0.3); }}
  .badge-orange {{ background:rgba(255,107,53,0.15); color:var(--accent3); border:1px solid rgba(255,107,53,0.3); }}
  .badge-red {{ background:rgba(255,71,87,0.15); color:var(--red); border:1px solid rgba(255,71,87,0.3); }}
  .badge-gold {{ background:rgba(255,215,0,0.1); color:var(--gold); border:1px solid rgba(255,215,0,0.3); }}
  .content-body {{ font-size:14px; color:var(--text); line-height:1.8; }}
  .content-body p {{ margin-bottom:12px; }}
  .content-body strong {{ color:var(--text-bright); }}
  .spec-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:16px 0; }}
  .spec-item {{ background:var(--surface2); border:1px solid var(--border); border-radius:8px; padding:14px 16px; }}
  .spec-label {{ font-size:10px; font-weight:700; letter-spacing:1px; color:var(--text-dim); text-transform:uppercase; margin-bottom:4px; }}
  .spec-value {{ font-size:15px; font-weight:700; color:var(--text-bright); }}
  .spec-note {{ font-size:11px; color:var(--accent); margin-top:2px; }}
  .insight-box {{ background:linear-gradient(135deg,rgba(118,185,0,0.05),rgba(0,163,224,0.05)); border:1px solid rgba(118,185,0,0.2); border-radius:10px; padding:20px 24px; margin:16px 0; }}
  .insight-label {{ font-size:11px; font-weight:700; letter-spacing:1px; color:var(--accent); text-transform:uppercase; margin-bottom:10px; }}
  .insight-text {{ font-size:14px; color:var(--text); line-height:1.8; }}
  .insight-impl {{ font-size:13px; color:var(--accent2); margin-top:10px; line-height:1.6; }}
  .quote {{ border-left:3px solid var(--accent); padding:12px 20px; margin:16px 0; background:var(--surface2); border-radius:0 8px 8px 0; }}
  .quote-text {{ font-size:15px; color:var(--text-bright); font-style:italic; line-height:1.6; }}
  .quote-author {{ font-size:12px; color:var(--accent); margin-top:8px; font-weight:600; }}
  .quote-sig {{ font-size:12px; color:var(--text-dim); margin-top:4px; }}
  .announcement-item {{ border-bottom:1px solid var(--border); padding:14px 0; }}
  .announcement-item:last-child {{ border-bottom:none; }}
  .ann-title {{ font-size:14px; font-weight:700; color:var(--text-bright); margin-bottom:4px; }}
  .ann-detail {{ font-size:13px; color:var(--text); line-height:1.6; margin-bottom:4px; }}
  .ann-sig {{ font-size:12px; color:var(--accent2); }}
  .demo-item {{ padding:8px 0; border-bottom:1px solid var(--border); font-size:13px; color:var(--text); }}
  .partner-item {{ padding:8px 0; border-bottom:1px solid var(--border); font-size:13px; color:var(--text); }}
  .tags {{ display:flex; flex-wrap:wrap; gap:6px; }}
  .tag {{ background:var(--surface2); border:1px solid var(--border); color:var(--text-dim); font-size:11px; padding:3px 10px; border-radius:20px; }}
  .grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  ::-webkit-scrollbar {{ width:6px; }}
  ::-webkit-scrollbar-track {{ background:var(--bg); }}
  ::-webkit-scrollbar-thumb {{ background:var(--border); border-radius:3px; }}
  @media (max-width:900px) {{
    #sidebar {{ display:none; }}
    #main {{ margin-left:0; }}
    .page {{ padding:24px 16px; }}
    .grid-2, .spec-grid {{ grid-template-columns:1fr; }}
  }}
</style>
</head>
<body>

<nav id="sidebar">
  <div class="sidebar-header">
    <div class="sidebar-logo">NVIDIA GTC 2026</div>
    <div class="sidebar-title">BCG Intelligence Brief</div>
    <div class="sidebar-date">Claude API 자동 분석 · March 2026</div>
  </div>
  <div class="sidebar-nav">
    <div class="nav-section">Overview</div>
    <a class="nav-item active" id="nav-overview" onclick="showPage('overview')">
      <span class="nav-icon">🏠</span> 전체 요약
    </a>
    {nav_html}
  </div>
  <div class="sidebar-footer">
    claude-opus-4-6 · adaptive thinking<br>
    GTC 2026 공식 YouTube 기반
  </div>
</nav>

<main id="main">
  {overview_html}
  {session_pages_html}
</main>

<script>
const allNavItems = document.querySelectorAll('.nav-item');

function showPage(id) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  allNavItems.forEach(n => n.classList.remove('active'));

  const page = document.getElementById('page-' + id);
  if (page) page.classList.add('active');

  const navItem = document.getElementById('nav-' + id);
  if (navItem) {{
    navItem.classList.add('active');
  }} else {{
    // nav-item 중 onclick에 id 포함된 것 찾기
    allNavItems.forEach(n => {{
      if (n.getAttribute('onclick') && n.getAttribute('onclick').includes("'" + id + "'")) {{
        n.classList.add('active');
      }}
    }});
  }}
  window.scrollTo(0, 0);
}}

function showPageById(id) {{
  showPage(id);
}}

// overview nav 클릭 이벤트 위임
document.querySelector('#nav-overview').addEventListener('click', () => showPage('overview'));
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="GTC 2026 HTML 리포트 생성기")
    parser.add_argument("--out", default="index.html", help="출력 HTML 파일 (기본: index.html)")
    args = parser.parse_args()

    console.print("[cyan]분석 결과 로드 중...[/cyan]")
    analyses = load_all_analyses()
    sessions = load_sessions()

    if not analyses:
        console.print("[yellow]분석 결과가 없습니다.[/yellow]")
        console.print("먼저 실행하세요:")
        console.print("  1. [cyan]python fetch_transcripts.py[/cyan]")
        console.print("  2. [cyan]python analyze_sessions.py[/cyan]")
        return

    console.print(f"[green]✓[/green] 분석 결과 {len(analyses)}개 로드")

    html = build_html(analyses, sessions)

    out_path = Path(args.out)
    out_path.write_text(html, encoding="utf-8")

    console.print(f"\n[bold green]✓ HTML 생성 완료: {out_path}[/bold green]")
    console.print(f"  크기: {out_path.stat().st_size / 1024:.1f} KB")
    console.print(f"  세션: {len(analyses)}개")
    console.print(f"\n브라우저에서 열기: [cyan]open {out_path}[/cyan]")


if __name__ == "__main__":
    main()
