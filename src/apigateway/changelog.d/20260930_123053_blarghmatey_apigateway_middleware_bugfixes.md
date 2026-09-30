### Fixed

- A userinfo header that isn't base64-encoded JSON, or that decodes to something other than a JSON object, is now logged as a warning and treated as a missing header. It used to raise out of the middleware as a 500.
