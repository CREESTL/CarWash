from django.urls import path
from django.conf.urls import url
from django.conf import settings
from django.conf.urls.static import static


'''
URL привязки локальные
'''

from . import views
from django.conf.urls import url


app_name = 'users' # это используется в файле stream.html
urlpatterns = [
    path('', views.index, name='index'),
    path('index/', views.index, name='index'),  # доманяя страница
    path('register/', views.register, name='register'),  # страница регистрации
    path('login/', views.login, name='login'),  # базовая форма логина. template_name указывает на то, какую html сраницу надо загрузить
    path('logout/', views.logout, name='logout'), # выход из аккаунта
    path('detect_cars/', views.car_detection_page, name="car_detection_page"), # страница, где отображаютсявсе результаты
    url('get_text_from_detector/', views.get_text_from_detector, name="get_text_from_detector"), # получение текстовой информации об авто
    url('get_total/', views.get_total, name="get_total"), # получение общего числа авто на видео за вссе время
    url('get_image_from_detector/', views.get_image_from_detector, name="get_image_from_detector"), # получение кадра с авто
    url('detect_LP/', views.detect_LP, name="detect_LP"), # если полявилась новая машина, то ее номер детектится
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
