from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('main/', views.main, name='main'),
    path('reset_chat/', views.reset_chat, name='reset_chat'),
    path('upload_record/', views.upload_record, name='upload_record'),
]
