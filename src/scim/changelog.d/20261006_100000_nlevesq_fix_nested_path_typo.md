### Fixed

- `UserAdapter`'s nested-path handler is now spelled
  `_handle_replace_nested_path`. It was `_handle_resplace_nested_path` - with
  the letters transposed - so a subclass that overrode it under the spelling
  the name reads never ran: a SCIM PATCH carrying an attribute that subclass
  was meant to handle returned 200 and silently wrote nothing. A subclass
  still matching the old misspelling keeps working and now raises a
  `DeprecationWarning`.
