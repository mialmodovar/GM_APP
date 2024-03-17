from django.shortcuts import render, redirect,get_object_or_404
from django.db.models.functions import Greatest
from django.views.generic import TemplateView
from django.core.exceptions import ObjectDoesNotExist
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
from django.forms.models import model_to_dict

load_dotenv()  # Load the .env file

gpt4_api_key = os.getenv('OPEN_AI')


def index(request):
    return render(request, 'app/new_enquiry.html')

def enquiry(request,pk):
    enquiry = get_object_or_404(Enquiry, pk=pk)
    return render(request, 'app/enquiry.html', {'enquiry': enquiry})


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
        return JsonResponse({'success': True, 'message': 'Enquiry and related data successfully processed.','pk':enquiry.id})

    # If the request method is not POST or if we're not returning within the POST block above,
    # return a response indicating the request method is not allowed.
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
def requests_offers_for_enquiry(request, enquiry_id):
    requests = Request.objects.filter(enquiry_id=enquiry_id).prefetch_related('offers', 'offers__supplier')
    
    data = []
    for req in requests:
        try:
            product_name = req.product.name  # Assuming 'name' field in Product model
        except ObjectDoesNotExist:
            product_name = "Not available"
        
        req_dict = {
            'product': product_name,
            'specs': req.specs,
            'size': req.size,
            'quantity': req.quantity,
            'incoterms': req.incoterms,
            'packaging': req.packaging,
            'discharge_port': req.discharge_port,
            'payment_terms_requested': req.payment_terms_requested,
            'notes': req.notes,
            'price_offered': req.price_offered,
            'payment_term_offered': req.payment_term_offered,
            'validity_offered': req.validity_offered if req.validity_offered else "Not available",  # Handle DateField
            'customer_feedback': req.customer_feedback,
            'offers': []
        }

        offers = req.offers.all()
        for offer in offers:
            try:
                supplier_name = offer.supplier.name  # Assuming 'name' field in Supplier model
            except ObjectDoesNotExist:
                supplier_name = "Not available"

            offer_dict = {
                'id': offer.id,
                'supplier': supplier_name,
                'supplier_price': offer.supplier_price,
                'incoterms': offer.incoterms,
                'specs': offer.specs,
                'size': offer.size,
                'packaging': offer.packaging,
                'payment_terms': offer.payment_terms,
                'validity': offer.validity.strftime("%Y-%m-%d") if offer.validity else "Not available",  # Format DateField
                'notes': offer.notes,
            }
            req_dict['offers'].append(offer_dict)
        
        data.append(req_dict)

    return JsonResponse(data, safe=False)
