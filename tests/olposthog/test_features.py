"""Tests for feature flags"""

import logging
import time
from datetime import timedelta

import pytest
from django.core.cache import caches
from freezegun import freeze_time
from mitol.common.utils.datetime import now_in_utc
from mitol.olposthog import features

pytestmark = [pytest.mark.django_db]


"""
Tests for OlPosthog and caching functionality

- Test grabbing flags from Posthog with a cleared cache; they should hit
  Posthog and then the flag should be cached
- Test population of the cache with calls to get_all
- Test flag grabbing after timeout
"""


@pytest.fixture(autouse=True)
def posthog_settings(settings):
    """Apply common settings and clear the cache for all feature flag tests."""
    settings.POSTHOG_ENABLED = True
    settings.HOSTNAME = "fake_host_name"
    settings.ENVIRONMENT = "prod"
    caches["durable"].clear()


def test_flags_from_cache(mocker, caplog, settings):
    """Test that flags are pulled from cache successfully."""
    get_feature_flag_mock = mocker.patch(
        "posthog.get_feature_flag", autospec=True, return_value=True
    )
    durable_cache = caches["durable"]
    settings.FEATURES["testing_function"] = True
    cache_key = features._generate_cache_key(  # noqa: SLF001
        "testing_function",
        features.default_unique_id(),
        features._get_person_properties(features.default_unique_id()),  # noqa: SLF001
    )

    # Cache cleared, so we should hit Posthog.

    with caplog.at_level(logging.DEBUG):
        was_enabled = features.is_enabled("testing_function")

        assert was_enabled
        assert durable_cache.get(cache_key, None) is not None
        get_feature_flag_mock.assert_called()

    assert "from Posthog" in caplog.text

    # Cache has stuff, so we should get it from that now.

    get_feature_flag_mock.reset_mock()

    with caplog.at_level(logging.DEBUG):
        was_enabled = features.is_enabled("testing_function")

        assert was_enabled
        assert durable_cache.get(cache_key, None) is not None
        get_feature_flag_mock.assert_not_called()

    assert "from the cache" in caplog.text


def test_cache_population(mocker, settings):
    """Test that the cache is populated correctly when get_all_feature_flags is called."""  # noqa: E501

    get_feature_flag_mock = mocker.patch(
        "posthog.get_feature_flag", autospec=True, return_value=True
    )
    get_all_flags_mock = mocker.patch(
        "posthog.get_all_flags",
        autospec=True,
        return_value={
            "testing_function_1": True,
            "testing_function_2": True,
            "testing_function_3": True,
        },
    )

    settings.FEATURES["testing_function_1"] = True
    settings.FEATURES["testing_function_2"] = True
    settings.FEATURES["testing_function_3"] = True

    all_flags = features.get_all_feature_flags()

    get_all_flags_mock.assert_called()

    for k in all_flags:
        assert features.is_enabled(k)
        get_feature_flag_mock.assert_not_called()


def test_circuit_breaker_trips_on_slow_response(mocker, caplog, settings):
    """Test that a slow PostHog call trips the circuit breaker."""

    def slow_flag(*_args, **_kwargs):
        time.sleep(0.1)

    mocker.patch("posthog.get_feature_flag", autospec=True, side_effect=slow_flag)
    durable_cache = caches["durable"]
    settings.FEATURES["testing_function"] = False
    settings.POSTHOG_CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60
    settings.POSTHOG_CIRCUIT_BREAKER_TRIP_THRESHOLD_SECONDS = 0  # trip immediately

    with caplog.at_level(logging.DEBUG):
        result = features.is_enabled("testing_function")

    # Falls back to settings.FEATURES
    assert result is False
    # Circuit is now open
    assert durable_cache.get(features.CIRCUIT_BREAKER_CACHE_KEY) is not None


def test_circuit_breaker_skips_posthog_when_open(mocker, caplog, settings):
    """Test that an open circuit skips PostHog and returns the settings fallback."""
    get_feature_flag_mock = mocker.patch(
        "posthog.get_feature_flag", side_effect=lambda *_, **__: time.sleep(0.1)
    )
    settings.FEATURES["testing_function"] = False
    settings.POSTHOG_CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60
    settings.POSTHOG_CIRCUIT_BREAKER_TRIP_THRESHOLD_SECONDS = 0

    features.is_enabled("testing_function")  # trips the circuit

    # Reset and verify the open circuit skips PostHog entirely
    get_feature_flag_mock.reset_mock()
    get_feature_flag_mock.side_effect = None
    get_feature_flag_mock.return_value = True

    with caplog.at_level(logging.DEBUG):
        result = features.is_enabled("testing_function")

    get_feature_flag_mock.assert_not_called()
    assert result is False
    assert "circuit open" in caplog.text


def test_circuit_breaker_trips_on_exception(mocker, caplog, settings):
    """Test that an unexpected PostHog exception trips the circuit and falls back."""
    mocker.patch(
        "posthog.get_feature_flag",
        autospec=True,
        side_effect=RuntimeError("unexpected SDK error"),
    )
    durable_cache = caches["durable"]
    settings.FEATURES["testing_function"] = False
    settings.POSTHOG_CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60
    settings.POSTHOG_CIRCUIT_BREAKER_TRIP_THRESHOLD_SECONDS = 0

    with caplog.at_level(logging.DEBUG):
        result = features.is_enabled("testing_function")

    assert result is False
    assert durable_cache.get(features.CIRCUIT_BREAKER_CACHE_KEY) is not None


def test_circuit_breaker_closes_after_cooldown(mocker, settings):
    """Test that the circuit closes after the cooldown period expires."""
    get_feature_flag_mock = mocker.patch(
        "posthog.get_feature_flag", autospec=True, return_value=True
    )
    durable_cache = caches["durable"]
    settings.FEATURES["testing_function"] = False
    settings.POSTHOG_CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60

    durable_cache.set(features.CIRCUIT_BREAKER_CACHE_KEY, 1, 60)

    time_freezer = freeze_time(now_in_utc() + timedelta(seconds=61))
    time_freezer.start()

    result = features.is_enabled("testing_function")

    time_freezer.stop()

    get_feature_flag_mock.assert_called()
    assert result is True


def test_posthog_flag_cache_timeout(mocker, settings):
    """Test that the cache gets invalidated as we expect"""

    get_feature_flag_mock = mocker.patch(
        "posthog.get_feature_flag", autospec=True, return_value=True
    )
    settings.FEATURES["testing_function"] = True

    timeout = settings.CACHES["durable"].get("TIMEOUT", 300)

    time_freezer = freeze_time(now_in_utc() + timedelta(seconds=timeout * 2))

    assert features.is_enabled("test_function")
    get_feature_flag_mock.assert_called()

    time_freezer.start()
    assert features.is_enabled("test_function")
    get_feature_flag_mock.assert_called()
    time_freezer.stop()
