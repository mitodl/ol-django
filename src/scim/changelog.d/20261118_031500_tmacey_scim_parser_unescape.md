### Fixed

- The SCIM filter parser decodes a quoted compValue as the JSON string RFC 7644 defines, so `emails.value eq "\"x\"@example.com"` matches the email `"x"@example.com`. It used to strip only the outer quotes and compare with the backslashes still in the value. A value with an escape JSON doesn't define (e.g. `\x41` or a doubled quote) is now a 400 `Invalid filter string` response instead of being matched literally.
