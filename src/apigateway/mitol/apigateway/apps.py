"""API Gateway app AppConfig"""

import os

from django.apps import AppConfig


class ApigatewayApp(AppConfig):
    """Default configuration for the Apigateway app"""

    name = "mitol.apigateway"
    label = "apigateway"
    verbose_name = "apigateway"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120


class TransitionalApigatewayApp(AppConfig):
    """AppConfig for transitioning a project with an existing 'Apigateway' app"""

    name = "mitol.apigateway"
    label = "transitional_apigateway"
    verbose_name = "apigateway"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120
