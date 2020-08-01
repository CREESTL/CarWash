import os
import cv2
import sys
import tensorflow as tf
from django.conf import settings


# import all necessary classes
from .NomeroffNet import filters, RectDetector, TextDetector, OptionsDetector, Detector, textPostprocessing #textPostprocessingAsync

graph = tf.get_default_graph()

'''
This class detects car number on it's license plate
'''
class LP_Detector():
    def __init__(self):
        print("\n[INFO] LOADING LICENSE PLATE DETECTOR...\n")
        self.NOMEROFF_NET_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../')

        # path to MaskRCNN
        self.MASK_RCNN_DIR = os.path.join(self.NOMEROFF_NET_DIR, 'Mask_RCNN')
        self.MASK_RCNN_LOG_DIR = os.path.join(self.NOMEROFF_NET_DIR, 'logs')

        sys.path.append(self.NOMEROFF_NET_DIR)
        # Initialize npdetector with default configuration file.
        self.nnet = Detector(self.MASK_RCNN_DIR, self.MASK_RCNN_LOG_DIR)
        self.nnet.loadModel("latest")

        self.rectDetector = RectDetector()

        self.optionsDetector = OptionsDetector()
        self.optionsDetector.load("latest")

        # Initializing text detector
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

        # path to the image to process
        # image was places there by another module of my program
        self.img_path = os.path.join(settings.STATICFILES_DIR + "/temp/detect_LP.jpg")

        self.max_img_w = 1600


    # main funtion
    def detect_license_plate(self):
        global graph
        print("\n[INFO] DETECTING LICENSE PLATE...\n")
        # it is important to convert image to GRAYSCALE
        img = cv2.imread(self.img_path, cv2.IMREAD_GRAYSCALE)

        # if there is no image to process - return empty line
        if img is None:
            return " "

        copy = cv2.imread(self.img_path)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        # resize image to increase speed
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

            # generate a mask
            cv_img_masks = filters.cv_img_mask(NP)

            # find number's box coordinates
            arrPoints = self.rectDetector.detect(cv_img_masks, outboundHeightOffset=0, fixGeometry=True, fixRectangleAngle=10)
            arrPoints[..., 1:2] = arrPoints[..., 1:2]*img_h_r
            arrPoints[..., 0:1] = arrPoints[..., 0:1]*img_w_r

            # draw all boxes
            filters.draw_box(copy, arrPoints, (0, 255, 0), 3)

            # cropp boxes for further analysis
            zones = self.rectDetector.get_cv_zonesBGR(img, arrPoints)

            # find a "number standard" according to the country
            regionIds, stateIds, countLines = self.optionsDetector.predict(zones)
            regionNames = self.optionsDetector.getRegionLabels(regionIds)

            # detect text and format it according to "number standard"
            textArr = self.textDetector.predict(zones, regionNames, countLines)
            textArr = textPostprocessing(textArr, regionNames)
            try:
                print("\n[INFO] TEXT FOUND: " + textArr[0] + "\n")
            except:
                print("\n[INFO] TEXT FOUND: NOTHING \n")

            # return the result (text)
            try:
                return textArr[0]
            except:
                return " "