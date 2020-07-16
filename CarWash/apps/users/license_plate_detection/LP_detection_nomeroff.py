# Импорт все библиотек
import os
import cv2
import numpy as np
import sys
import json
import matplotlib.image as mpimg
from django.conf import settings
# Импортируем все классы
from .NomeroffNet import filters, RectDetector, TextDetector, OptionsDetector, Detector, textPostprocessing #textPostprocessingAsync
import tensorflow as tf

graph = tf.get_default_graph()

# LP = license plata
class LP_Detector():
    def __init__(self):
        print("\n[INFO] LOADING LICENSE PLATE DETECTOR...\n")
        # путь к корню
        self.NOMEROFF_NET_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../')

        # путь к MaskRCNN (если она не в корне)
        self.MASK_RCNN_DIR = os.path.join(self.NOMEROFF_NET_DIR, 'Mask_RCNN')
        self.MASK_RCNN_LOG_DIR = os.path.join(self.NOMEROFF_NET_DIR, 'logs')

        sys.path.append(self.NOMEROFF_NET_DIR)
        # Initialize npdetector with default configuration file.
        self.nnet = Detector(self.MASK_RCNN_DIR, self.MASK_RCNN_LOG_DIR)
        self.nnet.loadModel("latest")

        self.rectDetector = RectDetector()

        self.optionsDetector = OptionsDetector()
        self.optionsDetector.load("latest")

        # Активируем детектор текста
        self.textDetector = TextDetector({
            "eu_ua_2004_2015": {
                "for_regions": ["eu_ua_2015", "eu_ua_2004"],
                "model_path": "latest"
            },
            "eu": {
                "for_regions": ["eu", "eu_ua_1995"],
                "model_path": "latest"
            },
            "ru": {
                "for_regions": ["ru", "eu-ua-fake-lnr", "eu-ua-fake-dnr"],
                "model_path": "latest"
            },
            "kz": {
                "for_regions": ["kz"],
                "model_path": "latest"
            },
            "ge": {
                "for_regions": ["ge"],
                "model_path": "latest"
            }
        })

        # Путь к фотке для распознавания
        self.img_path = os.path.join(settings.STATICFILES_DIR + "/temp/detect_LP.jpg")

        self.max_img_w = 1600


    # Функция распознавания номера автомобиля
    def detect_license_plate(self):
        global graph
        print("\n[INFO] DETECTING LICENSE PLATE...\n")
        # фотка читается в GRAYSСALE обязательно
        img = cv2.imread(self.img_path, cv2.IMREAD_GRAYSCALE)

        # если пока что не было загружено в папку temp никакой фотки, то возвращаем "пустой" текст
        if img is None:
            return " "

        copy = cv2.imread(self.img_path)
        # явно в BGR переводим
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        # изменяем размер фото для увеличения скорости
        img_w = img.shape[1]
        img_h = img.shape[0]
        img_w_r = 1
        img_h_r = 1
        if img_w > self.max_img_w:
            resized_img = cv2.resize(img, (self.max_img_w, int(self.max_img_w/img_w*img_h)))
            img_w_r = img_w/self.max_img_w
            img_h_r = img_h/(self.max_img_w/img_w*img_h)
        else:
            resized_img = img
        with graph.as_default():
            NP = self.nnet.detect([resized_img])

            # Генерируем маску
            cv_img_masks = filters.cv_img_mask(NP)

            # Находим координаты бокса номера
            arrPoints = self.rectDetector.detect(cv_img_masks, outboundHeightOffset=0, fixGeometry=True, fixRectangleAngle=10)
            arrPoints[..., 1:2] = arrPoints[..., 1:2]*img_h_r
            arrPoints[..., 0:1] = arrPoints[..., 0:1]*img_w_r

            # Рисуем все боксы
            filters.draw_box(copy, arrPoints, (0, 255, 0), 3)

            # вырезаем эти зоны для дальнейшего анализа
            zones = self.rectDetector.get_cv_zonesBGR(img, arrPoints)

            # находим стандарт номера, соответствующий стране (номер будет отформатирован под него)
            regionIds, stateIds, countLines = self.optionsDetector.predict(zones)
            regionNames = self.optionsDetector.getRegionLabels(regionIds)

            # находим текст и форматируем по стандарту страны
            textArr = self.textDetector.predict(zones, regionNames, countLines)
            textArr = textPostprocessing(textArr, regionNames)
            try:
                print("\n[INFO] TEXT FOUND: " + textArr[0] + "\n")
            except:
                print("\n[INFO] TEXT FOUND: NOTHING \n")

            # Возвращаем полученный текст
            try:
                return textArr[0]
            except:
                return " "