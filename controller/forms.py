from django import forms

BACKEND_ARRAYS = (
    ('', 'Select Backend array'),
    ('Unity#1', 'Unity#1'),
    ('Unity#2', 'Unity#2'),
    ('Unity#3', 'Unity#3'),
)

STORAGE_POOLS = (
    ('', 'Select Backend StoragePool'),
    ('Pool_0_Unity-1_SSD_VPLEX1', 'Pool_0_Unity-1_SSD_VPLEX1'),
    ('Pool_0_Unity-2_SSD_VPLEX2', 'Pool_0_Unity-2_SSD_VPLEX2'),
    ('Pool_0_Unity-3_SSD_VPLEX3', 'Pool_0_Unity-3_SSD_VPLEX3'),
)

VPLEXES = (
    ('', 'Select VPLEX'),
    ('VPLEX#1', 'VPLEX#1'),
    ('VPLEX#2', 'VPLEX#2'),
    ('VPLEX#3', 'VPLEX#3'),
)

SWITCH_PRIMARY = (
    ('', 'Select Primary Switch.'),
    ('MDS9222#1', 'MDS9222#1'),
    ('MDS9222#3', 'MDS9222#3'),
)

SWITCH_SECONDARY = (
    ('', 'Select Secondary Switch.'),
    ('MDS9222#2', 'MDS9222#2'),
    ('MDS9222#4', 'MDS9222#4'),
)

class SearchForm(forms.Form):
    server_name = forms.CharField(
        max_length=30,
        required=True,
        label='Servername to search',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter hostname to search here'
            })
    )


class OperationForm(forms.Form):
    server_name = forms.CharField(
        required=True,
        max_length=40,
        widget=forms.TextInput(attrs={
            'class':'form-control',
            'placeholder': 'Enter Server name to provision',
            })
        )
    wwpn_1 = forms.CharField(
        required=False,
        max_length=23,
        widget=forms.TextInput(attrs={
            'class':'form-control',
            'placeholder': '(Optional) Enter primary WWPN',
            })
        )
    wwpn_2 = forms.CharField(
        required=False,
        max_length=23,
        widget=forms.TextInput(attrs={
            'class':'form-control',
            'placeholder': '(Optional) Enter secondary WWPN',
            })
        )
    backend_array_name = forms.ChoiceField(
        required=True,
        label='Backend ArrayName',
        widget=forms.Select(attrs={'class':'form-control'}),
        choices=BACKEND_ARRAYS
        )
    backend_storagepool_name = forms.ChoiceField(
        required=True,
        label='Backend StoragePool Name',
        widget=forms.Select(attrs={'class':'form-control'}),
        choices=STORAGE_POOLS
    )
    vplex_name = forms.ChoiceField(
        required=True,
        label='VPLEX Name',
        widget=forms.Select(attrs={'class':'form-control'}),
        choices=VPLEXES
    )
    primary_mds_switch = forms.ChoiceField(
        required=True,
        label='Primary MDS Switch',
        widget=forms.Select(attrs={'class':'form-control'}),
        choices=SWITCH_PRIMARY
    )
    secondary_mds_switch = forms.ChoiceField(
        required=True,
        label='Secondary MDS Switch',
        widget=forms.Select(attrs={'class':'form-control'}),
        choices=SWITCH_SECONDARY
    )
    lun_name_on_backend = forms.CharField(
        max_length=30,
        required=True,
        label='Lun Name on Backend',
        widget=forms.TextInput(attrs={
            'class':'form-control',
            'placeholder': 'Enter LUN name to be created here',
            })
        )
    lun_size = forms.CharField(
        max_length=6,
        required=True,
        label='Lun Size (GB)',
        widget=forms.TextInput(attrs={
            'class':'form-control',
            'placeholder': '100',
            })
        )
    thin_volume_or_not = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-control'}),
        label='Thin Volume or Not'
    )
    hlu_on_vplex = forms.CharField(
        required=True,
        label='HLU on VPLEX',
        max_length=3,
        widget=forms.TextInput(attrs={
            'class':'form-control',
            'placeholder': '1',
            })
    )
    message = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class':'form-control',
            'placeholder': 'Enter operational summary here',
            })
        )

