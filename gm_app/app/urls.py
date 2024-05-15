from django.urls import path
from . import views
from django.urls import path, include



urlpatterns = [
   path('login/microsoft/', views.microsoft_login, name='microsoft_login'),
   path('login/callback/', views.microsoft_callback, name='microsoft_callback'),
   path('logout',views.ms_logout,name= 'ms_logout'),
   path('',views.index, name='index'),
   path('enquiry/<pk>',views.enquiry, name='enquiry'),
   path('create_enquiry_ajax', views.create_enquiry_ajax, name='create_enquiry_ajax'),
   path('enquiry/<int:enquiry_id>/requests_offers', views.requests_offers_for_enquiry, name='requests_offers_for_enquiry'),
   path('update_offers/', views.update_offers, name='update_offers'),
   path('update_client_offers/', views.update_client_offers, name='update_client_offers'),
   path('enquiry_list', views.enquiry_list,name = 'enquiry_list'),
   path('update_requests/', views.update_requests, name='update_requests'),
   path('update_enquiry_details/', views.update_enquiry_details, name = 'update_enquiry_details'),
   path('api/enquiries/', views.get_enquiries, name='api_enquiries'),
   path('supplier_list/', views.supplier_list, name='supplier_list'),
   path('api/suppliers/', views.suppliers_api, name='suppliers_api'),
   path('supplier_detail/<int:id>/', views.supplier_detail, name='supplier_detail'),
   path('login/', views.login_view, name='login'),
   path('testmail',views.send_email,name ='send_email')

   
]
                                                            