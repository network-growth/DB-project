"""
cli.py - 동아리 출결·활동일지 관리 프로그램의 글자 메뉴 화면

이 파일은 '얼굴' 역할만 한다.
실제 저장·조회는 전부 db.py(뇌)의 함수를 불러서 처리한다. SQL은 여기 없다.

실행: python3 cli.py
"""

import getpass
import sqlite3
import unicodedata
from datetime import datetime

import db


# ─────────────────────────────────────────────
# 1. 입력·출력 도우미
# ─────────────────────────────────────────────

def _input(prompt):
    """input() 대신 쓰는 안전한 입력.
    SSH로 한글을 치다가 백스페이스로 지우면 글자가 반쪽만 지워져서
    깨진 바이트가 들어오는 경우가 있다. 그럴 땐 다시 입력받는다.
    """
    while True:
        try:
            return input(prompt)
        except UnicodeDecodeError:
            print("  → 글자가 깨져서 들어왔어요. 다시 입력해 주세요.")


def _getpass(prompt):
    while True:
        try:
            return getpass.getpass(prompt)
        except UnicodeDecodeError:
            print("  → 글자가 깨져서 들어왔어요. 다시 입력해 주세요.")


def title(text):
    print("\n" + "=" * 44)
    print(f"  {text}")
    print("=" * 44)


def pause():
    _input("\n(엔터를 누르면 돌아가요)")


def ask(prompt, required=True):
    """글자 입력받기. required면 빈칸일 때 다시 물어본다."""
    while True:
        value = _input(prompt).strip()
        if value or not required:
            return value
        print("  → 비워둘 수 없어요.")


def ask_int(prompt):
    """숫자만 입력받기."""
    while True:
        value = _input(prompt).strip()
        if value.isdigit():
            return int(value)
        print("  → 숫자로 입력해 주세요.")


def ask_date(prompt):
    """날짜 입력받기. 엔터만 치면 오늘. 형식이 틀리면 다시 물어본다."""
    while True:
        value = _input(prompt).strip()
        if not value:
            return datetime.now().strftime("%Y-%m-%d")
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            print("  → 2026-10-30 처럼 입력해 주세요.")


def _width(text):
    """한글은 화면에서 2칸을 차지해서, 표 줄을 맞추려면 직접 계산해야 한다."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text, width):
    return text + " " * (width - _width(text))


def print_table(rows, columns):
    """dict 목록을 표로 출력. columns = 보여줄 컬럼 이름 목록"""
    if not rows:
        print("  (기록이 없어요)")
        return

    cells = [[("-" if r[c] is None else str(r[c])) for c in columns] for r in rows]
    widths = [
        max(_width(columns[i]), *(_width(row[i]) for row in cells))
        for i in range(len(columns))
    ]

    print("  " + " | ".join(_pad(c, w) for c, w in zip(columns, widths)))
    print("  " + "-+-".join("-" * w for w in widths))
    for row in cells:
        print("  " + " | ".join(_pad(v, w) for v, w in zip(row, widths)))


def choose_fields():
    """분야 목록을 보여주고 '1,2' 처럼 여러 개 고르게 한다."""
    fields = db.list_fields()
    valid_ids = {f["분야ID"] for f in fields}

    print("\n  분야: " + "  ".join(f"{f['분야ID']}.{f['분야명']}" for f in fields))
    while True:
        raw = _input("  해당 분야 번호 (여러 개면 1,2 / 없으면 엔터) > ").strip()
        if not raw:
            return []
        try:
            ids = {int(x) for x in raw.replace(" ", "").split(",")}
        except ValueError:
            print("  → 숫자와 쉼표만 써 주세요.")
            continue
        if ids <= valid_ids:
            return sorted(ids)
        print("  → 목록에 없는 번호가 있어요.")


# ─────────────────────────────────────────────
# 2. 첫 실행: 관리자 교사 만들기
# ─────────────────────────────────────────────

def first_setup():
    if db.has_teacher():
        return

    title("처음 실행이네요! 관리자(교사) 계정을 만들어요")
    name = ask("  교사 이름 > ")
    while True:
        pw = _getpass("  비밀번호 (화면에 안 보여요) > ")
        if len(pw) < 4:
            print("  → 4자 이상으로 해 주세요.")
            continue
        if pw == _getpass("  비밀번호 확인 > "):
            break
        print("  → 두 비밀번호가 달라요. 다시 입력해 주세요.")

    db.add_teacher(name, pw)
    print(f"\n  ✔ '{name}' 교사 계정이 만들어졌어요.")


# ─────────────────────────────────────────────
# 3. 학생 화면
# ─────────────────────────────────────────────

def student_login():
    student_id = ask("\n  학번 > ")
    student = db.get_student(student_id)
    if student is None:
        print("  → 등록되지 않은 학번이에요. 선생님께 등록을 요청하세요.")
        pause()
        return
    student_menu(student)


def student_menu(student):
    while True:
        title(f"학생 메뉴 - {student['이름']} ({student['학번']})")
        print("  1. 입실")
        print("  2. 퇴실")
        print("  3. 활동일지 쓰기")
        print("  4. 내 활동일지 보기")
        print("  0. 로그아웃")
        choice = _input("\n  선택 > ").strip()

        if choice == "1":
            ok, msg = db.check_in(student["학번"])
            print(f"  {'✔' if ok else '✖'} {msg}")
            pause()

        elif choice == "2":
            reason = None
            if datetime.now().strftime("%H:%M") < db.CLUB_END_TIME:
                print(f"  ※ 끝나는 시간({db.CLUB_END_TIME}) 전이라 조퇴로 기록돼요.")
                reason = ask("  조퇴 사유 > ")
            ok, msg = db.check_out(student["학번"], reason)
            print(f"  {'✔' if ok else '✖'} {msg}")
            pause()

        elif choice == "3":
            write_journal(student)

        elif choice == "4":
            show_journals(db.get_journals(student["학번"]))
            pause()

        elif choice == "0":
            return

        else:
            print("  → 메뉴에 있는 번호를 골라 주세요.")


def write_journal(student):
    title("활동일지 쓰기")
    content = ask("  오늘 한 활동 > ")
    learned = ask("  배운 점 (엔터=생략) > ", required=False)
    difficulty = ask("  어려웠던 점 (엔터=생략) > ", required=False)
    field_ids = choose_fields()

    journal_id = db.add_journal(student["학번"], content, learned, difficulty, field_ids)
    print(f"\n  ✔ 일지가 저장됐어요. (일지 번호 {journal_id})")
    pause()


def show_journals(journals):
    if not journals:
        print("\n  (작성한 일지가 없어요)")
        return
    for j in journals:
        status = f"확인: {j['확인교사']}" if j["확인교사"] else "미확인"
        print(f"\n  [{j['일지ID']}] {j['날짜']}  {j['이름']}  ({j['분야'] or '분야 없음'})  {status}")
        print(f"     활동   : {j['활동내용']}")
        print(f"     배운 점: {j['배운점'] or '-'}")
        print(f"     어려움 : {j['어려웠던점'] or '-'}")


# ─────────────────────────────────────────────
# 4. 교사 화면
# ─────────────────────────────────────────────

def teacher_login():
    name = ask("\n  교사 이름 > ")
    pw = _getpass("  비밀번호 > ")
    teacher = db.verify_teacher(name, pw)
    if teacher is None:
        print("  → 이름 또는 비밀번호가 틀렸어요.")
        pause()
        return
    teacher_menu(teacher)


def teacher_menu(teacher):
    while True:
        title(f"교사 메뉴 - {teacher['이름']}")
        print("  1. 날짜별 출결표")
        print("  2. 활동일지 보기 / 확인")
        print("  3. 결석 처리")
        print("  4. 학생 목록")
        print("  5. 학생 등록")
        print("  6. 학생 삭제")
        print("  7. 분야 추가")
        print("  8. 교사 추가")
        print("  0. 로그아웃")
        choice = _input("\n  선택 > ").strip()

        if choice == "1":
            date = ask_date("  날짜 (엔터=오늘, 예: 2026-10-30) > ")
            print(f"\n  ■ {date} 출결표")
            print_table(db.get_attendance_by_date(date),
                        ["학번", "이름", "상태", "입실시간", "퇴실시간", "사유"])
            pause()

        elif choice == "2":
            review_journals(teacher)

        elif choice == "3":
            student_id = ask("  학번 > ")
            if db.get_student(student_id) is None:
                print("  → 없는 학번이에요.")
            else:
                date = ask_date("  날짜 (엔터=오늘) > ")
                reason = ask("  사유 (엔터=생략) > ", required=False) or None
                db.mark_absent(student_id, date, reason)
                print(f"  ✔ {student_id} 학생을 {date} 결석 처리했어요.")
            pause()

        elif choice == "4":
            print_table(db.list_students(), ["학번", "이름", "학년", "반", "가입일"])
            pause()

        elif choice == "5":
            add_student()

        elif choice == "6":
            delete_student()

        elif choice == "7":
            name = ask("  새 분야 이름 > ")
            db.add_field(name)
            print("  ✔ 추가했어요. (이미 있으면 그대로 둬요)")
            pause()

        elif choice == "8":
            add_teacher()

        elif choice == "0":
            return

        else:
            print("  → 메뉴에 있는 번호를 골라 주세요.")


def review_journals(teacher):
    student_id = ask("  학번 (엔터=전체) > ", required=False) or None
    journals = db.get_journals(student_id)
    show_journals(journals)
    if not journals:
        pause()
        return

    raw = _input("\n  확인 처리할 일지 번호 (엔터=건너뛰기) > ").strip()
    if not raw:
        return
    if raw.isdigit() and int(raw) in {j["일지ID"] for j in journals}:
        db.confirm_journal(int(raw), teacher["교사ID"])
        print("  ✔ 확인 처리했어요.")
    else:
        print("  → 목록에 없는 번호예요.")
    pause()


def add_student():
    title("학생 등록")
    student_id = ask("  학번 (5자리) > ")
    if len(student_id) != 5 or not student_id.isdigit():
        print("  → 학번은 숫자 5자리예요.")
        pause()
        return
    name = ask("  이름 > ")
    grade = ask_int("  학년 > ")
    class_no = ask_int("  반 > ")

    try:
        db.add_student(student_id, name, grade, class_no)
        print(f"  ✔ {name} 학생을 등록했어요.")
    except sqlite3.IntegrityError:          # 학번(PK) 중복
        print("  → 이미 등록된 학번이에요.")
    pause()


def delete_student():
    student_id = ask("  삭제할 학번 > ")
    student = db.get_student(student_id)
    if student is None:
        print("  → 없는 학번이에요.")
        pause()
        return

    print(f"  ※ {student['이름']} 학생의 출석·일지 기록도 전부 지워져요.")
    if _input("  정말 삭제할까요? (y/n) > ").strip().lower() == "y":
        db.delete_student(student_id)
        print("  ✔ 삭제했어요.")
    else:
        print("  취소했어요.")
    pause()


def add_teacher():
    title("교사 추가")
    name = ask("  교사 이름 > ")
    pw = _getpass("  비밀번호 > ")
    if len(pw) < 4:
        print("  → 4자 이상으로 해 주세요.")
        pause()
        return
    try:
        db.add_teacher(name, pw)
        print(f"  ✔ '{name}' 교사를 추가했어요.")
    except sqlite3.IntegrityError:          # 교사 이름 UNIQUE
        print("  → 같은 이름의 교사가 이미 있어요.")
    pause()


# ─────────────────────────────────────────────
# 5. 시작 화면
# ─────────────────────────────────────────────

def main():
    db.init_db()
    first_setup()

    while True:
        title("동아리 출결·활동일지 관리")
        print("  1. 학생 로그인")
        print("  2. 교사 로그인")
        print("  0. 종료")
        choice = _input("\n  선택 > ").strip()

        if choice == "1":
            student_login()
        elif choice == "2":
            teacher_login()
        elif choice == "0":
            print("  종료할게요.")
            return
        else:
            print("  → 메뉴에 있는 번호를 골라 주세요.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):   # Ctrl+C / Ctrl+D 로 나가도 에러 없이 종료
        print("\n  종료할게요.")
