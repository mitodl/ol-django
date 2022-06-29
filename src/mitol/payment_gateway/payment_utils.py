"""Utilities for the Payment Gateway"""


# To delete None values in Input Request Json body
def clean_request_data(request_data):
    # Cybersource would not accept None values in payload that get generated through CyberSource's Data models
    # This functions cleans the request of any None values

    if isinstance(request_data, dict):
        return {key: value for key, value in request_data.items() if value is not None}
    return request_data
