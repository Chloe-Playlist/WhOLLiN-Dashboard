"""
WhOLLiN Dashboard Generator
매일 Google Drive에서 CURRENT.md를 읽어 index.html을 생성합니다.
커버곡은 음악 레퍼토리 시트에서 동적으로 읽어옵니다.
히스토리 스냅샷을 history/ 폴더에 JSON으로 저장합니다.
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
CURRENT_MD_ID  = "1bHcjkC6TKC6guk-6Cp8sdEpKiTUlZXdr"
COVER_SHEET_ID = "12D74nA7JngO5CDWPZPlpLxYX12armPEihleXOuGjM2g"
COVER_SHEET_GID = 911213125

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]
KST = timezone(timedelta(hours=9))

# 멤버 영문명 매핑 (이름은 안 바뀌므로 여기만 유지)
MEMBER_EN = {
    "시오": "SiO",
    "태이": "TAEI",
    "이소": "IISO",
    "이언": "EON",
    "강우": "KANGWOO",
}

# ── 인증
def get_credentials():
    key_json = os.environ["GOOGLE_SERVICE_ACCOUNT_KEY"]
    info = json.loads(key_json)
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

# ── CURRENT.md 읽기
def fetch_current_md(creds):
    service = build("drive", "v3", credentials=creds)
    request = service.files().get_media(fileId=CURRENT_MD_ID)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue().decode("utf-8")

# ── 커버곡 시트 읽기
def fetch_cover_songs(creds):
    try:
        sheets = build("sheets", "v4", credentials=creds)

        # gid로 시트 탭 이름 찾기
        meta = sheets.spreadsheets().get(spreadsheetId=COVER_SHEET_ID).execute()
        sheet_name = None
        for s in meta.get("sheets", []):
            if s["properties"]["sheetId"] == COVER_SHEET_GID:
                sheet_name = s["properties"]["title"]
                break

        if not sheet_name:
            print("  ⚠️  커버곡 시트 탭을 찾을 수 없음. 기본값 사용.")
            return []

        result = sheets.spreadsheets().values().get(
            spreadsheetId=COVER_SHEET_ID,
            range=f"{sheet_name}!A:P"
        ).execute()

        rows = result.get("values", [])
        if len(rows) < 2:
            return []

        headers = [h.strip() for h in rows[0]]
        covers_by_member = {}

        for row in rows[1:]:
            row_dict = dict(zip(headers, row + [""] * (len(headers) - len(row))))
            performer  = row_dict.get("performer_scope", "").strip()
            song_type  = row_dict.get("song_type", "").strip()
            song_title = row_dict.get("song_title", "").strip()
            artist     = row_dict.get("artist_original", "").strip()

            if song_type == "cover" and performer not in ("전체", "") and song_title:
                covers_by_member[performer] = f"{artist} · {song_title}" if artist else song_title

        # 멤버 순서 유지
        result_list = []
        for kr, en in MEMBER_EN.items():
            result_list.append({
                "name": kr,
                "en": en,
                "cover": covers_by_member.get(kr, "미정"),
            })

        print(f"  커버곡 {len(covers_by_member)}개 로드됨")
        return result_list

    except Exception as e:
        print(f"  ⚠️  커버곡 시트 읽기 실패: {e}")
        return []

# ── 마크다운 파싱
def parse_current(md, members_cover):
    data = {
        "d_day": "?",
        "basis_date": "",
        "debut_date": "2026-09-01",
        "top_priorities": [],
        "recent_confirmed": [],
        "upcoming_dates": [],
        "members_cover": members_cover,
    }

    # D-day 추출
    m = re.search(r"D-(\d+)", md)
    if m:
        data["d_day"] = m.group(1)

    # 기준일 추출
    m = re.search(r"Basis date:\s*(\d{4}-\d{2}-\d{2})", md)
    if m:
        data["basis_date"] = m.group(1)
    else:
        m = re.search(r"source_basis_date:\s*(\d{4}-\d{2}-\d{2})", md)
        if m:
            data["basis_date"] = m.group(1)

    # Key Milestones → upcoming_dates
    milestone_section = re.search(r"## Key Milestones\n(.*?)(?=\n##|\Z)", md, re.DOTALL)
    if milestone_section:
        items = re.findall(r"-\s+(\d{4})-(\d{2})-(\d{2}):\s+(.+)", milestone_section.group(1))
        for _, month, day, event in items:
            data["upcoming_dates"].append({
                "date": f"{int(month)}/{int(day)}",
                "event": event.strip()[:50]
            })
            if len(data["upcoming_dates"]) >= 6:
                break

    # Active Workstreams → top_priorities
    workstream_section = re.search(r"## Active Workstreams\n(.*?)(?=\n##|\Z)", md, re.DOTALL)
    if workstream_section:
        items = re.findall(r"-\s+[^:]+:\s+(.+)", workstream_section.group(1))
        for item in items:
            first = item.split(',')[0].strip()
            if first:
                data["top_priorities"].append(first[:60])
            if len(data["top_priorities"]) >= 6:
                break

    # Confirmed/Changed → recent_confirmed
    confirmed_section = re.search(r"## Confirmed.*?\n(.*?)(?=\n##|\Z)", md, re.DOTALL)
    if confirmed_section:
        items = re.findall(r"-\s+`(?:확정|완료)`:\s+(.+?)(?=\n-|\Z)", confirmed_section.group(1), re.DOTALL)
        for item in items:
            clean = item.strip().replace('\n', ' ')[:60]
            if clean:
                data["recent_confirmed"].append(clean)
            if len(data["recent_confirmed"]) >= 4:
                break

    return data

# ── 히스토리 스냅샷 저장
def save_history(data, today_str):
    os.makedirs("history", exist_ok=True)

    snapshot = {k: v for k, v in data.items() if k != "members_cover"}
    snapshot["saved_at"] = today_str
    with open(f"history/{today_str}.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    manifest_path = "history/index.json"
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = []

    if today_str not in manifest:
        manifest.append(today_str)
        manifest.sort(reverse=True)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)

    print(f"  히스토리 저장: history/{today_str}.json (총 {len(manifest)}일)")

# ── HTML 생성
def render_html(data, today_str):
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    members_html = "".join(
        f'''<div class="member-card">
          <div class="member-name">{m["name"]}</div>
          <div class="member-en">{m["en"]}</div>
          <div class="member-cover">{m["cover"]}</div>
        </div>'''
        for m in data["members_cover"]
    )

    today_json = json.dumps({
        "d_day": data["d_day"],
        "basis_date": data["basis_date"],
        "debut_date": data["debut_date"],
        "top_priorities": data["top_priorities"],
        "recent_confirmed": data["recent_confirmed"],
        "upcoming_dates": data["upcoming_dates"],
    }, ensure_ascii=False)

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
  .tabs {{
    display: flex;
    gap: 8px;
    margin-bottom: 14px;
  }}
  .tab-btn {{
    padding: 7px 18px;
    border-radius: 20px;
    border: 1px solid #ddd;
    background: white;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    color: #888;
  }}
  .tab-btn.active {{
    background: #111;
    color: white;
    border-color: #111;
  }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  .history-bar {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
  }}
  .history-bar select {{
    padding: 7px 12px;
    border-radius: 8px;
    border: 1px solid #ddd;
    font-size: 13px;
    background: white;
    cursor: pointer;
  }}
  .history-bar label {{ font-size: 13px; color: #666; }}
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
  .loading {{ color: #bbb; font-size: 13px; padding: 20px 0; text-align: center; }}
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

<div class="tabs">
  <button class="tab-btn active" onclick="switchTab('today')">오늘</button>
  <button class="tab-btn" onclick="switchTab('history')">히스토리</button>
</div>

<div id="tab-today" class="tab-panel active">
  <div class="grid" id="today-grid"></div>
  <div class="card" style="margin-bottom:14px">
    <div class="card-title">🎤 멤버 커버곡</div>
    <div class="members-grid">{members_html}</div>
  </div>
</div>

<div id="tab-history" class="tab-panel">
  <div class="history-bar">
    <label>날짜 선택</label>
    <select id="history-select" onchange="loadHistory(this.value)">
      <option value="">불러오는 중...</option>
    </select>
  </div>
  <div id="history-grid" class="grid"></div>
</div>

<div class="updated">마지막 업데이트: {now_kst} · PLAYLIST WhOLLiN</div>

<script>
const TODAY_DATA = {today_json};

function renderGrid(data, containerId) {{
  const priorities = (data.top_priorities || []).map(i =>
    `<div class="priority-item"><span class="dot"></span><span>${{i}}</span></div>`
  ).join('') || '<div class="empty">항목 없음</div>';
  const confirmed = (data.recent_confirmed || []).map(i =>
    `<div class="confirmed-item"><span class="check">✓</span><span>${{i}}</span></div>`
  ).join('') || '<div class="empty">항목 없음</div>';
  const dates = (data.upcoming_dates || []).map(d =>
    `<div class="date-item"><span class="date-tag">${{d.date}}</span><span>${{d.event}}</span></div>`
  ).join('') || '<div class="empty">임박 일정 없음</div>';

  document.getElementById(containerId).innerHTML = `
    <div class="card"><div class="card-title">🔴 최우선 과제</div>${{priorities}}</div>
    <div class="card"><div class="card-title">📅 임박 일정</div>${{dates}}</div>
    <div class="card"><div class="card-title">✅ 최근 완료</div>${{confirmed}}</div>
    <div class="card">
      <div class="card-title">📋 기준일</div>
      <div style="font-size:20px;font-weight:800;padding:10px 0">${{data.basis_date || '-'}}</div>
      <div style="font-size:12px;color:#888">D-${{data.d_day}} · 데뷔 ${{data.debut_date}}</div>
    </div>
  `;
}}

function switchTab(tab) {{
  document.querySelectorAll('.tab-btn').forEach((b, i) => {{
    b.classList.toggle('active', (i === 0) === (tab === 'today'));
  }});
  document.getElementById('tab-today').classList.toggle('active', tab === 'today');
  document.getElementById('tab-history').classList.toggle('active', tab === 'history');
  if (tab === 'history') loadManifest();
}}

function loadManifest() {{
  fetch('history/index.json?t=' + Date.now())
    .then(r => r.json())
    .then(dates => {{
      const sel = document.getElementById('history-select');
      sel.innerHTML = dates.map(d => `<option value="${{d}}">${{d}}</option>`).join('');
      if (dates.length > 0) loadHistory(dates[0]);
    }})
    .catch(() => {{
      document.getElementById('history-select').innerHTML = '<option>히스토리 없음</option>';
    }});
}}

function loadHistory(date) {{
  if (!date) return;
  document.getElementById('history-grid').innerHTML = '<div class="loading">불러오는 중...</div>';
  fetch(`history/${{date}}.json?t=` + Date.now())
    .then(r => r.json())
    .then(data => renderGrid(data, 'history-grid'))
    .catch(() => {{
      document.getElementById('history-grid').innerHTML = '<div class="empty">데이터를 불러올 수 없습니다.</div>';
    }});
}}

renderGrid(TODAY_DATA, 'today-grid');
</script>
</body>
</html>"""

# ── 메인
if __name__ == "__main__":
    today_str = datetime.now(KST).strftime("%Y-%m-%d")

    print("Google 인증 중...")
    creds = get_credentials()

    print("커버곡 시트 읽는 중...")
    members_cover = fetch_cover_songs(creds)

    print("CURRENT.md 읽는 중...")
    md = fetch_current_md(creds)

    print("파싱 중...")
    data = parse_current(md, members_cover)
    print(f"  D-{data['d_day']} | 우선순위 {len(data['top_priorities'])}개 | 일정 {len(data['upcoming_dates'])}개")

    print("히스토리 저장 중...")
    save_history(data, today_str)

    print("HTML 생성 중...")
    html = render_html(data, today_str)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("완료! index.html 저장됨")
