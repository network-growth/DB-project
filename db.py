"""
db.py - 동아리 출결·활동일지 관리 프로그램의 DB 레이어

규칙: 화면(GUI) 파일에는 SQL을 쓰지 않는다.
      화면은 이 파일의 함수만 호출한다. (예: db.check_in("20101"))
"""

import hashlib
import os
import secrets
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime


# ─────────────────────────────────────────────
# 1. 설정값
# ─────────────────────────────────────────────

def _base_dir():
    """DB 파일을 둘 폴더를 찾는다.
    - exe로 실행 중이면: exe 파일이 있는 폴더
    - .py로 실행 중이면: 이 파일이 있는 폴더
    (exe --onefile은 임시폴더에서 돌아서, 그냥 두면 DB가 매번 사라짐)
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DB_PATH = os.path.join(_base_dir(), "club_system.db")

# 동아리 끝나는 시간. 이 시간 전에 퇴실하면 '조퇴'로 기록됨
CLUB_END_TIME = "18:00"

# 처음 실행할 때 자동으로 들어갈 분야
DEFAULT_FIELDS = ["네트워크", "리눅스", "윈도우"]


# ─────────────────────────────────────────────
# 2. 테이블 정의
# ─────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS 학생 (
    학번   CHAR(5) PRIMARY KEY,
    이름   VARCHAR(20) NOT NULL,
    학년   INT,
    반     INT,
    가입일 DATE
);

CREATE TABLE IF NOT EXISTS 교사 (
    교사ID       INTEGER PRIMARY KEY AUTOINCREMENT,
    이름         VARCHAR(20) NOT NULL UNIQUE,
    비밀번호해시 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS 출석 (
    출석ID   INTEGER PRIMARY KEY AUTOINCREMENT,
    학번     CHAR(5) NOT NULL REFERENCES 학생(학번) ON DELETE CASCADE,
    날짜     DATE NOT NULL,
    상태     VARCHAR(10) NOT NULL,      -- 출석 / 조퇴 / 결석
    입실시간 TIME,
    퇴실시간 TIME,
    사유     VARCHAR(100),
    UNIQUE (학번, 날짜)                 -- 같은 날 두 번 출석 금지
);

CREATE TABLE IF NOT EXISTS 활동일지 (
    일지ID     INTEGER PRIMARY KEY AUTOINCREMENT,
    학번       CHAR(5) NOT NULL REFERENCES 학생(학번) ON DELETE CASCADE,
    날짜       DATE NOT NULL,
    활동내용   TEXT NOT NULL,
    배운점     TEXT,
    어려웠던점 TEXT,
    확인교사ID INT REFERENCES 교사(교사ID) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS 분야 (
    분야ID INTEGER PRIMARY KEY AUTOINCREMENT,
    분야명 VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS 일지_분야 (
    일지ID INT REFERENCES 활동일지(일지ID) ON DELETE CASCADE,
    분야ID INT REFERENCES 분야(분야ID) ON DELETE CASCADE,
    PRIMARY KEY (일지ID, 분야ID)
);
"""


# ─────────────────────────────────────────────
# 3. 공통 도구
# ─────────────────────────────────────────────

@contextmanager
def get_conn():
    """DB 연결을 열고, 끝나면 알아서 저장(commit)하고 닫아준다.
    중간에 에러가 나면 지금까지 한 작업을 전부 취소(rollback)한다.

    사용법:
        with get_conn() as conn:
            conn.execute(...)
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # 결과를 row["이름"]처럼 꺼낼 수 있게
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite는 외래키 검사가 기본 OFF
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _now_time():
    return datetime.now().strftime("%H:%M")


def _to_dicts(rows):
    """sqlite3.Row 목록을 일반 dict 목록으로 바꾼다 (print·화면 표시 편하게)."""
    return [dict(r) for r in rows]


def _hash_password(password, salt=None):
    """비밀번호를 해시로 바꾼다. 결과 형식: '솔트$해시'
    - 솔트: 사람마다 다른 랜덤값. 같은 비번이라도 해시가 달라짐
    - pbkdf2: 일부러 20만 번 반복해서 무차별 대입을 느리게 만듦
    """
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 200_000
    ).hex()
    return f"{salt}${digest}"


def _verify_password(password, stored):
    salt = stored.split("$", 1)[0]
    return secrets.compare_digest(_hash_password(password, salt), stored)


# ─────────────────────────────────────────────
# 4. 초기화
# ─────────────────────────────────────────────

def init_db():
    """테이블을 만들고 기본 분야를 넣는다. 여러 번 실행해도 안전하다."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO 분야 (분야명) VALUES (?)",
            [(name,) for name in DEFAULT_FIELDS],
        )


# ─────────────────────────────────────────────
# 5. 학생
# ─────────────────────────────────────────────

def add_student(student_id, name, grade, class_no, joined=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO 학생 (학번, 이름, 학년, 반, 가입일) VALUES (?, ?, ?, ?, ?)",
            (student_id, name, grade, class_no, joined or _today()),
        )


def get_student(student_id):
    """학번으로 학생 1명 조회. 없으면 None (로그인 확인용)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM 학생 WHERE 학번 = ?", (student_id,)
        ).fetchone()
    return dict(row) if row else None


def list_students():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM 학생 ORDER BY 학번").fetchall()
    return _to_dicts(rows)


def update_student(student_id, name, grade, class_no):
    with get_conn() as conn:
        conn.execute(
            "UPDATE 학생 SET 이름 = ?, 학년 = ?, 반 = ? WHERE 학번 = ?",
            (name, grade, class_no, student_id),
        )


def delete_student(student_id):
    """학생 삭제. 그 학생의 출석·일지도 같이 지워진다 (ON DELETE CASCADE)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM 학생 WHERE 학번 = ?", (student_id,))


# ─────────────────────────────────────────────
# 6. 교사
# ─────────────────────────────────────────────

def add_teacher(name, password):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO 교사 (이름, 비밀번호해시) VALUES (?, ?)",
            (name, _hash_password(password)),
        )
        return cur.lastrowid


def verify_teacher(name, password):
    """이름·비번이 맞으면 교사 정보(dict), 틀리면 None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM 교사 WHERE 이름 = ?", (name,)
        ).fetchone()
    if row and _verify_password(password, row["비밀번호해시"]):
        return {"교사ID": row["교사ID"], "이름": row["이름"]}
    return None


def has_teacher():
    """교사가 한 명이라도 등록돼 있는지 (첫 실행 때 관리자 만들기용)."""
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM 교사 LIMIT 1").fetchone() is not None


# ─────────────────────────────────────────────
# 7. 출석
# ─────────────────────────────────────────────

def check_in(student_id):
    """오늘 입실 기록. 결과: (성공여부, 메시지)"""
    if get_student(student_id) is None:
        return False, "등록되지 않은 학번이에요."

    now = _now_time()
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO 출석 (학번, 날짜, 상태, 입실시간) VALUES (?, ?, '출석', ?)",
                (student_id, _today(), now),
            )
        except sqlite3.IntegrityError:          # UNIQUE(학번, 날짜)에 걸림
            return False, "오늘은 이미 입실했어요."
    return True, f"{now} 입실 완료"


def check_out(student_id, reason=None):
    """오늘 퇴실 기록. 끝나는 시간 전이면 '조퇴'로 바뀐다."""
    now = _now_time()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 퇴실시간 FROM 출석 WHERE 학번 = ? AND 날짜 = ?",
            (student_id, _today()),
        ).fetchone()

        if row is None:
            return False, "오늘 입실 기록이 없어요."
        if row["퇴실시간"]:
            return False, "이미 퇴실했어요."

        status = "조퇴" if now < CLUB_END_TIME else "출석"
        conn.execute(
            "UPDATE 출석 SET 퇴실시간 = ?, 상태 = ?, 사유 = ? WHERE 학번 = ? AND 날짜 = ?",
            (now, status, reason, student_id, _today()),
        )
    return True, f"{now} 퇴실 완료 ({status})"


def mark_absent(student_id, date, reason=None):
    """교사가 결석 처리. 이미 기록이 있으면 결석으로 덮어쓴다 (UPSERT)."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO 출석 (학번, 날짜, 상태, 사유) VALUES (?, ?, '결석', ?)
            ON CONFLICT (학번, 날짜) DO UPDATE SET
                상태 = '결석', 사유 = excluded.사유, 입실시간 = NULL, 퇴실시간 = NULL
            """,
            (student_id, date, reason),
        )


def get_attendance_by_date(date=None):
    """특정 날짜 출결표. 기록 없는 학생도 상태 None으로 같이 나온다 (LEFT JOIN)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.학번, s.이름, a.상태, a.입실시간, a.퇴실시간, a.사유
            FROM 학생 s
            LEFT JOIN 출석 a ON a.학번 = s.학번 AND a.날짜 = ?
            ORDER BY s.학번
            """,
            (date or _today(),),
        ).fetchall()
    return _to_dicts(rows)


# ─────────────────────────────────────────────
# 8. 분야 · 활동일지
# ─────────────────────────────────────────────

def list_fields():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM 분야 ORDER BY 분야ID").fetchall()
    return _to_dicts(rows)


def add_field(name):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO 분야 (분야명) VALUES (?)", (name,))


def add_journal(student_id, content, learned="", difficulty="", field_ids=(), date=None):
    """일지 저장 + 분야 태그 연결. 둘 중 하나라도 실패하면 전부 취소된다."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO 활동일지 (학번, 날짜, 활동내용, 배운점, 어려웠던점)
            VALUES (?, ?, ?, ?, ?)
            """,
            (student_id, date or _today(), content, learned, difficulty),
        )
        journal_id = cur.lastrowid              # 방금 만든 일지의 ID
        conn.executemany(
            "INSERT INTO 일지_분야 (일지ID, 분야ID) VALUES (?, ?)",
            [(journal_id, fid) for fid in field_ids],
        )
    return journal_id


def get_journals(student_id=None):
    """일지 목록. student_id를 주면 그 학생 것만. 분야는 '네트워크, 리눅스'처럼 합쳐서."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT j.일지ID, j.학번, s.이름, j.날짜, j.활동내용, j.배운점, j.어려웠던점,
                   t.이름 AS 확인교사,
                   GROUP_CONCAT(f.분야명, ', ') AS 분야
            FROM 활동일지 j
            JOIN 학생 s           ON s.학번 = j.학번
            LEFT JOIN 교사 t      ON t.교사ID = j.확인교사ID
            LEFT JOIN 일지_분야 jf ON jf.일지ID = j.일지ID
            LEFT JOIN 분야 f      ON f.분야ID = jf.분야ID
            WHERE (? IS NULL OR j.학번 = ?)
            GROUP BY j.일지ID
            ORDER BY j.날짜 DESC, j.일지ID DESC
            """,
            (student_id, student_id),
        ).fetchall()
    return _to_dicts(rows)


def confirm_journal(journal_id, teacher_id):
    """교사가 일지 확인 처리."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE 활동일지 SET 확인교사ID = ? WHERE 일지ID = ?",
            (teacher_id, journal_id),
        )


# ─────────────────────────────────────────────
# 9. 테스트 (python db.py 로 직접 실행할 때만 동작)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("DB 위치:", DB_PATH)

    if get_student("20101") is None:
        add_student("20101", "홍길동", 2, 1)
    if not has_teacher():
        add_teacher("관리자", "1234")

    print("학생 목록:", list_students())
    print("분야 목록:", list_fields())
    print("입실:", check_in("20101"))
    print("입실 또 시도:", check_in("20101"))
    print("퇴실:", check_out("20101"))
    print("오늘 출결표:", get_attendance_by_date())

    jid = add_journal("20101", "VLAN 설정 실습", "트렁크 포트 개념", "명령어 순서", [1, 2])
    teacher = verify_teacher("관리자", "1234")
    confirm_journal(jid, teacher["교사ID"])
    print("일지:", get_journals("20101")[0])
    print("틀린 비번 로그인:", verify_teacher("관리자", "0000"))
