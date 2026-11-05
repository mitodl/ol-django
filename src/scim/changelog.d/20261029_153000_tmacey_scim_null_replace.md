### Fixed

- A PATCH that sets a mapped attribute to null returned a 500. scim-for-keycloak
  sends a remove as a path-less replace with the attribute set to null, and
  `UserAdapter` wrote that `None` straight onto the model, so a NOT NULL
  column (e.g. `username`, or mitxonline's `name` via `fullName`) failed the
  save. The client retries the op on every sync run, so it never leaves the
  queue. A null now becomes `""` for a text field that allows blank, `None`
  for a nullable field, and is ignored (with a warning) for a required or
  unique field such as `username`.
