from django.contrib import admin
from django.urls import path, include
from django.conf import settings # файл settings.py
from django.conf.urls.static import static



urlpatterns = [
    path('admin/', admin.site.urls, name="admin"),
    path('', include('users.urls')),

]
