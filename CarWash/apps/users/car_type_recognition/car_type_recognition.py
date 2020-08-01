import Algorithmia
import pyrebase
import os
from django.conf import settings

#######################################################################################
# FireBase configuration
config = {
    'apiKey': "AIzaSyBnsFHlZ9IP7kATKMILibYxT4y2_CRWUrM",
    'authDomain': "carwash-838f3.firebaseapp.com",
    'databaseURL': "https://carwash-838f3.firebaseio.com",
    'projectId': "carwash-838f3",
    'storageBucket': "carwash-838f3.appspot.com",
    'messagingSenderId': "548753653087",
    'appId': "1:548753653087:web:1dcba0736eff005002caea",
    'measurementId': "G-7YLLEJ4SX7"
}

firebase = pyrebase.initialize_app(config)

# user registration and authentication
auth = firebase.auth()

# all text data
db = firebase.database()

# media files (images and videos)
storage = firebase.storage()

##################################################################################


'''
This class detects type, make, model of a car on the image
'''
class CarTypeRecongizer():
    def __init__(self):
        # dictionary: ID -> image url
        self.urls = {}
        # dictionary: ID -> {type, make, model} (the value is also a dictionary)
        self.results = {}

    # function puts all images from "temp/" folder into FireBase and return a list of their URLs
    def get_url(self):
        if not os.listdir(settings.STATICFILES_DIR + "/temp"):
            print(" THERE ARE NO CROPPED CARS TO PROCESS IN DIRECTORY")
        for file in os.listdir(settings.STATICFILES_DIR + "/temp"):
            print(f"    file {file}")
            if 'temporary_frame' in file:
                # the last 1 or 2 symbols of a filename is an ID of a car on the frame
                try:
                    ID = int(file[-6:-4])
                except:
                    ID = int(file[-5:-4])
                print(f"    ID on it is {ID}")
                # put an image to FireBase
                temporary_put_response = storage.child('users').child(auth.current_user["localId"]).child("images").child("temp").child(f"temporary_frame{ID}.jpg").put(settings.STATICFILES_DIR + "/temp/" + file)
                # get a token that allows us to get the URL
                downloadToken = temporary_put_response['downloadTokens']
                # get the URL
                video_url = storage.child('users ').child(auth.current_user["localId"]).child("images").child("temp").child(f"temporary_frame{ID}.jpg").get_url(downloadToken)
                if "/o/users%20" in video_url:
                    video_url = video_url.replace("/o/users%20", "/o/users")
                self.urls[ID] = video_url

    # function detects car type, make, model on the image
    # takes image URL as an input
    def recognize(self):
        client = Algorithmia.client('simZM3WZ+0NRs8RwL73M0X5GROX1')
        algo = client.algo('LgoBE/CarMakeandModelRecognition/0.4.7')
        algo.set_options(timeout=300)  # optional
        # each new car is processed
        for ID, url in self.urls.items():
            print(f"    in type_recognizer processing car with ID{ID}")
            result = algo.pipe(url).result[0]
            print(f"    result is {result}")
            self.results[ID] = result
