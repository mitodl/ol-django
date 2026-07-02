from django.contrib import admin

from libraries.models import (
    Author,
    Book,
    Library,
    Media,
    Periodical,
    Recommendation,
    RecommendationList,
    Topic,
)

admin.site.register(Author)
admin.site.register(Topic)
admin.site.register(Book)
admin.site.register(Media)
admin.site.register(Periodical)
admin.site.register(Recommendation)
admin.site.register(RecommendationList)
admin.site.register(Library)
