from django.urls import path
from . import views


urlpatterns = [
   path('index',views.index, name='index'),
   path('enquiry/<pk>',views.enquiry, name='enquiry'),
   path('create_enquiry_ajax', views.create_enquiry_ajax, name='create_enquiry_ajax'),
    path('enquiry/<int:enquiry_id>/requests_offers', views.requests_offers_for_enquiry, name='requests_offers_for_enquiry')
]
