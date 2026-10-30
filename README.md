# 동아리 출결·활동일지 관리 프로그램

IT 동아리(기능반) 학생들의 **출결(입실·퇴실·조퇴)** 과 **활동일지**를 기록하고, 교사가 확인·관리할 수 있는 프로그램입니다.
Ubuntu Server 환경에서 동작하는 CLI(터미널 메뉴) 버전입니다.

<img width="1903" height="968" alt="image" src="https://github.com/user-attachments/assets/32228e6a-73a2-4ee9-bd4e-f19b37d53dbd" />

## 주요 기능

| 사용자 | 기능 |
|---|---|
| 학생 (학번 로그인) | 입실 · 퇴실(종료 시간 전이면 조퇴 + 사유) · 활동일지 작성(분야 태그 여러 개) · 내 일지 조회 |
| 교사 (이름 + 비밀번호) | 날짜별 출결표 · 활동일지 조회/확인 처리 · 결석 처리 · 학생 등록/삭제 · 분야 추가 · 교사 추가 |
| 첫 실행 | 등록된 교사가 없으면 관리자 계정 생성 |

## 기술 스택

| 구분 | 사용 |
|---|---|
| 언어 | Python 3 (표준 라이브러리만 사용) |
| DB | SQLite |
| 실행 환경 | Ubuntu Server 26.04 LTS (VirtualBox), SSH 접속 |
| 버전 관리 | Git / GitHub |

## 실행 방법

```bash
git clone https://github.com/network-growth/DB-project.git
cd DB-project
python3 cli.py
```

처음 실행하면 관리자(교사) 계정을 만들고, `club_system.db` 파일이 자동으로 생성됩니다.

## 프로젝트 구조

```
DB-project/
├── db.py      # DB 레이어: 테이블 생성, 출석·일지·교사 인증 등 모든 SQL
├── cli.py     # 화면 레이어: 글자 메뉴, 입력 검사 (SQL 없음)
└── README.md
```

화면(`cli.py`)과 데이터 처리(`db.py`)를 분리해서, 나중에 GUI 화면을 붙여도 `db.py`는 그대로 재사용할 수 있습니다.

## DB 설계

<img width="1289" height="670" alt="image" src="https://github.com/user-attachments/assets/a9248085-5f69-4e8d-8d63-2750a143cc23" />

| 테이블 | 역할 |
|---|---|
| 학생 | 학번(PK), 이름, 학년, 반, 가입일 |
| 교사 | 교사ID(PK), 이름(UNIQUE), 비밀번호해시 |
| 출석 | 날짜별 상태(출석/조퇴/결석), 입실·퇴실 시간, 사유 — `UNIQUE(학번, 날짜)` |
| 활동일지 | 활동내용, 배운 점, 어려웠던 점, 확인교사 |
| 분야 | 네트워크, 리눅스, 윈도우 등 |
| 일지_분야 | 활동일지 ↔ 분야 N:M 연결 |

### 설계하면서 신경 쓴 점

| 문제 | 해결 |
|---|---|
| SQLite는 외래키 검사가 기본 OFF | 연결할 때마다 `PRAGMA foreign_keys = ON` |
| 같은 날 출석이 중복 기록될 수 있음 | `UNIQUE(학번, 날짜)`로 DB 차원에서 차단 |
| 일지 삭제 시 분야 연결이 고아 데이터로 남음 | `ON DELETE CASCADE` |
| 일지 저장 중 일부만 저장될 수 있음 | 일지 + 분야 연결을 하나의 트랜잭션으로 처리 |
| SQL 인젝션 | 모든 쿼리에 `?` 자리표시자 사용 |
| 비밀번호 평문 저장 | 솔트 + PBKDF2-SHA256(20만 회) 해시로 저장 |

## 트러블슈팅

| 문제 | 원인 | 해결 |
|---|---|---|
| VM 콘솔에서 한글이 ◆로 깨짐 | 리눅스 텍스트 콘솔에 한글 폰트 없음 | VirtualBox 포트 포워딩(2222→22) 후 Windows 터미널에서 SSH 접속 |
| 한글 입력 후 `UnicodeDecodeError`로 종료 | 터미널이 백스페이스를 바이트 단위로 처리해 한글이 반쪽만 지워짐 | `stty iutf8` 설정 + 입력 함수에서 예외 처리 후 재입력 |
| Ubuntu Desktop VM 설치 중 멈춤 | 호스트 PC 성능·가상화 환경 제약 | Ubuntu Server(CLI)로 전환 |

## 앞으로 할 것

- [ ] PyInstaller로 실행파일 하나로 묶기
- [ ] cron으로 DB 자동 백업
- [ ] 학생 PIN (대리 출석 방지)
- [ ] 출석률 통계 / CSV 내보내기
- [ ] GUI(CustomTkinter) 화면 추가
