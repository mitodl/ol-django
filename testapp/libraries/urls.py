from rest_framework.routers import SimpleRouter

from libraries.views import BookViewSet, LibraryViewSet, RecommendationListViewSet

router = SimpleRouter()
router.register(r"libraries", LibraryViewSet, basename="library")
router.register(r"books", BookViewSet, basename="book")
router.register(
    r"recommendation-lists", RecommendationListViewSet, basename="recommendationlist"
)

urlpatterns = router.urls
