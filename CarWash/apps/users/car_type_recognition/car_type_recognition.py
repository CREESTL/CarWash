import Algorithmia
import pyrebase
import os
import cv2
from django.conf import settings

#######################################################################################
# конфиг для FireBase
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

auth = firebase.auth()  # регистраци и вход пользователей

db = firebase.database()  # текстовые данные

storage = firebase.storage()  # медиа-файлы

##################################################################################


class CarTypeRecongizer():
    def __init__(self, frame):
        self.frame = frame
        self.downloadToken = None
        self.video_url = None


    def get_url(self):
        # сначала фотку сохраняем в папку temp в static
        cv2.imwrite(settings.STATICFILES_DIR + r"\temp\temporary_frame.jpg", self.frame)
        # затем эту фотку помещаем на firebase
        temporary_put_response = storage.child('users').child(auth.current_user["localId"]).child("images").child("temp").child("temporary_frame.jpg").put(settings.STATICFILES_DIR + r"\temp\temporary_frame.jpg")
        # удаляем фотку с компа, так как она больше не нужна
        #os.remove(settings.STATICFILES_DIR + r"\temp\temporary_frame.jpg")
        # получаем токен, который нужен для получения url
        self.downloadToken = temporary_put_response['downloadTokens']
        # получаем сам URL видео
        self.video_url = storage.child('users ').child(auth.current_user["localId"]).child("images").child("temp").child("temporary_frame.jpg").get_url(self.downloadToken)
        if "/o/users%20" in self.video_url:
            self.video_url = self.video_url.replace("/o/users%20", "/o/users")
        return self.video_url
    # Функция принимает на вход url картинки с авто и возращает информацию о типе и марке авто
    def recognize(self, video_url):
        # здесь токен моего аккаунта на Algorithmia
        client = Algorithmia.client('simZM3WZ+0NRs8RwL73M0X5GROX1')
        algo = client.algo('LgoBE/CarMakeandModelRecognition/0.4.7')
        algo.set_options(timeout=300)  # optional
        # Обработка
        result = algo.pipe(video_url).result[0]
        # Вывод результата в удобной форме
        return result
