"""common constants"""

USERNAME_SEPARATOR = "-"
# Characters that should be replaced by the specified separator character
USERNAME_SEPARATOR_REPLACE_CHARS = "\\s_"
# Characters that should be removed entirely from the full name to create the username
USERNAME_INVALID_CHAR_PATTERN = (
    rf"[^\w{USERNAME_SEPARATOR_REPLACE_CHARS}{USERNAME_SEPARATOR}]|[\d]"
)

USERNAME_TURKISH_I_CHARS = r"[ıİ]"
USERNAME_TURKISH_I_CHARS_REPLACEMENT = "i"

# Pattern for chars to replace with a single separator. The separator character itself
# is also included in this pattern so repeated separators are squashed down.
USERNAME_SEPARATOR_REPLACE_PATTERN = (
    rf"[{USERNAME_SEPARATOR_REPLACE_CHARS}{USERNAME_SEPARATOR}]+"
)

USERNAME_MAX_LEN = 30
USERNAME_COLLISION_ATTEMPTS = 10
