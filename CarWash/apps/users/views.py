from django.contrib import messages
from django.conf import settings
from django.shortcuts import render, redirect
from .forms import UserRegisterForm, UserLoginForm, VideoURLForm
from django.http import StreamingHttpResponse
from django.http import HttpResponse, JsonResponse
from django.views.decorators import gzip
from time import gmtime, strftime
import datetime
import pytz




import os
import pyrebase
import cv2
import pafy
import imutils
import time

from CarWash.apps.users.car_detection.car_detector import CarDetector
from CarWash.apps.users.car_type_recognition.car_type_recognition import CarTypeRecongizer
from CarWash.apps.users.license_plate_detection.LP_detection_nomeroff import LP_Detector
from CarWash.apps.users.car_type_recognition.car_type_recognition import db, storage, firebase, auth

license_downloadToken = None
video_downloadTOken = None

# это глобальная переменная, отвечающая за распознавание типов авто
#car_detector = CarDetector(settings.STATICFILES_DIR + '/input/audi.mp4')
car_detector = None

# это глобальная переменная, отвечающая за распознавание номеров автомобилей
LP_detector = LP_Detector()
# это глобальная переменная - текст с номера авто
LP_text = "не найдено"


# Страница регистрации
def register(request):
    if request.method == 'POST':

        # Создается форма, заполненная данными, который ввел пользователь
        form = UserRegisterForm(request.POST)

        # Если форма корректная (Django ее сам проверяет), то создается пользователь
        if form.is_valid():
            email = form.cleaned_data.get("email")
            password1 = form.cleaned_data.get("password1")
            password2 = form.cleaned_data.get("password2")
            username = form.cleaned_data.get("username")

            # Создается пользователь и сохраняется в FireBase
            user = auth.create_user_with_email_and_password(email, password1)

            # Сообщение об успешной регистрации
            messages.info(request, f'Вы успешно зарегистрировались')
            return redirect('../login')
        # Если форма некорректная, то выводится сообщение об этом
        else:
            messages.info(request, f'Некорректные данные')
            return render(request, "users/register.html", {"form": form})
    # Если пользователь еще ничего не вводил, со создается пустая форма
    else:
        form = UserRegisterForm()
        return render(request, 'users/register.html', {"form": form})


# Домашняя страница
def index(request):
    if auth.current_user is not None:
        logged_in = True
    else:
        logged_in = False
    global LP_text
    # этот текст изменяется на странице стрима, но при переходе на домашнюю страницу он должен обнуляться
    LP_text = "не найдено"
    return render(request, 'users/index.html', {"logged_in": logged_in})


# Страница входа
def login(request):
    if request.method == "POST":
        # Создается форма, заполненная данными, который ввел пользователь
        form = UserLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password1")

            try:
                login = auth.sign_in_with_email_and_password(email, password)
                messages.info(request, f'Вы успешно вошли в аккаунт')
            except Exception:
                auth.current_user = None
                messages.info(request, f'Некорректные данные')
                return render(request, 'users/login.html', {"form": form})
            if auth.current_user:
                logged_in = True
            else:
                logged_in = False

            return render(request, 'users/index.html', {"logged_in":logged_in})
        # Если форма некорректная, то выводится сообщение об этом
        else:
            messages.info(request, f'Некорректные данные')
            return render(request, "users/login.html", {"form": form})
    # Если пользователь еще ничего не вводил, со создается пустая форма
    else:
        form = UserLoginForm()
        return render(request, 'users/login.html', {"form": form})


# Страница выхода из аккаунта
def logout(request):
    if auth.current_user is not None:
        auth.current_user = None # так делается выход из аккаунта
        messages.info(request, f'Вы успешно вышли из аккаунта')
        return render(request, 'users/logout.html')
    else:
        logged_in = False
        return render(request, 'users/logout.html', {"logged_in": logged_in})


# Функция рендерит страницу, где отображается видео с распознанными машинами снаружи мойки
def car_detection_outside_page(request):
    if auth.current_user is not None:
        logged_in = True
    else:
        logged_in = False
    if request.method == 'POST':
        return HttpResponse('')
    return render(request, 'users/car_detection_outside.html', {"logged_in": logged_in})  # рендерится страница, на которую будет загружаться видео

# Функция рендерит страницу, где отображается видео с распознанными машинами изнутри мойки
def car_detection_inside_page(request):
    if auth.current_user is not None:
        logged_in = True
    else:
        logged_in = False
    if request.method == 'POST':
        return HttpResponse('')
    return render(request, 'users/car_detection_inside.html', {"logged_in": logged_in})  # рендерится страница, на которую будет загружаться видео



# Функция обращается к ранее созданному объекту детектора и возвращает информацию, которую тот обработал
def get_text_from_detector(request):
    if request.method == "GET":
        global car_detector
        # сохраняю результат в FireBase ТОЛЬКО если общее число авто увеличилось на 1
        if car_detector.total > car_detector.old_total:
            push_to_firebase(request, None)
        # result - словарь типа JSON
        return HttpResponse(
            "<p><div class='text-muted'><i>Тип авто</i>: </div> <div class='text-info'><strong>" + car_detector.result["body_style"] + "</strong></div></p>" +
            "<p><div class='text-muted'><i>Марка</i>: </div> <div class='text-info'><strong>" + car_detector.result["make"] + "</strong></div></p>" +
            "<p><div class='text-muted'><i>Модель</i>: </div> <div class='text-info'><strong>" + car_detector.result["model"] + "</strong></div></p>"
        )


# Функция возвращает общее число авто на видео за все время
def get_total(request):
    global car_detector
    total = str(car_detector.total)
    return HttpResponse(
        "<p><div class='text-muted'><i>Общее число авто</i>: </div> <div class='text-info'><strong>" + total + "</strong></div></p>"
    )

# Функция обращается к ранее созданному объекту детектора и возвращает кадр с автомобилями
@gzip.gzip_page
def get_image_from_detector(request):
    print("\n[INFO] get_image_from_detector ACTIVATED!\n")
    global car_detector
    car_detector = CarDetector(settings.STATICFILES_DIR + '/input/audi.mp4')
    return StreamingHttpResponse(car_detector.detect_cars(), content_type="multipart/x-mixed-replace;boundary=frame")



# Функция проверяет, увеличилось ли количество машин на кадре. И если да, то начинает распознавания номеров
def detect_LP(request):
    global LP_detector
    global car_detector
    global LP_text
    # Если количество машин возрастает - начинается распознавание номеров
    if car_detector.total > car_detector.old_total:
        LP_text = LP_detector.detect_license_plate()
        push_to_firebase(request, LP_text)
        return HttpResponse(
            "<p><div class='text-muted'><i>Госномер авто</i>: </div> <div class='text-info'><strong>" + LP_text + "</strong></div></p>"
        )
    else:
        return HttpResponse(
            "<p><div class='text-muted'><i>Госномер авто</i>: </div> <div class='text-info'><strong>" + LP_text + "</strong></div></p>"
        )


# Функция помещает результаты обработки в FireBase
def push_to_firebase(request, LP_text=None):
    print("\n[INFO] SAVING RESULTS TO FIREBASE...\n")
    global car_detector
    #today = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    # Если общее число авто пока не известно, то его в БД не пишем
    offset = datetime.timezone(datetime.timedelta(hours=3))
    # общее время в формате: 2020-06-27 20:14:46.234231+3.00
    now = str(datetime.datetime.now(offset))
    # дата в формате 2020-06-27
    todays_date = now[:10]
    # время в формате 20:14:46
    time = now[11:19]
    # Если номер авто был распознан, то он также помещается в БД
    if LP_text is not None:
        result_to_update = {
            "Тип авто: ": car_detector.result["body_style"],
            "Марка: ": car_detector.result["make"],
            "Модель: ": car_detector.result["model"],
            "Общее число авто: ": car_detector.result["total"],
            "Госномер авто: ": LP_text
        }
        results_put_response = db.child('info').child(todays_date).child(time).update(result_to_update)
    # Если нет, то только общая информация об авто помещается в БД
    else:
        results_put_response = db.child('info').child(todays_date).child(time).update(car_detector.result)


