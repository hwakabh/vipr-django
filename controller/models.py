from django.db import models
from django.utils import timezone

# Create your models here.

class CatalogHistory(models.Model):
    register_time = models.DateTimeField(default=timezone.now, null=True)
    server_name = models.CharField(max_length=40, null=True)
    wwpn_1 = models.CharField(max_length=23, null=True)
    wwpn_2 = models.CharField(max_length=23, null=True)
    backend_array_name = models.CharField(max_length=30, null=True)
    backend_storagepool_name = models.CharField(max_length=30, null=True)
    vplex_name = models.CharField(max_length=30, null=True)
    primary_mds_switch = models.CharField(max_length=30, null=True)
    secondary_mds_switch = models.CharField(max_length=30, null=True)
    lun_name_on_backend = models.CharField(max_length=30, null=True)
    lun_size = models.CharField(max_length=30, null=True)
    thin_volume_or_not = models.CharField(max_length=30, null=True)
    hlu_on_vplex = models.CharField(max_length=30, null=True)
    message = models.CharField(max_length=50, null=True)

    def __str__(self):
        return '{}'.format(self.message)