from mitol.common.envs import get_bool, get_int, get_string

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

POSTHOG_PERSONAL_API_KEY = get_string(
    name="POSTHOG_PERSONAL_API_KEY",
    default="",
    description="Personal API key for PostHog local flag evaluation. When set, flags are evaluated locally without per-request HTTP calls.",  # noqa: E501
)
POSTHOG_API_HOST = get_string(
    name="POSTHOG_API_HOST",
    default="https://us.posthog.com",
    description="Host URL for the PostHog API",
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

POSTHOG_POLL_INTERVAL = get_int(
    name="POSTHOG_POLL_INTERVAL",
    default=300,
    description="Seconds between PostHog flag config polling. Relevant when POSTHOG_PERSONAL_API_KEY is set for local evaluation.",  # noqa: E501
)

POSTHOG_CIRCUIT_BREAKER_COOLDOWN_SECONDS = get_int(
    name="POSTHOG_CIRCUIT_BREAKER_COOLDOWN_SECONDS",
    default=60,
    description="Seconds to wait before retrying PostHog after a failed request.",
)

POSTHOG_CIRCUIT_BREAKER_TRIP_THRESHOLD_SECONDS = get_int(
    name="POSTHOG_CIRCUIT_BREAKER_TRIP_THRESHOLD_SECONDS",
    default=6,
    description="Seconds a PostHog request can take before the circuit breaker trips.",
)
