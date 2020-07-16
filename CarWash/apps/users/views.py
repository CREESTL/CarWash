from django.contrib import messages
from django.conf import settings
from django.shortcuts import render, redirect
from .forms import UserRegisterForm, UserLoginForm, VideoURLForm
from django.http import StreamingHttpResponse
from django.http import HttpResponse, JsonResponse
from django.views.decorators import gzip
import datetime



from CarWash.apps.users.car_detection_outside.car_detector_outside import CarDetectorOutside
from CarWash.apps.users.car_detection_inside.car_detector_inside import CarStopDetector
from CarWash.apps.users.car_type_recognition.car_type_recognition import CarTypeRecongizer
from CarWash.apps.users.license_plate_detection.LP_detection_nomeroff import LP_Detector
from CarWash.apps.users.car_type_recognition.car_type_recognition import db, storage, firebase, auth

license_downloadToken = None
video_downloadTOken = None

# это глобальная переменная, отвечающая за распознавание типов авто
car_detector_outside = CarDetectorOutside()

# это глобальная переменная, отвечающая за распознавание остановки авто внутри мойки
car_detector_inside = CarStopDetector()

# это глобальная переменная, отвечающая за распознавание номеров автомобилей
LP_detector = LP_Detector()
# это глобальная переменная - текст с номера авто
LP_text = "не найдено"
# это глобальная переменная, которая принимает значение True, если происходит распознавание госномера, и
# значение False, если распознавание не идет
# Необходима, чтобы не запускать функцию detect_LP несколько раз до окончания ее работы
LP_in_process = False

#========== ОБЩИЕ СТРАНИЦЫ ==========
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

#========================================




#========== РАСПОЗНАВАНИЕ АВТО СНАРУЖИ МОЙКИ ==========

# Функция обращается к ранее созданному объекту детектора и возвращает информацию, которую тот обработал
def get_text_from_detector_outside(request):
    if request.method == "GET":
        global car_detector_outside
        # сохраняю результат в FireBase ТОЛЬКО если общее число авто увеличилось на 1
        if car_detector_outside.total > car_detector_outside.old_total:
            push_to_firebase(request, None)
        # result - словарь типа JSON
        return HttpResponse(
            "<p><div class='text-muted'><i>Тип авто</i>: </div> <div class='text-info'><strong>" + car_detector_outside.result["body_style"] + "</strong></div></p>" +
            "<p><div class='text-muted'><i>Марка</i>: </div> <div class='text-info'><strong>" + car_detector_outside.result["make"] + "</strong></div></p>" +
            "<p><div class='text-muted'><i>Модель</i>: </div> <div class='text-info'><strong>" + car_detector_outside.result["model"] + "</strong></div></p>"
        )


# Функция возвращает общее число авто на видео за все время
def get_total(request):
    global car_detector_outside
    total = str(car_detector_outside.total)
    return HttpResponse(
        "<p><div class='text-muted'><i>Общее число авто</i>: </div> <div class='text-info'><strong>" + total + "</strong></div></p>"
    )


# Функция обращается к ранее созданному объекту детектора и возвращает кадр с автомобилями
@gzip.gzip_page
def get_image_from_detector_outside(request):
    print("\n[INFO] get_image_from_detector ACTIVATED!\n")
    global car_detector_outside
    # Функция запускает поток для распознавания авто
    car_detector_outside.start()
    return StreamingHttpResponse(car_detector_outside.generator, content_type="multipart/x-mixed-replace;boundary=frame")



# Функция помещает результаты обработки в FireBase
# stopped_from - время, когда авто остановилось, stopped_to - время, когда авто начало двигаться или исчезло из кадра
def push_to_firebase(request, LP_text=None):
    print("\n[INFO] SAVING RESULTS TO FIREBASE...\n")
    global car_detector_outside
    global car_detector_inside
    #today = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    # Если общее число авто пока не известно, то его в БД не пишем
    offset = datetime.timezone(datetime.timedelta(hours=3))
    # общее время в формате: 2020-06-27 20:14:46.234231+3.00
    now = str(datetime.datetime.now(offset))
    # дата в формате 2020-06-27
    todays_date = now[:10]
    # время в формате 20:14:46
    time = now[11:19]
    # Номер авто распознается на внутренней камере. Поэтому в этом случае мы записываем просто номер,
    # время начала и конца остановки
    # В этом случае обращаемся к внутреннему детектору
    if LP_text is not None:
        result_to_update = {
            "Госномер авто: ": LP_text
        }
        # Если в детекторе уже были обнаружены остановившиеся автомобили, то добавляем их в результат, который
        # будет записан в БД
        # result - это словарь: ID -> [время начала остановки, время конца остановки]
        if car_detector_inside.result.keys() != []:
            for ID, [stopped_from, stopped_to] in car_detector_inside.result.items():
                result_to_update[str(ID)] = [stopped_from, stopped_to]
        # Если известно время начала и конца остановки, то нет смысла записывать время в БД
        results_put_response = db.child('info').child(todays_date).update(result_to_update)
    # Если же работа производилась с внешней камеры, то там распознается только общая информация об авто
    # В этом случае обращаемся к внешнему детектору
    else:
        result_to_update = {
            "Тип авто: ": car_detector_outside.result["body_style"],
            "Марка: ": car_detector_outside.result["make"],
            "Модель: ": car_detector_outside.result["model"],
            "Общее число авто: ": car_detector_outside.result["total"],
        }
        results_put_response = db.child('info').child(todays_date).child(time).update(result_to_update)


# Функция рендерит страницу, где отображается видео с распознанными машинами снаружи мойки
def car_detection_outside_page(request):
    if auth.current_user is not None:
        logged_in = True
    else:
        logged_in = False
    if request.method == 'POST':
        return HttpResponse('')
    return render(request, 'users/car_detection_outside.html', {"logged_in": logged_in})  # рендерится страница, на которую будет загружаться видео


#========================================



#========== РАСПОЗНАВАНИЕ АВТО ВНУТРИ МОЙКИ ==========

# Функция рендерит страницу, где отображается видео с распознанными машинами изнутри мойки
def car_detection_inside_page(request):
    if auth.current_user is not None:
        logged_in = True
    else:
        logged_in = False
    if request.method == 'POST':
        return HttpResponse('')
    return render(request, 'users/car_detection_inside.html', {"logged_in": logged_in})  # рендерится страница, на которую будет загружаться видео


# Функция обращается к ранее созданному объекту детектора и возвращает кадр с автомобилями
@gzip.gzip_page
def get_image_from_detector_inside(request):
    global car_detector_inside
    # запускаем поток, который запускает функцию detect_car_stop и присваивает ее генератору
    car_detector_inside.start()
    return StreamingHttpResponse(car_detector_inside.generator, content_type="multipart/x-mixed-replace;boundary=frame")

# Функция обращается к ранее созданному объекту детектора внутри мойки и возвращает данные, которые он обработал
def get_text_from_detector_inside(request):
    if request.method == "GET":
        global car_detector_inside
        # result - словарь типа JSON
        # Перебираю каждый остановившийся автомобиль и вывожу инфу о времени начала и конца его остановки на сайт
        response_to_return = ""
        # dict.keys() не поддерживает индексацию, поэтому я создам свой массив из ключей, чтобы было удобнее работать
        # если словарь не пустой, то дополняем response
        if car_detector_inside.result.keys():
            keys = [key for key in car_detector_inside.result.keys()]
            for ID in keys:
                response_to_return += "<p><div class='text-muted'>Автомобиль №" + str(ID+1) + " не двигался <i>с</i> <strong>" + str(car_detector_inside.result[ID][0]) + "</strong> <i>до</i> <strong>" + str(car_detector_inside.result[ID][1]) + "</strong></p>"
        return HttpResponse(
            response_to_return
        )

# Функция проверяет, увеличилось ли количество машин на кадре. И если да, то начинает распознавания номеров
def detect_LP(request):
    global LP_in_process
    global LP_detector
    global car_detector_inside
    global LP_text
    # Если на кадре появилось новое авто, то производим распознавание номера
    if car_detector_inside.total > car_detector_inside.old_total:
        if not LP_in_process:
            # detect_license_plate() работает довольно долго, поэтому на время ее работы глобальный переключатель
            # делаем положительным чтобы эта (detect_LP) функция не запустила распознавание еще раз
            LP_in_process = True
            LP_text = LP_detector.detect_license_plate()
            # Записываем в БД номер авто, и (если оно есть) время начала и конца остановки
            push_to_firebase(request, LP_text)
            LP_in_process = False
            # после распознавания необходимо приравнять эти две переменные, чтобы распознавание не началось заново
            # то есть было 0 машин, потом стало 3 машины, распознали номера, сказали, что теперь 3 машины, ждем, пока не станет больше
            car_detector_inside.old_total = car_detector_inside.total
            print(f"\n\n\t\tnow old_total = {car_detector_inside.total}  and old_total is {car_detector_inside.old_total}\n\n")
            return HttpResponse(
                "<p><div class='text-muted'><i>Госномер авто</i>: </div> <div class='text-info'><strong>" + LP_text + "</strong></div></p>"
            )
    return HttpResponse(" ")
#========================================