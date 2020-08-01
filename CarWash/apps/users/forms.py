
from django import forms
from django.core.exceptions import ValidationError

# User creation form
class UserRegisterForm(forms.Form):
    # using "widget" I add Bootstrap tags to make it all look better
    username = forms.CharField(min_length=5, max_length=50, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Введите ник (максимум 50 символов)', 'type':'text'}))
    email = forms.EmailField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Введите почту (максимум 50 символов)', 'type':'text'}))
    password1 = forms.CharField(max_length=25,required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Введите пароль (максимум 25 символов)', 'type':'password'}))
    password2 = forms.CharField(max_length=25,required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder':'Введите пароль ещё раз', 'type':'password'}))

    # function checks if password match
    # when in "views.py" we "form.is_valid()" is activated all function with "clean" in the beginning
    # of their names activate here
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if len(password1) > 25 or len(password2) > 25:
            raise ValidationError("Максимум 25 символов")

        if password1 and password2 and password1 != password2:
            raise ValidationError("Пароли не воспадают!")

        return password2

    # function checks if username is not too long
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if len(username) > 50:
            raise ValidationError("Максимум 50 символов!")
        return username


    # function checks if email is not too long
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if len(email) > 50:
            raise ValidationError("Максимум 50 символов!")
        return email

# Login form
class UserLoginForm(forms.Form):
    # using "widget" I add Bootstrap tags to make it all look better
    email = forms.EmailField(max_length=50, required=True,widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите почту (максимум 50 символов)', 'type':'text'}))
    password1 = forms.CharField(max_length=25,required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите пароль (максимум 25 символов)', 'type':'password'}))

    # fucntion checks if email is not too long
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if len(email) > 50:
            raise ValidationError("Максимум 50 символов!")
        return email

    # function checks if password is not too long
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        if len(password1) > 25:
            raise ValidationError("Максимум 25 символов")
        return password1












