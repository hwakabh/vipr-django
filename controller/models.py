from django.db import models
from django.utils import timezone

# Create your models here.

class CatalogHistory(models.Model):
    register_time = models.DateTimeField(default=timezone.now)
    message = models.CharField(max_length=50)

    def __str__(self):
        return '{}'.format(self.message)