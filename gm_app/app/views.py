from django.shortcuts import render, redirect
from django.db.models.functions import Greatest
from django.views.generic import TemplateView

from django.utils import timezone
from django.views.generic import TemplateView

from .models import Enquiry, Client, Offer, Product, Request, Supplier 
import time
from django.db.models import F
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm , AuthenticationForm
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import re
import os
from dotenv import load_dotenv
import openai
from django.core import serializers
import json
from datetime import *
load_dotenv()  # Load the .env file

gpt4_api_key = os.getenv('OPEN_AI')


def index(request):
    return render(request, 'app/new_enquiry.html')

def forms(request):
    return render(request, 'app/enquiry.html')

@csrf_exempt
def create_enquiry_ajax(request):
    if request.method == 'POST':
        # Decode the JSON payload
        data = json.loads(request.body)

        # Create or get the client
        client_name = data.get('client')
        client, _ = Client.objects.get_or_create(name=client_name)

        # Parse dates
        received_date = datetime.strptime(data.get('inquiry_received_date'), '%m/%d/%Y').date() if data.get('inquiry_received_date') else None
        deadline_date = datetime.strptime(data.get('inquiry_deadline_date'), '%m/%d/%Y').date() if data.get('inquiry_deadline_date') else None

        # Create the enquiry
        enquiry = Enquiry.objects.create(
            client=client,
            received_date=received_date,
            submission_deadline=deadline_date,
            status='ACTIVE'  # Assuming a new enquiry starts as 'ACTIVE'
        )

        # Process each product detail
        for product_detail in data.get('products_details', []):
            product_name = product_detail.get('product_name')
            product, _ = Product.objects.get_or_create(name=product_name)

            # Create request for each product in the enquiry
            request = Request.objects.create(
                enquiry=enquiry,
                product=product,
                specs=product_detail.get('specs', ''),
                size=product_detail.get('size', ''),
                quantity=product_detail.get('quantity', ''),
                packaging=product_detail.get('packaging', ''),
                # Add other fields as necessary
            )

            # Process suppliers for this product
            for supplier_name in product_detail.get('suppliers', []):
                supplier, _ = Supplier.objects.get_or_create(name=supplier_name)
                # Here, you might want to create an offer or a similar relation between the supplier and the request
                # This is an example; adjust according to your needs
                Offer.objects.create(
                    request=request,
                    supplier=supplier,
                    # Populate other fields as necessary
                )

        # Once processing is complete, return a JsonResponse indicating success
        return JsonResponse({'success': True, 'message': 'Enquiry and related data successfully processed.'})

    # If the request method is not POST or if we're not returning within the POST block above,
    # return a response indicating the request method is not allowed.
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
