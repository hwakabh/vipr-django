from django.conf.urls import url
from django.urls import path

from rest_framework import routers
from controller import views

router = routers.DefaultRouter()
router.register(r'cataloghist', views.CatalogViewSet)

urlpatterns = [
    url(r'^uploads', views.upload_menu, name='uploads'),
    url(r'^histories', views.history_menu, name='histories'),
    path('history/<int:pk>',views.catalog_details, name='history'),
    url(r'^redirect', views.page_not_found, name='redirect'),
    url(r'^', views.front_main, name='home'),
]
