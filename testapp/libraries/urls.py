from rest_framework import routers

from libraries import views

router = routers.DefaultRouter()
router.register(r"libraries", views.LibrariesViewSet, basename="libraries_api")

urlpatterns = router.urls
