"""vipr_django URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.urls import include

from controller.views import RunAnsible
from controller.views import DeviceSearch
from controller.urls import router as apirouter
from django.views.decorators.csrf import csrf_exempt


urlpatterns = [
    path('admin/', admin.site.urls),
    path('controller/', include('controller.urls')),
    path('api/v1/search/', csrf_exempt(DeviceSearch.as_view()), name='device_search'),
    path('api/v1/operation/', csrf_exempt(RunAnsible.as_view()), name='run_ansible'),
    path('api/v1/', include(apirouter.urls)),
]
