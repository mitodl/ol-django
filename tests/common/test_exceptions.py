from mitol.common.exceptions import RequiredPrefetchMissingError


def test_required_prefetch_missing_error():
    """Test that the serial"""

    err = RequiredPrefetchMissingError(
        "prefetch_name",
        [("FirstLevel1Serializer", "second_level"), ("SecondLevel1Serializer", None)],
    )

    assert str(err) == (
        "Required prefetch is missing: prefetch='prefetch_name' "
        "path='FirstLevel1Serializer.second_level -> SecondLevel1Serializer'"
    )
