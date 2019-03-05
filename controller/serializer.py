from rest_framework import serializers
from controller.models import CatalogHistory

class CatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogHistory
        fields = (
            'id',
            'backend_array_name', 'backend_storagepool_name', 'vplex_name',
            'primary_mds_switch', 'secondary_mds_switch',
            'lun_name_on_backend', 'lun_size', 'thin_volume_or_not', 'hlu_on_vplex',
            'message'
            )
