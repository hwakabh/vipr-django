from django.conf.urls import url

from controller import views

urlpatterns = [
    url(r'^', views.front_main, name='home'),
    url(r'^uploads', views.upload_menu, name='uploads'),
    url(r'^histories', views.history_menu, name='histories'),
    url(r'^redirect', views.page_not_found, name='redirect'),
    url(r'^', views.front_main, name='home'),
]
