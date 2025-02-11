"""transcoding app AppConfig"""

import os

from django.apps import AppConfig


class Transcoding(AppConfig):
    """Default configuration for the transcoding app"""

    name = "mitol.transcoding"
    label = "transcoding"
    verbose_name = "transcoding"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120


class TransitionalTranscoding(AppConfig):
    """AppConfig for transitioning a project with an existing 'transcoding' app"""

    name = "mitol.transcoding"
    label = "transitional_transcoding"
    verbose_name = "transcoding"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120
