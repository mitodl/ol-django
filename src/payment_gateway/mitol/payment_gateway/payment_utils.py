"""Utilities for the Payment Gateway"""

from decimal import Decimal


# To delete None values in Input Request Json body
def clean_request_data(request_data):
    # Cybersource would not accept None values in payload that get generated through CyberSource's Data models  # noqa: E501
    # This functions cleans the request of any None values

    if isinstance(request_data, dict):
        return {key: value for key, value in request_data.items() if value is not None}
    return request_data


def strip_nones(datasource):
    """Strips None values from the supplied iterable. Does not recurse."""  # noqa: D401

    retval = {}

    for key in datasource:
        if datasource[key] is not None:
            retval[key] = datasource[key]

    return retval


def quantize_decimal(value, precision=2):
    """Quantize a decimal value to the specified precision"""
    return Decimal(value).quantize(Decimal("0.{}".format("0" * precision)))
