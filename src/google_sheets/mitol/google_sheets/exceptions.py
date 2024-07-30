"""Sheets app exceptions"""


class SheetValidationException(Exception):  # noqa: N818
    """
    General exception for failures during the validation of Sheet data
    """


class SheetUpdateException(Exception):  # noqa: N818
    """
    General exception for failures while attempting to update a Sheet via API
    """


class SheetRowParsingException(Exception):  # noqa: N818
    """
    General exception for failures while attempting to parse the data in a Sheet row
    """


class SheetOutOfSyncException(Exception):  # noqa: N818
    """
    General exception for situations where the data in a spreadsheet does not reflect the state of the database
    """  # noqa: E501

    def __init__(self, coupon_gen_request, coupon_req_row, msg=None):
        self.coupon_gen_request = coupon_gen_request
        self.coupon_req_row = coupon_req_row
        super().__init__(msg)


class InvalidSheetProductException(Exception):  # noqa: N818
    """
    Exception for an invalid product entered into the coupon request spreadsheet
    """
