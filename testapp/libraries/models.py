from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=255)


class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.ForeignKey(Author, related_name="books", on_delete=models.CASCADE)


class Library(models.Model):
    name = models.CharField(max_length=255)

    books = models.ManyToManyField(Book, related_name="libraries")
