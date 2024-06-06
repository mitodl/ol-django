"""Utility functions for course related functions"""

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey


def get_course_number(courseware_id):
    """
    Returns course number from courseware_id in course_run
    in case of exception, returns courseware_id as it is, so code does not break
    e.g:
        returns DemoX from course-v1:edX+DemoX+Demo_Course
        returns 14.740x from course-v1:MITx+14.740x+3T2021

    Args:
        courseware_id: Courseware Id from course run: course_run.courseware_id
    Returns:
        str: course number or Courseware Id
    """
    try:
        course_key = CourseKey.from_string(courseware_id)
        return course_key.course
    except InvalidKeyError:
        return courseware_id
