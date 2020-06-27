**Overview**
================
#### To be short:
This program is a part of a large web-project which allows
- The owner of a car to get a more detailed information about the process of his car beeing washed
- The owner of a car wash to manage his clients and control workers

Unfortunately, it is __not__ available in public access right now, as it is still in process of work

But here is a short list of it's functions:
* A user first of all gets to a home page where he can choose between several options:
    * To register
    * To sign in
* If he wished to register he is redirected to a registration page to fill in the specific form. He provides hes e-mail, password and a username.
* If he has already registered before he will, of course, log in
* After both of this options a user will be redirected to another page where he will have the only option - __watch live-stream from the car wash__. That allows the user to:
- watch a video-stream from the car wash cameras
- switch between cameras
- see all important information about the vehicles on the video

While streaming the video onto user's device, the service actually does a lot of stuff such as:
* detects cars on the video
* counts and tracks cars
* detects car's type, make and model
* puts all info into FireBase

In case of any accident the owner of the car wash can easily access the data-base and get all the information he needs
____

***WARNING***
This repo contains __NOT__ full source code. So you won't be able to run it properly if you cloned it.
____
### What was used?
- OpenCV
- Bootstrap 4
- Python 3.6
- Pyrebase
- Tesseract
