from CarWash.apps.users.car_type_recognition.car_type_recognition import CarTypeRecongizer
from CarWash.apps.users.car_detection_outside.pyimagesearch.centroidtracker import CentroidTracker
from CarWash.apps.users.car_detection_outside.pyimagesearch.trackableobject import TrackableObject
import numpy as np
import imutils
import dlib
import cv2
from django.conf import settings
import pyrebase


'''
Попробую многопоточность с OpenCV
'''

import cv2
import threading
from threading import Thread

'''
Класс распознавет авто в отдельном потоке
'''
class CarDetectorOutside():
    def __init__(self):
        print("\n[INFO] LOADING CAR DETECTOR...\n")

        # Конфигурация для нейронной сети
        #______________________________________________________________________________
        self.video = cv2.VideoCapture(settings.STATICFILES_DIR + "/input/audi.mp4")
        self.weights_path = settings.STATICFILES_DIR + "/yolo/yolov3_608.weights"
        self.cfg_path = settings.STATICFILES_DIR + "/yolo/yolov3_608.cfg"
        self.names_path = settings.STATICFILES_DIR + "/yolo/yolov3_608.names"
        with open(self.names_path) as f:
            self.CLASSES = [line.strip() for line in f.readlines()]
        # Создание самой нейронной сети
        self.net = cv2.dnn.readNet(self.weights_path, self.cfg_path)
        self.layer_names = self.net.getLayerNames()
        self.output_layers = [self.layer_names[i[0] - 1] for i in self.net.getUnconnectedOutLayers()]
        # Размеры входного изображения
        self.inpWidth = 608
        self.inpHeight = 608
        # инициализируем размеры кадра как пустые значения
        # они будут переназначены при анализе первого кадра и только
        # это ускорит работу программы
        self.width = None
        self.height = None

        # Конфигурация для трекера центроидов
        self.ct = CentroidTracker()
        self.ct.maxDisappeared = 10


        # сам список трекеров
        self.trackers = []
        self.class_ids = []


        # список объектов для трекинга
        self.trackableObjects = {}

        # классы объектов, которые следует обрабатывать, а остальные - игнорировать
        self.available_classes = ["car", "truck"]

        # полное число кадров в видео
        self.totalFrames = 0

        # счетчик машин и временная переменная
        self.total = 0
        self.old_total = 0
        self.temp = None

        # номер кадра видео
        self.frame_number = 0

        # пропуска кадром
        self.skip_frames = 5

        # это словарь с результатами обработки видео
        self.result = {
            "body_style": "не найдено",
            "model": "не найдено",
            "make": "не найдено",
            "total": "0"
        }
        # ______________________________________________________________________________

        # Пременная - результат работы self.detect_cars()
        self.generator = None

        # Переменная прекарщает работу детектора
        self.stopped = False

        # Переменная - обрабатываемый кадр
        self.frame = None

    # Функция создает поток, отвечающий за распознавания автомобилей
    # На вход получает кадр из VideoGetter(), который затем обрабатывается
    def start(self):
        print("[INFO] STARTING DETECTION_THREAD...")
        detection_outside_thread = Thread(target=self.get_generator, args=())
        detection_outside_thread.name = "detection_outside_thread"
        detection_outside_thread.start()
        return self # нужно возвращать self, чтобы можно было start() приравнять к какой-нибудь переменной

    # Фукнция останавливает распознавание
    def stop(self):
        self.stopped = True

    # Функция получает генератор из фунции detect_cars()
    def get_generator(self):
        self.generator = self.detect_cars()
    # Основная функция по распознаванию авто, возвращает генератор
    def detect_cars(self):
        print("[INFO] RUNNING detect_cars...")
        while not self.stopped:

            self.old_total = self.total
            self.frame_number += 1
            ret, frame = self.video.read()
            self.frame = frame
            if not ret:
                print("ERROR! Video not found!")
                self.stop()
            if frame is None:
                print("=============================================")
                print("The end of the video reached")
                print("Total number of cars on the video is ", self.total)
                print("=============================================")
                self.stop()
            # изменим размер кадра для ускорения работы
            frame = imutils.resize(frame, width=800)
            # для работы библиотеки dlib необходимо изменить цвета на RGB вместо BGR
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # размеры кадра
            if self.width is None or self.height is None:
                self.height, self.width, self.channels = frame.shape

            # этот список боксов может быть заполнен двумя способами:
            # (1) детектором объектов
            # (2) трекером наложений из библиотеки dlib
            rects = []

            if self.totalFrames % self.skip_frames == 0:

                # создаем пустой список трекеров
                self.trackers = []
                # список номером классов (нужен для подписи класса у боксов машин
                self.class_ids = []

                # получаем blob-модель из кадра и пропускаем ее через сеть, чтобы получить боксы распознанных объектов
                blob = cv2.dnn.blobFromImage(frame, 0.00392, (self.inpWidth, self.inpHeight), (0, 0, 0), True,
                                             crop=False)
                self.net.setInput(blob)
                outs = self.net.forward(self.output_layers)
                # анализируем список боксов
                for out in outs:
                    for detection in out:
                        scores = detection[5:]
                        class_id = np.argmax(scores)
                        confidence = scores[class_id]
                        # получаем ID наиболее "вероятных" объектов
                        if confidence > 0.4:
                            result_class = self.CLASSES[class_id]
                            # Если обнаружен не автомобиль или внедорожник, то игнорируем
                            if result_class not in self.available_classes:
                                continue

                            center_x = int(detection[0] * self.width)
                            center_y = int(detection[1] * self.height)
                            # это ИМЕННО ШИРИНА - то есть расстояние от левого края до правого
                            w = int(detection[2] * self.width)
                            # это ИМЕННО ВЫСОТА - то есть расстояние от верхнего края до нижнего
                            h = int(detection[3] * self.height)

                            # Координаты бокса (2 точки углов)
                            x1 = int(center_x - w / 2)
                            y1 = int(center_y - h / 2)
                            x2 = x1 + w
                            y2 = y1 + h

                            # возьмем максимальный радиус для CentroidTracker пропорционально размеру машины
                            self.ct.maxDistance = w

                            # рисую бокс для теста
                            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)
                            cv2.putText(frame, self.CLASSES[class_id], (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                        (0, 255, 0), 2)

                            # создаем трекер ДЛЯ КАЖДОЙ МАШИНЫ
                            tracker = dlib.correlation_tracker()
                            # создаем прямоугольник из бокса (фактически, это и есть бокс)
                            rect = dlib.rectangle(x1, y1, x2, y2)
                            # трекер начинает отслеживание КАЖДОГО БОКСА
                            tracker.start_track(rgb, rect)
                            # и каждый трекер помещается в общий массив
                            self.trackers.append(tracker)
                            self.class_ids.append(class_id)

            # если же кадр не явялется N-ым, то необходимо работать с массивом сформированных ранее трекеров, а не боксов
            else:
                for tracker, class_id in zip(self.trackers, self.class_ids):
                    status = "Tracking..."

                    '''
                    На одном кадре машина была распознана. Были получены координаты ее бокса. ВСЕ последующие 5 кадров эти координаты
                    не обращаются в нули, а изменяются благодяра update(). И каждый их этих пяти кадров в rects помещается предсказанное
                    программой местоположение бокса!
                    '''
                    tracker.update(rgb)
                    # получаем позицию трекера в списке(это 4 координаты)
                    pos = tracker.get_position()

                    # из трекера получаем координаты бокса, соответствующие ему
                    x1 = int(pos.left())
                    y1 = int(pos.top())
                    x2 = int(pos.right())
                    y2 = int(pos.bottom())

                    # рисую бокс
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)
                    cv2.putText(frame, self.CLASSES[class_id], (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0),
                                2)

                    # и эти координаты помещаем в главный список коодинат боксов ДЛЯ КАДРА (по нему и будет производиться рисование)
                    rects.append((x1, y1, x2, y2))

            objects = self.ct.update(rects)
            # алгоритм подсчета машин
            length = len(objects.keys())
            if length > self.total:
                self.total += length - self.total
            if self.temp is not None:
                if (length > self.temp):
                    self.total += length - self.temp
            if length < self.total:
                self.temp = length
            # Если количество машин увеличилось, то распознаем тип появившейся машины
            if self.total > self.old_total:
                # __________________________________________________________________
                # Определяю тип авто на кадре, если он там был обнаружен
                print("\n[INFO] NEW VEHICLE FOUND! DETECTING TYPE...\n")
                recognizer = CarTypeRecongizer(frame)
                video_url = recognizer.get_url()
                result = recognizer.recognize(video_url)

                # присваиваю полученный результат глобальной переменной

                self.result = {
                    "body_style": result["body_style"],
                    "make": result["make"],
                    "model": result["model"],
                    "total": str(self.total)
                }

            # анализируем массив отслеживаемых объектов
            for (objectID, centroid) in objects.items():
                # проверяем существует ли отслеживаемый объект для данного ID
                to = self.trackableObjects.get(objectID, None)

                # если его нет, то создаем новый, соответствующий данному центроиду
                if to is None:
                    to = TrackableObject(objectID, centroid)

                # в любом случае помещаем объект в словарь
                # (1) ID (2) объект
                self.trackableObjects[objectID] = to

            self.totalFrames += 1

            # запоминается текущее состояние кадра, чтобы потом его можно было вывести в другой функции
            self.frame = frame

            # кадр переводится в формат jpeg и выводится в генератор
            jpeg = cv2.imencode('.jpg', frame)[1].tostring()
            yield (b'--frame_1\r\n'b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n\r\n')







