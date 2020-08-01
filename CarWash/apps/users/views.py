from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import UserRegisterForm, UserLoginForm
from django.http import StreamingHttpResponse
from django.http import HttpResponse
from django.views.decorators import gzip
import datetime

'''
ATTENTION!

This program was created for one car wash in Russia, so you can find some Russian words here in the code
Don`t worry I'll write all comments ir English
'''





# importing car type detector, car stop detector, and license plate detector
from CarWash.apps.users.car_detection_outside.car_detector_outside import CarDetectorOutside
from CarWash.apps.users.car_detection_inside.car_detector_inside import CarStopDetector
from CarWash.apps.users.license_plate_detection.LP_detection_nomeroff import LP_Detector

# importing some modules to work with FireBase
from CarWash.apps.users.car_type_recognition.car_type_recognition import db, auth


license_downloadToken = None
video_downloadTOken = None

# initializing all detectors
car_detector_outside = CarDetectorOutside()
car_detector_inside = CarStopDetector()
LP_detector = LP_Detector()

# text from license plate(LP)
LP_text = "не найдено"

# this variable is True when LP detection is in process and False when it`s not
LP_in_process = False

# Dictionary: car ID -> LP
ID_LP = {}

#========== Common pages ==========
# registration page
def register(request):
    if request.method == 'POST':

        # a registration form is created and filled by user
        form = UserRegisterForm(request.POST)

        # if the form is correct then a new user is created
        if form.is_valid():
            email = form.cleaned_data.get("email")
            password1 = form.cleaned_data.get("password1")
            password2 = form.cleaned_data.get("password2")
            username = form.cleaned_data.get("username")

            # creating user and saving to FireBase
            user = auth.create_user_with_email_and_password(email, password1)

            # message about successful registration
            messages.info(request, f'Вы успешно зарегистрировались')
            return redirect('../login')
        # message about incorrect form
        else:
            messages.info(request, f'Некорректные данные')
            return render(request, "users/register.html", {"form": form})
    # creating a blank form for user input
    else:
        form = UserRegisterForm()
        return render(request, 'users/register.html', {"form": form})


# home page
def index(request):
    if auth.current_user is not None:
        logged_in = True
    else:
        logged_in = False
    global LP_text
    # this text is changing if you are on stream page but when you go back to home page it should be reset
    LP_text = "не найдено"
    return render(request, 'users/index.html', {"logged_in": logged_in})


# login page
def login(request):
    if request.method == "POST":
        # login form is created and filled by user
        form = UserLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password1")
            # trying to log in
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
        # message about incorrect form
        else:
            messages.info(request, f'Некорректные данные')
            return render(request, "users/login.html", {"form": form})
    # creating a blank form for user input
    else:
        form = UserLoginForm()
        return render(request, 'users/login.html', {"form": form})


# logout page
def logout(request):
    if auth.current_user is not None:
        auth.current_user = None # deleting current user
        messages.info(request, f'Вы успешно вышли из аккаунта')
        return render(request, 'users/logout.html')
    else:
        logged_in = False
        return render(request, 'users/logout.html', {"logged_in": logged_in})

#========================================




#========== CAR DETECTION OUTSIDE THE CAR WASH ==========

# this function puts into FireBase information like this:
# 1) car type
# 2) car make
# 3) car model
# 4) total number of cars


def push_general_car_info_to_firebase(request):
    global car_detector_outside
    # getting current time and date in format:
    # year-month-day hours:minutes:seconds
    offset = datetime.timezone(datetime.timedelta(hours=3))
    now = str(datetime.datetime.now(offset))
    # today's date
    todays_date = now[:10]
    # current time
    time = now[11:19]
    # if we work with outside detector that means that we get general info about vehicle
    # we put this info to FireBase only if car type was detected
    if car_detector_outside.car_recognized == True:
        result_to_update = {}
        for ID, info in car_detector_outside.result.items():
            result_to_update[f"Авто №{ID}"] = info
        # all info about lase detected car is written into folder with name = current time
        results_put_response = db.child('info').child("outside_camera").child(todays_date).child(time).update(result_to_update)
        # those two switches become False to make detector work correctly
        # I could have switched them in the detector itself, but the thing is that I'm working with AJAX requests that happen
        # every 3-5 seconds and THIS function only activates with each ot those requests and until this function finishes
        # it's work those switches must stay in one (positive) position
        # yeah, it's complicated, but that's the only way I've found to make things work proper
        car_detector_outside.car_recognized = False
        car_detector_outside.cars_were_cropped = False
        # now those switches can become True inside car_detector_outside.py


# function returns text info from detector
# this info is later shown on web-page
def get_text_from_detector_outside(request):
    if request.method == "GET":
        # trying to put info to FireBase
        push_general_car_info_to_firebase(request)
        global car_detector_outside
        response_to_return = ""
        for ID, info in car_detector_outside.result.items():
            # at first after detector has been initialized all IDs are equal to "не найдено" ("not found")
            if ID != "не найдено":
                # on the web-page you can see information only about those cars that are ON the frame
                # if a car moves away information is not shown any more
                if ID in car_detector_outside.current_IDs:
                    response_to_return += "<p><div class='text-muted'><strong><i>Авто №" + str(ID) + "</i></strong></div></p>"
                    response_to_return += "<p><div class='text-muted'><i>Тип авто</i>: </div> <div class='text-info'><strong>" + info["body_style"] + "</strong></div></p>"
                    response_to_return += "<p><div class='text-muted'><i>Марка</i>: </div> <div class='text-info'><strong>" + info["make"] + "</strong></div></p>"
                    response_to_return += "<p><div class='text-muted'><i>Модель</i>: </div> <div class='text-info'><strong>" + info["model"] + "</strong></div></p>"
        return HttpResponse(response_to_return)

# function returns total number of cars on the video
def get_total(request):
    global car_detector_outside
    # it looks better if a total number of cars is shown on a page at the same time as all other info
    if car_detector_outside.show_total:
        total = str(car_detector_outside.total)
        return HttpResponse(
            "<p><div class='text-muted'><i>Общее число авто</i>: </div> <div class='text-info'><strong>" + total + "</strong></div></p>"
        )
    else:
        return HttpResponse(" ")


'''
I've been trying to understand how to display OpenCV frame onto a Django web-page for several weeks! And I've finally
found a resolution of this problem. So this is how it works:
1) On the HTML page made to "frame steaming"(car_detection_outside.html) there is and "src" attribute in "img" tag. In this attribute I've 
wrote a URL that calls this function
2) This function takes and object of car detector and starts a separate thread in which detection takes place
3) That thread yields it's results to "generator" variable
4) The results from this variable are streamed to the HTMl page. The results are basically just processed frames of video

So in other words: detector is working independently processing frames, this function takes processed frames and puts them
onto HTML page
'''

@gzip.gzip_page
def get_image_from_detector_outside(request):
    global car_detector_outside
    # car detection thread starts
    car_detector_outside.start()
    return StreamingHttpResponse(car_detector_outside.generator, content_type="multipart/x-mixed-replace;boundary=frame")


# function renders page where all results of car detection outside the car wash are displayed
def car_detection_outside_page(request):
    if auth.current_user is not None:
        logged_in = True
    else:
        logged_in = False
    if request.method == 'POST':
        return HttpResponse('')
    return render(request, 'users/car_detection_outside.html', {"logged_in": logged_in})


#========================================



#========== CAR DETECTION OUTSIDE THE CAR WASH ==========

# function renders page where all results of car detection inside the car wash are displayed
def car_detection_inside_page(request):
    if auth.current_user is not None:
        logged_in = True
    else:
        logged_in = False
    if request.method == 'POST':
        return HttpResponse('')
    return render(request, 'users/car_detection_inside.html', {"logged_in": logged_in})


# works exactly like "get_image_from_detector_outside()" function but for detector inside the car wash
@gzip.gzip_page
def get_image_from_detector_inside(request):
    global car_detector_inside
    car_detector_inside.start()
    return StreamingHttpResponse(car_detector_inside.generator, content_type="multipart/x-mixed-replace;boundary=frame")


# this function puts into FireBase information like this:
# car with LP: *license plate number*
#     ID = ...
#     was standing from ...
#     was standing till ...
# this info is formed as two dictionaries

def push_LP_stoptime_to_firebase(request):
    global ID_LP
    global car_detector_inside
    # getting current time and date in format:
    # year-month-day hours:minutes:seconds
    offset = datetime.timezone(datetime.timedelta(hours=3))
    # общее время в формате: 2020-06-27 20:14:46.234231+3.00
    now = str(datetime.datetime.now(offset))
    # today's date
    todays_date = now[:10]
    # current time
    time = now[11:19]
    result_to_update = {}
    if ID_LP.items():
        for ID, LP_text in ID_LP.items():
            if LP_text != " ":
                # put LP to DB only if it has been detected
                result_to_update[f"Авто c госномером {LP_text}"] = {}
                result_to_update[f"Авто c госномером {LP_text}"]["ID = "] = ID
                if ID in car_detector_inside.result.keys():
                    # if we know how long the car was not moving - write it to DB
                    if car_detector_inside.result[ID][0] and car_detector_inside.result[ID][1]:
                        result_to_update[f"Авто c госномером {LP_text}"]["Стояло с "] = car_detector_inside.result[ID][0]
                        result_to_update[f"Авто c госномером {LP_text}"]["Стояло до "] = car_detector_inside.result[ID][1]
            # If LP hasn't been detected then we just write the time when the car stopped
            else:
                if ID in car_detector_inside.result.keys():
                    if car_detector_inside.result[ID][0] and car_detector_inside.result[ID][1]:
                        result_to_update[f"Неопознанное авто c ID = {ID}"] = {}
                        result_to_update[f"Неопознанное авто c ID = {ID}"]["Стояло с "] = car_detector_inside.result[ID][0]
                        result_to_update[f"Неопознанное авто c ID = {ID}"]["Стояло до "] = car_detector_inside.result[ID][1]
            # if the information dictionary is not empty - write it to DB
            if result_to_update != {}:
                print("\n[INFO] SAVING LP TO FIREBASE\n")
                results_put_response = db.child('info').child('inside_camera').child(todays_date).update(result_to_update)

# function returns text info from detector
# this info is later shown on web-page
def get_text_from_detector_inside(request):
    if request.method == "GET":
        global car_detector_inside
        # trying to put info to FireBase
        push_LP_stoptime_to_firebase(request)
        # pick each stopped car and display info about the time when it has stopped and the time it started moving onto web-page
        response_to_return = ""
        # если словарь не пустой, то дополняем response
        if car_detector_inside.result.keys():
            keys = [key for key in car_detector_inside.result.keys()]
            for ID in keys:
                # display info only about those cars that are ON the frame
                if ID in car_detector_inside.current_IDs:
                    response_to_return += "<p><div class='text-muted'>Автомобиль c ID " + str(ID) + " не двигался <i>с</i> <strong>" + str(car_detector_inside.result[ID][0]) + "</strong> <i>до</i> <strong>" + str(car_detector_inside.result[ID][1]) + "</strong></p>"
        return HttpResponse(
            response_to_return
        )

# function connects latest detected LP to lates arrived vehicle
def connect_LP_to_ID(request, LP_text):
    global ID_LP
    IDs = list(car_detector_inside.ID_boxes.keys())
    last_arrived_car_ID = IDs[-1]
    ID_LP[last_arrived_car_ID] = LP_text


# function detects LP(license_plate) on the frame
def detect_LP(request):
    global LP_in_process
    global LP_detector
    global car_detector_inside
    global LP_text
    global ID_LP
    response_to_return = ""
    # We assume that cars enter car wash box (a place where they are washed) one by one. So the maximum amount of LPs on the frame is 1
    # So if there is a car in "long_stopped_cars" it means that this is the only car in the box and it has one LP that we can detect
    if (car_detector_inside.total > car_detector_inside.old_total) and (car_detector_inside.long_stopped_cars or car_detector_inside.long_stopped_trucks):
        print(f"THERE ARE STOPPED CARS --- DETECT LP!")
        if not LP_in_process:
            # detect_license_plate() works pretty long, so I switch LP_in_process to True until the LP is detected
            # that helps prevent the algorithm trying to detect the LP before it has finished detected previous one
            LP_in_process = True
            LP_text = LP_detector.detect_license_plate()
            # connect latest detected LP to the latest arrived car
            connect_LP_to_ID(request, LP_text)
            LP_in_process = False
            # As I've written before, many of functions in this file are activated with AJAX requests. Those requests activate
            # these functions only if current number of cars increases, BUT AJAX requests are sent each 3-5 seconds and if the total number
            # increased between them, then the function won't be activated. So I had to make "old_total" and "total" variables equal only
            # after the function was activated and finished working.
            # In other words: a new car appears on the frame, total increases (becomes more than old_total), we wait for AJAX request,
            # request calls this function< this function sees that total is more than old_total, it starts detecting LP, after the detection
            # is done it makes those two variables equal until another car comes to the cameras line of sight
            car_detector_inside.old_total = car_detector_inside.total
            print(f"\n\n\t\tnow old_total = {car_detector_inside.total}  and old_total is {car_detector_inside.old_total}\n\n")
            for ID, LP_text in ID_LP.items():
                if LP_text[0] != " ":
                    response_to_return += "<p><div class='text-muted'><i>Госномер авто c ID = <strong>" + str(ID) + "</strong></i>: </div> <div class='text-info'><strong>" + LP_text + "</strong></div></p>"
    return HttpResponse(
        response_to_return
    )



#========================================