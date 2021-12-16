"""Tests for courses utils"""
from mitol.openedx.utils.courses import get_course_number


def test_get_course_number():
    """
    Tests get_course_number
    """

    courseware_id = "course-v1:edX+DemoX+Demo_Course"
    course_number = get_course_number(courseware_id)
    assert course_number == "DemoX"

    courseware_id = "course-v1:edX-DemoX-Demo_Course"
    course_number = get_course_number(courseware_id)
    assert course_number == courseware_id
