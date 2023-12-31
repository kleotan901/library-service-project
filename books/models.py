from django.core.validators import MinValueValidator
from django.db import models


class Book(models.Model):
    ENUM = [("HARD", "HARD"), ("SOFT", "SOFT")]

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    cover = models.CharField(max_length=20, choices=ENUM)
    inventory = models.IntegerField(
        validators=[
            MinValueValidator(
                limit_value=1, message="Amount of books can not be 0 or negative number"
            )
        ]
    )
    daily_fee = models.DecimalField(decimal_places=2, max_digits=12)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return f"{self.title}({self.author})"
