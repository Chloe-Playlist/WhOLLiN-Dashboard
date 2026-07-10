# WhOLLiN Dashboard 세팅 가이드

배포 URL: `https://chloe-playlist.github.io/WhOLLiN-Dashboard`  
매일 오전 9시(KST) 자동 업데이트됩니다.

---

## 1단계 — Google Service Account 만들기 (10분)

1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. 상단 프로젝트 선택 → **새 프로젝트** → 이름: `whollin-dashboard` → 만들기
3. 왼쪽 메뉴 → **API 및 서비스** → **라이브러리**
4. `Google Drive API` 검색 → **사용 설정**
5. 왼쪽 메뉴 → **API 및 서비스** → **사용자 인증 정보**
6. **+ 사용자 인증 정보 만들기** → **서비스 계정**
7. 이름: `whollin-reader` → **만들고 계속하기** → **완료**
8. 생성된 서비스 계정 클릭 → **키** 탭 → **키 추가** → **새 키 만들기** → **JSON** → **만들기**
9. JSON 파일이 다운로드됨 (이게 바로 `GOOGLE_SERVICE_ACCOUNT_KEY`)

---

## 2단계 — CURRENT.md를 서비스 계정과 공유

1. Google Drive에서 `00_README_INDEX` 폴더의 `CURRENT.md` 파일 우클릭 → **공유**
2. 서비스 계정 이메일 입력 (JSON 파일 안의 `client_email` 값, 예: `whollin-reader@whollin-dashboard.iam.gserviceaccount.com`)
3. 권한: **뷰어** → **완료**

---

## 3단계 — GitHub Secret 등록

1. [repo Settings](https://github.com/Chloe-Playlist/WhOLLiN-Dashboard/settings/secrets/actions) 접속
2. **New repository secret** 클릭
3. Name: `GOOGLE_SERVICE_ACCOUNT_KEY`
4. Secret: 다운로드한 JSON 파일 내용을 **전체 복사**해서 붙여넣기
5. **Add secret**

---

## 4단계 — GitHub Pages 활성화

1. repo [Settings → Pages](https://github.com/Chloe-Playlist/WhOLLiN-Dashboard/settings/pages)
2. Source: **Deploy from a branch**
3. Branch: **main** / **/ (root)** → **Save**

---

## 5단계 — 첫 실행

1. repo → **Actions** 탭
2. `Update WhOLLiN Dashboard` 워크플로우 클릭
3. **Run workflow** → **Run workflow**
4. 1~2분 후 `https://chloe-playlist.github.io/WhOLLiN-Dashboard` 접속 확인

---

이후에는 매일 오전 9시에 자동으로 업데이트됩니다.
