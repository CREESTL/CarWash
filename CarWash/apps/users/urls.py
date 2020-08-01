from django.urls import path
from django.conf.urls import url
from django.conf import settings
from django.conf.urls.static import static

from . import views


app_name = 'users'
urlpatterns = [
    path('', views.index, name='index'),
    path('index/', views.index, name='index'),  # home page
    path('register/', views.register, name='register'),  # registration page
    path('login/', views.login, name='login'),  # login page
    path('logout/', views.logout, name='logout'), # logout page
    path('car_detection_outside/', views.car_detection_outside_page, name="car_detection_page"), # outside camera page
    path('car_detection_inside/', views.car_detection_inside_page, name="car_detection_page"), # inside camera page
    url('get_text_from_detector_outside/', views.get_text_from_detector_outside, name="get_text_from_detector_outside"), # getting results from outside camera
    url('get_text_from_detector_inside/', views.get_text_from_detector_inside, name="get_text_from_detector_inside"), # getting results from inside camera
    url('get_total/', views.get_total, name="get_total"), # getting total number of cars passed by the car wash
    url('get_image_from_detector_outside/', views.get_image_from_detector_outside, name="get_image_from_detector_outside"), # streaming frames from outside detector
    url('get_image_from_detector_inside/', views.get_image_from_detector_inside, name="get_image_from_detector_inside"), # streaming frames from inside detector
    url('detect_LP/', views.detect_LP, name="detect_LP"), # license plate detection
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
