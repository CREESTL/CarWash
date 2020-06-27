# Здесь хранятся все формы.

from django import forms
from django.core.exceptions import ValidationError

# Создание пользователя
class UserRegisterForm(forms.Form):
    # Через widget я добавляю bootstrap теги, чтобы все это выглядело не как стоковая версия от django
    username = forms.CharField(min_length=5, max_length=50, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Введите ник (максимум 50 символов)', 'type':'text'}))
    email = forms.EmailField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Введите почту (максимум 50 символов)', 'type':'text'}))
    password1 = forms.CharField(max_length=25,required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Введите пароль (максимум 25 символов)', 'type':'password'}))
    password2 = forms.CharField(max_length=25,required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Введите пароль ещё раз', 'type':'password'}))

    # Функция проверяет, совпадают ли пароли
    # Когда в views запускаем form.is_valid() то ВСЕ функции с "clean" впереди РАБОТАЮТ
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if len(password1) > 25 or len(password2) > 25:
            raise ValidationError("Максимум 25 символов")

        if password1 and password2 and password1 != password2:
            raise ValidationError("Пароли не воспадают!")

        return password2

    # Функция проверяет длину имени пользователя
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if len(username) > 50:
            raise ValidationError("Максимум 50 символов!")
        # Функция проверяет длину имени пользователя
        return username


    # Функция проверяет длину адреса почты
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if len(email) > 50:
            raise ValidationError("Максимум 50 символов!")
        return email

# Вход в аккаунт
class UserLoginForm(forms.Form):
    # Через widget я добавляю bootstrap теги, чтобы все это выглядело не как стоковая версия от django
    email = forms.EmailField(max_length=50, required=True,widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите почту (максимум 50 символов)', 'type':'text'}))
    password1 = forms.CharField(max_length=25,required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите пароль (максимум 25 символов)', 'type':'password'}))

    # Функция проверяет длину адреса почты
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if len(email) > 50:
            raise ValidationError("Максимум 50 символов!")
        return email

    # Проверяет корректность пароля
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')

        if len(password1) > 25:
            raise ValidationError("Максимум 25 символов")

        return password1


# Форма, в которой вводится URL видео
class VideoURLForm(forms.Form):
    url = forms.CharField(min_length=20, max_length=1000, required=True, widget=forms.TextInput(attrs={"class": "form-control", "placeholder":"Введите URL", "type":"text"}))

    # Проверяется, ввел ли что-либо пользователь
    def clean_url(self):
        url=self.cleaned_data.get("url")
        if (url is None) or (url==""):
            raise ValidationError("Пожалуйста, введите данные")
        elif "https://www.youtube.com/watch" not in url:
            raise ValidationError("Пожалуйста, проверьте правильность URL")
        return url
















