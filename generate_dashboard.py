"""
WhOLLiN Dashboard Generator
매일 Google Drive에서 CURRENT.md를 읽어 index.html을 생성합니다.
"""

import os
import json
import re
from datetime import datetime, timezone, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# ── 설정
FILE_ID = "1bHcjkC6TKC6guk-6Cp8sdEpKiTUlZXdr"  # CURRENT.md
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
KST = timezone(timedelta(hours=9))

# ── Google Drive 인증
def get_drive_service():
    key_json = os.environ["GOOGLE_SERVICE_ACCOUNT_KEY"]
    info = json.loads(key_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

# ── CURRENT.md 읽기
def fetch_current_md(service):
    request = service.files().get_media(fileId=FILE_ID)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue().decode("utf-8")

# ── 마크다운 파싱
def parse_current(md):
    data = {
        "d_day": "?",
        "basis_date": "",
        "debut_date": "2026-09-01",
        "top_priorities": [],
        "recent_confirmed": [],
        "upcoming_dates": [],
        "members_cover": [
            {"name": "시오", "en": "SiO", "cover": "태양 · 눈,코,입"},
            {"name": "태이", "en": "TAEI", "cover": "쥬지 · 바라봐줘요"},
            {"name": "이소", "en": "IISO", "cover": "미세스그린애플 · 아오토나츠"},
            {"name": "이언", "en": "EON", "cover": "카리나 · UP"},
            {"name": "강우", "en": "KANGWOO", "cover": "헤비 · BE I"},
        ],
    }

    # D-day 추출
    m = re.search(r"D-(\d+)", md)
    if m:
        data["d_day"] = m.group(1)

    # 기준일 추출
    m = re.search(r"(\d{4}-\d{2}-\d{2})\(", md)
    if m:
        data["basis_date"] = m.group(1)

    # 최우선 섹션 파싱
    priority_section = re.search(r"최우선.*?\n(.*?)(?=\n##|\Z)", md, re.DOTALL)
    if priority_section:
        items = re.findall(r"\[ \]\s+(.+)", priority_section.group(1))
        data["top_priorities"] = items[:6]

    # 최근 완료 파싱
    confirmed_section = re.search(r"최근 종결.*?\n(.*?)(?=\n##|\Z)", md, re.DOTALL)
    if confirmed_section:
        items = re.findall(r"\*\s+(.+?)(?:\s+—|\n|$)", confirmed_section.group(1))
        data["recent_confirmed"] = [i.strip() for i in items[:4]]

    # 날짜 포함 임박 일정 파싱 (7/숫자 형식)
    date_items = re.findall(r"[\*\-\[\] ]*(?:7/\d+|8/\d+)[^\n]*\n?", md)
    seen = set()
    for item in date_items:
        clean = re.sub(r"[\*\[\] ]", "", item).strip()
        if clean and clean not in seen and len(clean) > 5:
            seen.add(clean)
            m = re.search(r"((?:7|8)/\d+[^\s]*)\s+(.*)", clean)
            if m:
                data["upcoming_dates"].append({"date": m.group(1), "event": m.group(2)[:50]})
        if len(data["upcoming_dates"]) >= 6:
            break

    return data

# ── HTML 생성
def render_html(data):
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    priorities_html = "".join(
        f'<div class="priority-item"><span class="dot"></span><span>{item}</span></div>'
        for item in data["top_priorities"]
    ) or '<div class="empty">항목 없음</div>'

    confirmed_html = "".join(
        f'<div class="confirmed-item"><span class="check">✓</span><span>{item}</span></div>'
        for item in data["recent_confirmed"]
    ) or '<div class="empty">항목 없음</div>'

    dates_html = "".join(
        f'<div class="date-item"><span class="date-tag">{d["date"]}</span><span>{d["event"]}</span></div>'
        for d in data["upcoming_dates"]
    ) or '<div class="empty">임박 일정 없음</div>'

    members_html = "".join(
        f'''<div class="member-card">
          <div class="member-name">{m["name"]}</div>
          <div class="member-en">{m["en"]}</div>
          <div class="member-cover">{m["cover"]}</div>
        </div>'''
        for m in data["members_cover"]
    )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WhOLLiN Dashboard</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, 'Noto Sans KR', sans-serif;
    background: #f8f8f8;
    color: #1a1a1a;
    font-size: 14px;
    line-height: 1.6;
    padding: 20px;
    max-width: 900px;
    margin: 0 auto;
  }}
  .header {{
    background: #111;
    color: white;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .header h1 {{ font-size: 22px; font-weight: 800; letter-spacing: -0.5px; }}
  .header .meta {{ font-size: 12px; color: #aaa; margin-top: 4px; }}
  .dday {{
    background: white;
    color: #111;
    border-radius: 8px;
    padding: 8px 16px;
    text-align: center;
  }}
  .dday .num {{ font-size: 28px; font-weight: 800; line-height: 1; }}
  .dday .label {{ font-size: 10px; color: #888; margin-top: 2px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }}
  @media (max-width: 600px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .card {{
    background: white;
    border-radius: 10px;
    padding: 14px 16px;
    border: 1px solid #e8e8e8;
  }}
  .card-title {{
    font-size: 11px;
    font-weight: 700;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 10px;
  }}
  .priority-item, .confirmed-item, .date-item {{
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 5px 0;
    font-size: 13px;
    border-bottom: 1px solid #f5f5f5;
    line-height: 1.5;
  }}
  .priority-item:last-child, .confirmed-item:last-child, .date-item:last-child {{ border-bottom: none; }}
  .dot {{ width: 7px; height: 7px; border-radius: 50%; background: #ef4444; margin-top: 5px; flex-shrink: 0; }}
  .check {{ color: #22c55e; font-weight: 700; flex-shrink: 0; font-size: 13px; }}
  .date-tag {{
    background: #111;
    color: white;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 4px;
    white-space: nowrap;
    flex-shrink: 0;
    margin-top: 2px;
  }}
  .empty {{ color: #bbb; font-size: 12px; padding: 8px 0; }}
  .members-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
  }}
  @media (max-width: 600px) {{ .members-grid {{ grid-template-columns: repeat(3, 1fr); }} }}
  .member-card {{
    background: #fafafa;
    border-radius: 8px;
    padding: 10px 6px;
    text-align: center;
    border: 1px solid #eee;
  }}
  .member-name {{ font-size: 13px; font-weight: 700; }}
  .member-en {{ font-size: 10px; color: #aaa; margin-top: 2px; }}
  .member-cover {{ font-size: 10px; color: #666; margin-top: 5px; line-height: 1.4; }}
  .updated {{ text-align: right; font-size: 11px; color: #bbb; margin-top: 10px; }}
  .full-col {{ grid-column: 1 / -1; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>WhOLLiN</h1>
    <div class="meta">데뷔 {data['debut_date']} · TIME SLEEP &nbsp;|&nbsp; 기준 {data['basis_date']}</div>
  </div>
  <div class="dday">
    <div class="label">데뷔까지</div>
    <div class="num">D-{data['d_day']}</div>
  </div>
</div>

<div class="grid">
  <div class="card">
    <div class="card-title">🔴 최우선 과제</div>
    {priorities_html}
  </div>
  <div class="card">
    <div class="card-title">📅 임박 일정</div>
    {dates_html}
  </div>
  <div class="card">
    <div class="card-title">✅ 최근 완료</div>
    {confirmed_html}
  </div>
  <div class="card">
    <div class="card-title">🎤 멤버 커버곡</div>
    <div class="members-grid">
      {members_html}
    </div>
  </div>
</div>

<div class="updated">마지막 업데이트: {now_kst} · PLAYLIST WhOLLiN</div>

</body>
</html>"""

# ── 메인
if __name__ == "__main__":
    print("Google Drive 연결 중...")
    service = get_drive_service()

    print("CURRENT.md 읽는 중...")
    md = fetch_current_md(service)

    print("파싱 중...")
    data = parse_current(md)
    print(f"  D-{data['d_day']} | 우선순위 {len(data['top_priorities'])}개 | 일정 {len(data['upcoming_dates'])}개")

    print("HTML 생성 중...")
    html = render_html(data)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("완료! index.html 저장됨")
