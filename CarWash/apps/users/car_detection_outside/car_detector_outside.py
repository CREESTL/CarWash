from CarWash.apps.users.car_type_recognition.car_type_recognition import CarTypeRecongizer
from CarWash.apps.users.car_detection_outside.pyimagesearch.centroidtracker import CentroidTracker
from CarWash.apps.users.car_detection_outside.pyimagesearch.trackableobject import TrackableObject
import numpy as np
import imutils
import dlib
import cv2
import os
from django.conf import settings
import math as maths
from threading import Thread

'''
This class detects general info about car: type, model, total number, etc...
'''
class CarDetectorOutside():
    def __init__(self):
        print("\n[INFO] LOADING CAR DETECTOR OUTSIDE...\n")

        # clear the "temp/" folder just in case
        self.clear_temp()

        # YOLOv3 configuration
        #______________________________________________________________________________
        self.video = cv2.VideoCapture(settings.STATICFILES_DIR + "/input/van_in.mp4")
        self.weights_path = settings.STATICFILES_DIR + "/yolo/yolov3_608.weights"
        self.cfg_path = settings.STATICFILES_DIR + "/yolo/yolov3_608.cfg"
        self.names_path = settings.STATICFILES_DIR + "/yolo/yolov3_608.names"
        with open(self.names_path) as f:
            self.CLASSES = [line.strip() for line in f.readlines()]
        # creating a NN
        self.net = cv2.dnn.readNet(self.weights_path, self.cfg_path)
        self.layer_names = self.net.getLayerNames()
        self.output_layers = [self.layer_names[i[0] - 1] for i in self.net.getUnconnectedOutLayers()]
        # NN input frame size
        self.inpWidth = 608
        self.inpHeight = 608
        # processed video frame size
        self.width = None
        self.height = None

        # centroid tracker configuration
        self.ct = CentroidTracker()
        self.ct.maxDisappeared = 10

        # list of trackers
        self.trackers = []
        self.class_ids = []

        # current processed frame
        self.frame = None

        # objects for tracking
        self.trackableObjects = {}

        # these are the only two classes we should process
        # others should be skipped
        self.available_classes = ["car", "truck"]

        # total number of frames in the video
        self.totalFrames = 0

        # car counter and temporary variable
        self.total = 0
        self.old_total = 0
        self.temp = None

        # current frame number
        self.frame_number = 0


        # frame 1 - detect cars
        # frame 2 - track cars
        # frame 3 - track cars
        # frame 4 - track cars
        # frame 5 - track cars
        # frame 6 - track cars
        # frame 7 - detect cars
        # etc...
        self.skip_frames = 5

        # a dictionary with video detection results
        self.result = {"не найдено":
                           {
                            "body_style": "не найдено",
                            "model": "не найдено",
                            "make": "не найдено"
                            }
                       }
        # ______________________________________________________________________________

        # result of work of self.detect_cars()
        self.generator = None

        # stops detection
        self.stopped = False

        # dictionary: ID -> box coordinates
        self.ID_boxes = {}

        # list of all IDs on a current frame
        self.all_IDs = []
        # list of all IDs that were on a previous frame
        self.old_all_IDs = []
        # list of all IDs that are present on a current frame, but were not present on the previous frame
        self.new_IDs = []

        # list of all car boxes on the frame
        self.all_boxes = None

        # this is one of the "switches"
        # they are used to make functions from "views.py" work correctly
        self.car_recognized = False

        # this is the second of the "switches"
        # it turns True if cars were detected on the frame and each of them was cropped to the .jpg file
        self.cars_were_cropped = False

        # this is the third of the "switches"
        # it turns True only once so that total number of cars could be shown on the web-page at the same time
        # as all other info, but not earlier
        # that just looks better
        self.show_total = False

        # list of all IDs on the frame
        self.current_IDs = []

    # function starts a thread for car detection
    def start(self):
        print("[INFO] STARTING DETECTION_THREAD...")
        detection_outside_thread = Thread(target=self.get_generator, args=())
        detection_outside_thread.name = "detection_outside_thread"
        detection_outside_thread.start()
        return self

    # function stops detection
    def stop(self):
        self.stopped = True

    # function starts detection and puts it's results to a single variable
    def get_generator(self):
        self.generator = self.detect_cars()

    # function clears "temp/" folder just in case
    def clear_temp(self):
        for file in os.listdir(settings.STATICFILES_DIR + "/temp/"):
            os.remove(settings.STATICFILES_DIR + "/temp/" + file)
        print("\n[INFO] 'temp/' folder has been cleared!\n")

    # function fills a list of all IDs on the frame
    def fill_currrent_IDs(self, objects):
        keys = [key for key in objects.keys()]
        if keys == []:
            return
        else:
            self.current_IDs = [objectID for objectID in objects.keys()]

    # Function calculates distance between two centroids
    def find_distance(self, c1, c2):
        try:
            distance = int(maths.sqrt((c2[0] - c1[0]) ** 2 + (c2[1] - c1[1]) ** 2))
            return distance
        except:
            c1 = c1.tolist()
            c2 = c2.tolist()
            distance = int(maths.sqrt((c2[0] - c1[0]) ** 2 + (c2[1] - c1[1]) ** 2))
            return distance

    # function compares centroids of all boxes found on the frame with centroids from "cars" and "trackers" variables
    # if centroids' coordinates match then it connects ID to the certain centroid
    def connect_ID_to_box(self, objects):
        if (objects.items()) and (self.all_boxes != []):
            print(f"connecting IDs to boxes")
            for box in self.all_boxes:
                centroid_1 = [int((box[2] + box[0]) / 2), int((box[3] + box[1]) / 2)]
                for (objectID, centroid_2) in objects.items():
                    centroid_2 = centroid_2.tolist()
                    distance = self.find_distance(centroid_1, centroid_2)
                    if distance <= 30:
                        print(f"    now box {box} is connected to ID {objectID}")
                        self.ID_boxes[objectID] = box  # добавляем в словарь ID и бокс
        print("in the end of connect_ID_to_box ID_boxes is")
        for k,v in self.ID_boxes.items():
            print(k, v)

    # function finds all IDs that are present on the current frame, but were not present on the previous frame
    def find_new_IDs(self):
        temp = []
        if self.all_IDs != []:
            print(f"looking for new IDs")
            for new_ID in self.all_IDs:
                if new_ID not in self.old_all_IDs:
                    print(f"    ID {new_ID} is a new one!")
                    temp.append(new_ID)
                    self.new_IDs = temp
        print(f"in the end of find_new_IDs new_IDs are {self.new_IDs} and temp is {temp}")

    # each of cars has it's box coordinates
    # this function cuts those boxes out with cars in them and puts them into a separate folder
    def cropp_new_IDs(self):
        if self.ID_boxes.keys():
            print("cropping new IDs")
            print("THOSE IDS ARE NEW!")
            for new_ID in self.new_IDs:
                if new_ID in self.ID_boxes.keys():
                    print(f"    new ID {new_ID} has box coords {self.ID_boxes[new_ID]}")
                    box_coords = self.ID_boxes[new_ID]
                    # box = [x1, y1, x2, y2]
                    # cut a box a bit smaller than it's actual size so that a colored box does not get into the .jpg file
                    cropped_box = self.frame.copy()[(box_coords[1]+2):(box_coords[3]-2), (box_coords[0]+2):(box_coords[2]-2)]
                    cv2.imwrite(settings.STATICFILES_DIR + f"/temp/temporary_frame{new_ID}.jpg", cropped_box)
                    print(f"    saving temporary_frame")
                    self.cars_were_cropped = True
                else:
                    print(f"ID {new_ID} has not been connected to box yet!")

    # main function
    def detect_cars(self):
        while not self.stopped:
            self.all_boxes = []
            self.frame_number += 1
            success_capture, self.frame = self.video.read()
            if not success_capture:
                print("=============================================")
                print("ERROR! VIDEO NOT FOUND")
                print("=============================================")
                self.stop()
                # stop if the end of the video is reached
            if self.frame is None:
                print("=============================================")
                print("The end of the video reached")
                print("=============================================")
                self.stop()

            print("\n=============================================")
            print(f"FRAME {self.frame_number}")
            print(f"in the beginning total is {self.total} and old_total is {self.old_total}")
            print(f"car_recognized = {self.car_recognized}")

            # resize frame to increase speed
            self.frame = imutils.resize(self.frame, width=600)
            # change from BGR to RGB to work with dlib library
            rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)

            # get frame size
            if self.width is None or self.height is None:
                self.height, self.width, self.channels = self.frame.shape

            # list of boxes
            rects = []

            # every N frames (look at "skip-frames" argument) vehicles DETECTION takes place
            # then between those frames every vehicles is being TRACKED
            # that increases the speed significantly
            if self.totalFrames % self.skip_frames == 0:
                # create an empty list of trackers
                self.trackers = []
                # list of car class numbers
                self.class_ids = []

                # pass the blob-model of the frame through the NN to get boxes of detected objects
                blob = cv2.dnn.blobFromImage(self.frame, 0.00392, (self.inpWidth, self.inpHeight), (0, 0, 0), True,
                                             crop=False)
                self.net.setInput(blob)
                outs = self.net.forward(self.output_layers)

                # analyze boxes list
                for out in outs:
                    for detection in out:
                        scores = detection[5:]
                        class_id = np.argmax(scores)
                        confidence = scores[class_id]
                        if confidence > 0.4:
                            result_class = self.CLASSES[class_id]
                            # if neither car nor truck is detected - skip it
                            if result_class not in self.available_classes:
                                continue

                            center_x = int(detection[0] * self.width)
                            center_y = int(detection[1] * self.height)
                            w = int(detection[2] * self.width)
                            h = int(detection[3] * self.height)

                            # if a box is too small, for example if a car is moving very close to the edge of a frame, then we do skip it
                            # the smaller the number is, the bigger the minimum size of a box is
                            if h <= (self.height / 4):
                                continue

                            # coords of left upper and right lower connors of the box
                            x1 = int(center_x - w / 2)
                            y1 = int(center_y - h / 2)
                            x2 = x1 + w
                            y2 = y1 + h

                            # let's make a maximum distance of centroid tracker equal to the width of a box
                            self.ct.maxDistance = w

                            # draw a box
                            cv2.rectangle(self.frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 1)

                            # add a box to a list of all boxes
                            self.all_boxes.append([x1, y1, x2, y2])

                            # create a tracker for every car
                            tracker = dlib.correlation_tracker()
                            # create a dlib rectangle for a box
                            rect = dlib.rectangle(x1, y1, x2, y2)
                            # start tracking each box
                            tracker.start_track(rgb, rect)
                            # every tracker is placed into a list
                            self.trackers.append(tracker)
                            self.class_ids.append(class_id)

            # if frame number is not N then we work with previously created list of trackers rather that boxes
            else:
                for tracker, class_id in zip(self.trackers, self.class_ids):

                     # a car was detected on one frame and after that on other frames it's coords are constantly updating
                    tracker.update(rgb)

                    pos = tracker.get_position()

                    # get box coords from each tracker
                    x1 = int(pos.left())
                    y1 = int(pos.top())
                    x2 = int(pos.right())
                    y2 = int(pos.bottom())

                    # draw a box
                    cv2.rectangle(self.frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 1)

                    # add this box coordinates to the list of all boxes
                    rects.append((x1, y1, x2, y2))

            # this is the list of cars that we tracked and centroids were moved to their new positions
            objects = self.ct.update(rects)

            # connect IDs to car boxes
            self.connect_ID_to_box(objects)

            # create lists of all IDs on the frame
            self.fill_currrent_IDs(objects)

            # car counting algorithm
            length = len(objects.keys())
            if length > self.total:
                self.total += length - self.total
            if self.temp is not None:
                if (length > self.temp):
                    self.total += length - self.temp
            if length < self.total:
                self.temp = length

            print(f"after counting total is {self.total} and old_total is {self.old_total}")


            # if a new car appeared on the frame I need:
            # 1) give it and ID
            # 2) cropp it's box
            # 3) place cropped box to the separate folder
            # 4) detect car type on the cropped image

            # this must be done not only if total number of cars has increased but also if "car_recognized" switch is False
            if (self.total > self.old_total) and (not self.car_recognized):
                print("total > old_total - creating old_all_IDs")
                self.old_all_IDs = self.all_IDs
                self.all_IDs = [ID for ID in objects.keys()]  # create a list of all IDs on the frame
                # find all new IDs
                self.find_new_IDs()
                # images could be cropped NOT EARLIER than 6th frame because "ID_boxes" dictionary is required
                self.cropp_new_IDs()

                # car type is detected only if images were cropped
                # else there is just not images to process
                if self.cars_were_cropped:
                    # __________________________________________________________________
                    print("\n[INFO] NEW VEHICLE FOUND! DETECTING TYPE...\n")
                    recognizer = CarTypeRecongizer()
                    # get urls of images of new cars from FireBase
                    recognizer.get_url()
                    # recognize car type on each image using urls
                    recognizer.recognize()
                    type_recognition_results = recognizer.results

                    # dictionary: ID -> {car type, make, model} (the value is also a dictionary)
                    self.result = type_recognition_results

                    # this "switch" turns True only if types of all cars on cropped images were detected
                    all_recognized = False
                    for ID, info in self.result.items():
                        if info["body_style"] != "не найдено":
                            all_recognized = True
                        else:
                            all_recognized = False
                    print(f"all_recognized = {all_recognized}")
                    # if images with cars were cropped and car types were detected then we make a "car_recognized" switch True and
                    # make "total" be equal to "old_total"
                    if all_recognized:
                        if self.cars_were_cropped:
                            print('\n\n\nCARS WERE CROPPED AND TYPE WAS DETECTED\n\n\n')
                            self.car_recognized = True
                            self.old_total = self.total
                            # make this "switch" True only once so that total number of cars could be shown on a web page
                            self.show_total = True
            # if total number of cars did not change, just make a list of all IDs
            else:
                self.all_IDs = [ID for ID in objects.keys()]

            # analyze the dictionary of tracked objects
            for (objectID, centroid) in objects.items():

                # check if a trackable objects exists for particular ID
                to = self.trackableObjects.get(objectID, None)

                # if it doesn't then we create a new one corresponding to the given centroid
                if to is None:
                    to = TrackableObject(objectID, centroid)

                # place the trackable object into the dictionary
                self.trackableObjects[objectID] = to

                # drawing circle and text
                text = "ID {}".format(objectID)
                cv2.putText(self.frame, text, (centroid[0] - 10, centroid[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.circle(self.frame, (centroid[0], centroid[1]), 4, (0, 255, 0), -1)

            self.totalFrames += 1


            # the processed frame is converted to .jpg and yielded to the "generator" variable
            jpeg = cv2.imencode('.jpg', self.frame)[1].tostring()
            yield (b'--frame_1\r\n'b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n\r\n')







