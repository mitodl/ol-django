from mitol.common.envs import get_string, get_bool, get_int
POSTHOG_ENABLED = get_bool(
    name="POSTHOG_ENABLED",
    default=False,
    description="Whether to enable Posthog feature flags",
)
POSTHOG_PROJECT_API_KEY = get_string(
    name="POSTHOG_PROJECT_API_KEY",
    default="",
    description="Private API key to communicate with PostHog",
)
POSTHOG_API_HOST = get_string(
    name="POSTHOG_API_HOST",
    default="https://us.posthog.com",
    description="API host for PostHog",
)
POSTHOG_FEATURE_FLAG_REQUEST_TIMEOUT_MS = get_int(
    name="POSTHOG_FEATURE_FLAG_REQUEST_TIMEOUT_MS",
    default=3000,
    description="Timeout(MS) for PostHog feature flag requests.",
)

POSTHOG_MAX_RETRIES = get_int(
    name="POSTHOG_MAX_RETRIES",
    default=3,
    description="Numbers of time requests to PostHog should be retried after failing.",
)
# CACHES = {
#     # general durable cache (redis should be considered ephemeral)
#     "durable": {
#         "BACKEND": "django.core.cache.backends.db.DatabaseCache",
#         "LOCATION": "durable_cache",
#     },
# }
if os.getenv("POSTHOG_ENABLED", "False").lower() in ("true", "1", "t"):
    posthog.api_key = POSTHOG_API_TOKEN
    posthog.host = POSTHOG_API_HOST
    posthog.feature_flags_request_timeout_seconds = (
        POSTHOG_FEATURE_FLAG_REQUEST_TIMEOUT_MS / 1000
    )
    posthog.max_retries = POSTHOG_MAX_RETRIES
