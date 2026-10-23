### Added

- `EdxApi.enrollments_v2`, a client for `/api/enrollment/v2/`. v2 accepts only JWT or session auth, so it sends the access token under the `JWT` scheme. Its list methods follow v2's page-number pagination, and `get_student_enrollments` takes a `username` and drops inactive enrollments and enrollments in deleted courses unless `include_inactive=True`, which matches what v1 returned. openedx/openedx-platform#39128 deprecates `/api/enrollment/v1/` and removes it one named release after Willow.
