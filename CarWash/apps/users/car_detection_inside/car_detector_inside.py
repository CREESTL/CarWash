from CarWash.apps.users.car_detection_outside.pyimagesearch.centroidtracker import CentroidTracker
from CarWash.apps.users.car_detection_outside.pyimagesearch.trackableobject import TrackableObject
import numpy as np
import imutils
import dlib
import cv2
from django.conf import settings
import math as maths
import time
from threading import Thread


'''
This class detects license plate number on stopped cars
'''
class CarStopDetector():
    def __init__(self):

        print("\n[INFO] LOADING CAR DETECTOR INSIDE...\n")

        # YOLOv3 configuration
        # ______________________________________________________________________________
        self.video = cv2.VideoCapture(settings.STATICFILES_DIR + "/input/mazda_not_in.mp4")
        self.weights_path = settings.STATICFILES_DIR + "/yolo/yolov3_608.weights"
        self.cfg_path = settings.STATICFILES_DIR + "/yolo/yolov3_608.cfg"
        self.names_path = settings.STATICFILES_DIR + "/yolo/yolov3_608.names"
        # cascades for LP(license plate) box drawing
        self.faceCascade = cv2.CascadeClassifier(settings.STATICFILES_DIR + "/cascades/plates_cascade.xml")
        with open(self.names_path) as f:
            self.CLASSES = [line.strip() for line in f.readlines()]
        # creating a NN
        self.net = cv2.dnn.readNet(self.weights_path, self.cfg_path)
        self.layer_names = self.net.getLayerNames()
        self.output_layers = [self.layer_names[i[0] - 1] for i in self.net.getUnconnectedOutLayers()]
        # NN input image size
        self.inpWidth = 608
        self.inpHeight = 608

        # processed video frame size
        self.width = None
        self.height = None

        # NN minimum confidence
        self.min_confidence = 0.80

        # Centroid tracker configuration
        self.car_ct = CentroidTracker()
        self.car_ct.maxDisappeared = 10
        self.truck_ct = CentroidTracker()
        self.truck_ct.maxDisappeared = 10

        # list of trackers
        self.trackers = []
        self.class_ids = []

        # objects for tracking
        self.trackableObjects = {}

        # car counter and temporary variable
        self.total = 0
        self.old_total = 0
        self.temp = None

        # number of frames in the video
        self.totalFrames = 0

        # number of current frame
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

        # result of work of self.detect_cars()
        self.generator = None

        # stops detector's work
        self.stopped = False

        # current processed frame
        self.frame = None

        # old vehicle trackers
        # "old" means the trackers of the previous frame
        self.old_car_trackers = None
        self.old_truck_trackers = None

        # IDs of vehicles that are MAYBE stopped
        self.stopped_car_IDs = []
        self.stopped_truck_IDs = []

        # dictionaries: ID -> amount of frames a vehicle was not moving for
        self.car_counting_frames = {}
        self.truck_counting_frames = {}

        # dictionaries: ID -> amount of seconds a vehicle was not moving for
        self.car_counting_seconds = {}
        self.truck_counting_seconds = {}

        # this variable is used for car stop detection
        self.parts = 60

        # this is how many frames a car should stand at one place so we can say that it has stopped
        # if the video is recorded in 60fps 120 frames is equal to 2 seconds of real time
        self.frames_to_stop = 120

        # vehicles that are stopped
        self.long_stopped_cars = []
        self.long_stopped_trucks = []

        # dictionary: ID -> [stopped at, started moving at]
        self.result = {}

        # dictionary: ID -> box coordinates
        self.ID_boxes = {}

        # list of all LP boxes on the frame
        self.plaques = []

        # list of all car boxes on the frame
        # centroids from this list are compared to centroids from "cars" or "trucks" dictionaries to connect
        # each ID to some box
        self.all_boxes = None

        # when a car is stopped I increase it's box size a bit. This is how many times box size increases
        self.times = 1.1

        # list of all IDs on the frame
        self.current_IDs = []

    # function starts a separate thread for car detection
    def start(self):
        print("[INFO] STARTING DETECTION_INSIDE_THREAD...")
        detection_inside_thread = Thread(target=self.get_generator, args=())
        detection_inside_thread.name = "detection_outside_thread"
        detection_inside_thread.start()
        return self  # нужно возвращать self, чтобы можно было start() приравнять к какой-нибудь переменной

    # function starts detection and puts it's results to a single variable
    def get_generator(self):
        self.generator = self.detect_car_stop()

    # function stops detection
    def stop(self):
        self.stopped = True

    # function draws car centroid
    # centroid is green if the car is moving
    # centroid is red if the car is not moving
    def draw_centroids(self, objects):
        for (objectID, centroid) in objects.items():
            # check if a trackable objects exists for particular ID
            to = self.trackableObjects.get(objectID, None)

            # if it doesn't then we create a new one corresponding to the given centroid
            if to is None:
                to = TrackableObject(objectID, centroid)

            # place the trackable object into the dict.
            self.trackableObjects[objectID] = to

            # drawing circle and text
            if objectID in self.long_stopped_cars:
                text = "ID {} STOPPED".format(objectID)
                # if a car is not moving then we draw a large yellow centroid
                cv2.putText(self.frame, text, (centroid[0] - 10, centroid[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                cv2.circle(self.frame, (centroid[0], centroid[1]), 6, (0, 255, 255), -1)
            else:
                text = "ID {}".format(objectID + 1)
                # else we draw a smaller green centroid
                cv2.putText(self.frame, text, (centroid[0] - 10, centroid[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.circle(self.frame, (centroid[0], centroid[1]), 3, (0, 255, 0), -1)

    # function compares centroids of all boxes found on the frame with centroids from "cars" and "trackers" variables
    # if centroids' coordinates match then it connects ID to the certain centroid
    # then it checks if the ID is is the list of stopped vehicles and draw a large box. Or, it's not -  draw a normal box
    def draw_boxes(self, objects):
        for box in self.all_boxes:
            centroid_1 = [int((box[2] + box[0]) / 2), int((box[3] + box[1]) / 2)]
            for (objectID, centroid_2) in objects.items():
                centroid_2 = centroid_2.tolist()
                if self.find_distance(centroid_1, centroid_2) <= 30:
                    self.ID_boxes[objectID] = box  # add ID and box to the dictionary
        for ID, box in self.ID_boxes.items():
            if ID in self.long_stopped_cars:
                # draw a large red box
                cv2.rectangle(self.frame, (int(box[0] / self.times), int(box[1] / self.times)),
                              (int(box[2] * self.times), int(box[3] * self.times)), (0, 0, 255), 2)

    # function calculates distance between two centroids
    def find_distance(self, c1, c2):
        try:
            distance = int(maths.sqrt((c2[0] - c1[0]) ** 2 + (c2[1] - c1[1]) ** 2))
            return distance
        except:
            c1 = c1.tolist()
            c2 = c2.tolist()
            distance = int(maths.sqrt((c2[0] - c1[0]) ** 2 + (c2[1] - c1[1]) ** 2))
            return distance

    # function returns a list of IDs that are currently on the frame
    def fill_currrent_IDs(self, objects):
        keys = [key for key in objects.keys()]
        if keys == []:
            return
        else:
            self.current_IDs = [objectID for objectID in objects.keys()]

    # function translates time.asctime() into Russian
    def format_time(self, now):
        now = now.replace("Sun", "Воскресенье")
        now = now.replace("Mon", "Понедельник")
        now = now.replace("Tue", "Вторник")
        now = now.replace("Wed", "Среда")
        now = now.replace("Thu", "Четверг")
        now = now.replace("Fri", "Пятница")
        now = now.replace("Sat", "Суббота")
        now = now.replace("Jul", "Июль")
        now = now.replace("Aug", "Июль")
        now = now.replace("Sept", "Июль")
        now = now.replace("Oct", "Июль")
        now = now.replace("Nov", "Июль")
        now = now.replace("Dec", "Июль")
        now = now.replace("Jan", "Июль")
        now = now.replace("Feb", "Июль")
        now = now.replace("Mar", "Июль")
        now = now.replace("Apr", "Июль")
        now = now.replace("May", "Июль")
        now = now.replace("Jun", "Июль")
        now = now.replace(" ", ", ")
        return now

    # function compares coordinates on the certain car's box on N and N+1 frames
    # it returns a list of cars that are, PERHAPS, not moving
    def compare_trackers(self, old_trackers, new_trackers, vehicle_type=None):
        for (old_objectID, old_centroid) in old_trackers.items():
            for (new_objectID, new_centroid) in new_trackers.items():
                if old_objectID == new_objectID:
                    distance = self.find_distance(old_centroid, new_centroid)
                    if vehicle_type == "car":
                        print(f"Distance between centroids of car number {old_objectID + 1} is {distance}", end='')
                        # If the distance between centroids is less than 1/N of width of the frame then we add it to the list
                        if distance < self.width / self.parts:
                            print(" - it is OK")
                            if new_objectID not in self.stopped_car_IDs:
                                print(f"{new_objectID + 1} is a new car - add it to stopped_car_ID")
                                self.stopped_car_IDs.append(new_objectID)
                        else:
                            print(" - it is more than we need")
                            if new_objectID in self.stopped_car_IDs:
                                print(f"deleting {new_objectID + 1}")
                                # If the distance is more than 1/N then it means that the car started moving again - delete it from the list
                                self.stopped_car_IDs.remove(new_objectID)
                    if vehicle_type == "truck":
                        print(f"Distance between centroids of truck number {old_objectID + 1} is {distance}", end='')
                        # If the distance between centroids is less than 1/N of width of the frame then we add it to the list
                        if distance < self.width / self.parts:
                            print(" it is OK")
                            if new_objectID not in self.stopped_truck_IDs:
                                print(f"{new_objectID + 1} is a new truck - add it to stopped_truck_ID")
                                self.stopped_truck_IDs.append(new_objectID)
                        else:
                            print(" it is more than we need")
                            if new_objectID in self.stopped_truck_IDs:
                                print(f"deleting {new_objectID + 1}")
                                # If the distance is more than 1/N then it means that the car started moving again - delete it from the list
                                self.stopped_truck_IDs.remove(new_objectID)
                # if a car has moved away from the frame and we can not see it anymore then we should
                # delete it from the list of stopped cars
                if old_objectID not in new_trackers.keys():
                    if vehicle_type == "car":
                        if old_objectID in self.stopped_car_IDs:
                            print(f"car {old_objectID + 1} is not on the frame anymore - deleting it...")
                            self.stopped_car_IDs.remove(old_objectID)
                    if vehicle_type == "truck":
                        if old_objectID in self.stopped_truck_IDs:
                            print(f"truck {old_objectID + 1} is not on the frame anymore - deleting it...")
                            self.stopped_truck_IDs.remove(old_objectID)

        # if new_trackers are an empty array, that means that there are NO cars of a frame at all
        # so we should clear stopped_car_IDs
        if len(new_trackers.keys()) == 0:
            if vehicle_type == "car":
                if self.stopped_car_IDs != []:
                    print("there is no any car on a frame - clear stopped_car_IDs")
                    self.stopped_car_IDs.clear()
            if vehicle_type == "truck":
                if self.stopped_truck_IDs != []:
                    print("there is no any truck on a frame - clear stopped_truck_IDs")
                    self.stopped_truck_IDs.clear()

    # function finds cars/trucks that were not moving long enough
    def find_stopped_cars(self, counting_frames):
        long_stopped_vehicles = []
        for ID, frames in counting_frames.items():
            if frames > self.frames_to_stop:  # this number can be changed to increase work efficiency
                long_stopped_vehicles.append(ID)
        return long_stopped_vehicles

    # function deletes LP plaques boxes with similar coordinates not to draw them one upon another
    def only_different(self):
        plaques = list(self.plaques)
        for i, plq in enumerate(plaques):
            plq = list(plq)
            plaques[i] = plq
        for plq in plaques:
            i = plaques.index(plq)
            for j in range(0, len(plaques) - 1):
                if plaques[i] == plaques[j]:
                    plaques.remove(plaques[j])
        return plaques

    # function draws boxes on license plates (it DOES NOT detect text on them)
    def draw_LP_boxes(self):
        gray = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        # 1.3 = scale, 5 = min_neighbours
        self.plaques = self.faceCascade.detectMultiScale(gray, 1.3, 5)
        # delete similar LP plaques
        self.plaques = self.only_different()
        for plaque in self.plaques:
            (x, y, w, h) = plaque
            cv2.rectangle(self.frame, (x, y), (x + w, y + h), (0, 255, 0), 1)

    # main function
    def detect_car_stop(self):
        while not self.stopped:
            # this list should be filled from scratch every time
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
            print(f"total is {self.total} and old_total is {self.old_total}")

            # change frame size to increase speed a bit
            self.frame = imutils.resize(self.frame, width=600)

            # change colors from RGB to BGR to work in dlib
            rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)

            if self.width is None or self.height is None:
                self.height, self.width, channels = self.frame.shape

            print(f"minimum distance is {self.width / self.parts}")

            # lists of bounding boxes
            car_rects = []
            truck_rects = []

            # every N frames (look at "skip-frames" argument) vehicles DETECTION takes place
            # then between those frames every vehicles is being TRACKED
            # that increases the speed significantly
            if self.totalFrames % self.skip_frames == 0:
                # empty list of trackers
                self.trackers = []
                # list of classes numbers
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
                        if (class_id != 2) and (class_id != 7):  # if a car or a truck is detected - continue
                            continue
                        confidence = scores[class_id]
                        if confidence > self.min_confidence:
                            # box'es center coords
                            center_x = int(detection[0] * self.width)
                            center_y = int(detection[1] * self.height)
                            # width of the box
                            w = int(detection[2] * self.width)
                            # height of the box
                            h = int(detection[3] * self.height)

                            # if a box is too small (for example if a car is moving very close to the edge of a frame, then we do skip it
                            if h <= (self.height / 4):
                                continue

                            # coords of left upper and right lower connors of the box
                            x1 = int(center_x - w / 2)
                            y1 = int(center_y - h / 2)
                            x2 = x1 + w
                            y2 = y1 + h

                            # let's make a maximum distance of centroid tracker equal to the width of a box
                            self.truck_ct.maxDistance = w
                            self.car_ct.maxDistance = w

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

                    # add a box to a list of all boxes
                    self.all_boxes.append([x1, y1, x2, y2])

                    obj_class = self.CLASSES[class_id]

                    if obj_class == "car":
                        car_rects.append((x1, y1, x2, y2))
                    elif obj_class == "truck":
                        truck_rects.append((x1, y1, x2, y2))

            # those are the lists of cars that we tracked and centroids were moved to their new positions
            cars = self.car_ct.update(car_rects)
            trucks = self.truck_ct.update(truck_rects)

            # create lists of all IDs on the frame
            self.fill_currrent_IDs(cars)
            self.fill_currrent_IDs(trucks)

            # car counting algorithm
            length = len(cars.keys()) + len(trucks.keys())
            if length > self.total:
                self.total += length - self.total
            if self.temp is not None:
                if (length > self.temp):
                    self.total += length - self.temp
            if length < self.total:
                self.temp = length
            # if a total number of cars has increased - write a frame to the file to detect LP using it later
            # Если количество машин увеличилось, то распознаем тип появившейся машины
            if self.total > self.old_total:
                cv2.imwrite(settings.STATICFILES_DIR + "/temp/detect_LP.jpg", self.frame)

            # drawing LP boxes (works only if a car is not far away from the camera)
            self.draw_LP_boxes()

            # get the IDs of cars that are, perhaps, stopped
            if self.old_car_trackers is not None:
                self.compare_trackers(self.old_car_trackers, cars, "car")
            if self.old_truck_trackers is not None:
                self.compare_trackers(self.old_truck_trackers, trucks, "truck")
                if self.stopped_car_IDs != []:
                    for ID in self.stopped_car_IDs:
                        # Increasing the number of frames
                        if ID in self.car_counting_frames.keys():
                            self.car_counting_frames[ID] += 1
                        # Adding a new car ID
                        else:
                            self.car_counting_frames[ID] = 1
                    # if any ID is IN car_counting_frames.keys() but it os NOT IN the stopped_car_IDs then we have to delete
                    # from the dictionary as it means that the car is stopped and moving at the same time which is impossible
                    for ID in self.car_counting_frames.copy().keys():
                        if ID not in self.stopped_car_IDs:
                            print(
                                f"{ID + 1} is in car_counting_frames but is not in stopped_car_IDs - delete it from car_counting_frames")
                            self.car_counting_frames.pop(ID)
                else:
                    # If a list is empty it means that there are no cars to process
                    self.car_counting_frames = {}
                # same thing for trucks (you can add your classe here)
                if self.stopped_truck_IDs != []:
                    for ID in self.stopped_truck_IDs:
                        if ID in self.truck_counting_frames.keys():
                            self.truck_counting_frames[ID] += 1
                        else:
                            self.truck_counting_frames[ID] = 1

                    for ID in self.truck_counting_frames.copy().keys():
                        if ID not in self.stopped_truck_IDs:
                            self.truck_counting_frames.pop(ID)
                else:
                    self.truck_counting_frames = {}

            print("\n")
            # some info on the screen (debug)
            for k, v in self.car_counting_frames.items():
                print(f"car {k + 1} was standing for {v} frames")
            for k, v in self.truck_counting_frames.items():
                print(f"truck {k + 1} was standing for {v} frames")

            # those are the lists of cars that have been standing still long enough
            # they refresh EACH frame
            self.long_stopped_cars = self.find_stopped_cars(self.car_counting_frames)
            self.long_stopped_trucks = self.find_stopped_cars(self.truck_counting_frames)

            # now when we have a list of cars that are for sure stopped we can count how long (in seconds) they are not moving
            for ID in self.long_stopped_cars:
                if ID not in self.car_counting_seconds.keys():
                    # if it is a new car then we pinpoint time when car stops
                    start = time.asctime()
                    start = self.format_time(start)
                    # [0,0] will later be replaced
                    self.car_counting_seconds[ID] = [0, 0]
                    self.car_counting_seconds[ID][0] = start
                else:
                    # else if this car is already on the list then we add time to it's current time
                    stop = time.asctime()
                    stop = self.format_time(stop)
                    self.car_counting_seconds[ID][1] = stop

            # do the same thing but for trucks
            for ID in self.long_stopped_trucks:
                if ID not in self.truck_counting_seconds.keys():
                    # if it is a new car then we pinpoint time when car stops
                    start = time.asctime()
                    self.truck_counting_seconds[ID] = [0, 0]
                    self.truck_counting_seconds[ID][0] = start
                else:
                    # else if this car is already on the list then we add time to it's current time
                    stop = time.asctime()
                    self.truck_counting_seconds[ID][1] = stop

            if (self.car_counting_seconds.keys()) or (self.truck_counting_seconds.keys()):
                print("\n----RESULTS----:")
                # show info about seconds in command line
                for ID, [start, stop] in self.car_counting_seconds.items():
                    print(f"car {ID + 1} was standing from: {start} to {stop}")
                for ID, [start, stop] in self.truck_counting_seconds.items():
                    print(f"truck {ID + 1} was standing from: {start} to {stop}")

            self.old_car_trackers = cars.copy()
            self.old_truck_trackers = trucks.copy()

            # draw centroids for cars and trucks
            self.draw_centroids(cars)
            self.draw_centroids(trucks)

            # draw boxes for cars and trucks
            self.draw_boxes(cars)
            self.draw_boxes(trucks)

            # increase frame number
            self.totalFrames += 1

            # add each stopped vehicle to the result dictionary
            for ID, [start, stop] in self.car_counting_seconds.items():
                self.result[ID] = [start, stop]

            # the processed frame is converted to .jpg and yielded to the "generator" variable
            jpeg = cv2.imencode('.jpg', self.frame)[1].tostring()
            yield (b'--frame_1\r\n'b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n\r\n')
