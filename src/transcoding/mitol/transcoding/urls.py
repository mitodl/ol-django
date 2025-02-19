"""URLs for Transcoding app."""

from django.urls import path

from mitol.transcoding.views import TranscodeJobView

urlpatterns = [
    path(
        "api/transcode-jobs/",
        TranscodeJobView.as_view(),
        name="transcode_jobs",
    ),
]
