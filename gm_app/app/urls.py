from django.urls import path
from . import views


urlpatterns = [
   path('index',views.index, name='index'),
   path('forms',views.forms, name='forms'),
   path('create_enquiry_ajax', views.create_enquiry_ajax, name='create_enquiry_ajax'),
]
