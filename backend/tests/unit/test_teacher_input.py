from app.services.teacher_input import topic_issue


def test_boundary_of_the_minimum_length() -> None:
    assert topic_issue("一二三四五六七八九十一二三四五六七八九") == "too_short"
    assert topic_issue("一二三四五六七八九十一二三四五六七八九零") is None


def test_keyboard_runs_and_repeated_filler_are_refused() -> None:
    assert topic_issue("asdfghjkl asdfghjkl asdfghjkl") == "unreadable"
    assert topic_issue("qwertyuiop qwertyuiop qwertyuiop") == "unreadable"
    assert topic_issue("ab" * 15) == "unreadable"


def test_ordinary_topics_and_injection_discussions_pass() -> None:
    assert topic_issue("比較兩位作者對於誰應該做決定的不同主張與理由") is None
    assert topic_issue("Compare two accounts of who should decide in class.") is None
    assert (
        topic_issue("討論提示注入本身是否應該被允許並說明學生如何判斷 AI 的指令")
        is None
    )
