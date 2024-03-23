from django.urls import path
from . import views


urlpatterns = [
   path('index',views.index, name='index'),
   path('enquiry/<pk>',views.enquiry, name='enquiry'),
   path('create_enquiry_ajax', views.create_enquiry_ajax, name='create_enquiry_ajax'),
   path('enquiry/<int:enquiry_id>/requests_offers', views.requests_offers_for_enquiry, name='requests_offers_for_enquiry'),
   path('update_offers/', views.update_offers, name='update_offers'),
   path('enquiry_list', views.enquiry_list,name = 'enquiry_list'),
   path('update_requests/', views.update_requests, name='update_requests'),
   path('api/enquiries/', views.get_enquiries, name='api_enquiries')
]
                                                            