from django.contrib import admin
from django.conf.urls import url
from django.urls import path

from django.conf import settings
from django.conf.urls.static import static

from controller import views

urlpatterns = [
    url(r'^', views.front_main, name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
