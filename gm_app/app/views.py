from django.shortcuts import render, redirect,get_object_or_404
from django.db.models.functions import Greatest
from django.views.generic import TemplateView
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.views.generic import TemplateView

from .models import Enquiry, Client, Offer, Product, Request, Supplier, Offer_Client, Manager
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
from django.db.models import Prefetch
from django.db.models import Prefetch


from .models import Enquiry
from django.http import JsonResponse

load_dotenv()  # Load the .env file

gpt4_api_key = os.getenv('OPEN_AI')


def index(request):
    # Fetch all client names
    clients = Client.objects.all().order_by('name').values_list('name', flat=True)

    # Fetch all product names
    products = Product.objects.all().order_by('name').values_list('name', flat=True)

    # Fetch all supplier names
    suppliers = Supplier.objects.all().order_by('name').values_list('name', flat=True)

    # Prepare context to be passed to the template
    context = {
        'clients': list(clients),
        'products': list(products),
        'suppliers': list(suppliers)
    }

    return render(request, 'app/new_enquiry.html', context)

def enquiry(request,pk):
    enquiry = get_object_or_404(Enquiry, pk=pk)
    # Fetch all client names
    clients = Client.objects.all().order_by('name').values_list('name', flat=True)

    # Fetch all product names
    products = Product.objects.all().order_by('name').values_list('name', flat=True)

    # Fetch all supplier names
    suppliers = Supplier.objects.all().order_by('name').values_list('name', flat=True)
    print(enquiry)
    # Prepare context to be passed to the template
    context = {
        'enquiry': enquiry,
        'clients': list(clients),
        'products': list(products),
        'suppliers': list(suppliers)
    }
    return render(request, 'app/enquiry.html', context)


@csrf_exempt
def create_enquiry_ajax(request):
    if request.method == 'POST':
        # Decode the JSON payload
        data = json.loads(request.body)
        print(data)
        # Create or get the client
        client_name = data.get('client')
        print(client_name)
        client, _ = Client.objects.get_or_create(name=client_name)

        # Create or get the manager
        manager_name = data.get('manager')
        manager, _ = Manager.objects.get_or_create(name=manager_name)
        print(manager)

        # Parse dates
        received_date = datetime.strptime(data.get('inquiry_received_date'), '%d/%m/%Y').date() if data.get('inquiry_received_date') else None
        deadline_date = datetime.strptime(data.get('inquiry_deadline_date'), '%d/%m/%Y').date() if data.get('inquiry_deadline_date') else None

        # Create the enquiry
        enquiry = Enquiry.objects.create(
            client=client,
            manager = manager,
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
                incoterms = data.get('incoterm_wanted'),
                discharge_port = data.get('port_of_discharge')

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
        product_name = req.product.name if req.product and req.product.name else "Not available"
        
        req_dict = {
            'product': product_name,
            'id': req.id,
            'specs': req.specs or "",
            'size': req.size or "",
            'quantity': req.quantity or "",
            'incoterms': req.incoterms or "",
            'packaging': req.packaging or "",
            'discharge_port': req.discharge_port or "",
            'payment_terms_requested': req.payment_terms_requested or "",
            'notes': req.notes or "",
            'price_offered': req.price_offered or "",
            'payment_term_offered': req.payment_term_offered or "",
            'validity_offered': req.validity_offered.strftime("%Y-%m-%d") if req.validity_offered else "DD/MM/YYYY",
            'customer_feedback': req.customer_feedback or "",
            'offers': [],
            'offers_client': []
        }

        offers = req.offers.all()
        offers_client = req.offers_client.all()
        
        for offer in offers:
            supplier_name = offer.supplier.name if offer.supplier and offer.supplier.name else "Not available"

            offer_dict = {
                'id': offer.id,
                'supplier': supplier_name,
                'supplier_price': offer.supplier_price or "",
                'incoterms': offer.incoterms or "",
                'specs': offer.specs or "",
                'size': offer.size or "",
                'packaging': offer.packaging or "",
                'payment_terms': offer.payment_terms or "",
                'validity': offer.validity.strftime("%Y-%m-%d") if offer.validity else "DD/MM/YYYY",
                'notes': offer.notes or "",
            }
            req_dict['offers'].append(offer_dict)

        for offer_client in offers_client:
            supplier_name = offer_client.supplier.name if offer_client.supplier and offer_client.supplier.name else "Not available"

            offer_client_dict = {
                'id': offer_client.id,
                'supplier': supplier_name,
                'price_offered': offer_client.price_offered or "",
                'payment_term_offered': offer_client.payment_term_offered or "",
                'validity_offered': offer_client.validity_offered or "DD/MM/YYYY",
                'customer_feedback': offer_client.customer_feedback or "",
                'notes': offer_client.notes or "",
            }
            req_dict['offers_client'].append(offer_client_dict)

        data.append(req_dict)

    return JsonResponse(data, safe=False)


@csrf_exempt
def update_offers(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print(data)
            offers = data.get('offers', [])
            for offer_data in offers:
                supplier_name = offer_data.get('supplier')
                supplier, created = Supplier.objects.get_or_create(name=supplier_name)

                # Convert validity string to date object, set to None if invalid or not provided
                validity_str = offer_data.get('validity')
                validity_date = None
                if validity_str:
                    try:
                        validity_date = datetime.strptime(validity_str, "%Y-%m-%d").date()
                    except ValueError:
                        # Invalid date format, keep validity_date as None
                        pass

                if 'id' not in offer_data or not offer_data['id']:
                    request_instance = Request.objects.get(id=offer_data.get('request_id'))
                    Offer.objects.create(
                        request=request_instance,
                        supplier=supplier,
                        supplier_price=offer_data.get('supplier_price'),
                        payment_terms=offer_data.get('payment_terms'),
                        incoterms=offer_data.get('incoterms'),
                        specs=offer_data.get('specs'),
                        size=offer_data.get('size'),
                        packaging=offer_data.get('packaging'),
                        validity=validity_date,
                        notes=offer_data.get('notes'),
                    )
                else:
                    offer = Offer.objects.get(id=offer_data['id'])
                    offer.supplier = supplier
                    offer.supplier_price = offer_data.get('supplier_price', offer.supplier_price)
                    offer.payment_terms = offer_data.get('payment_terms', offer.payment_terms)
                    offer.incoterms = offer_data.get('incoterms', offer.incoterms)
                    offer.specs = offer_data.get('specs', offer.specs)
                    offer.size = offer_data.get('size', offer.size)
                    offer.packaging = offer_data.get('packaging', offer.packaging)
                    offer.validity = validity_date
                    offer.notes = offer_data.get('notes', offer.notes)
                    offer.save()

            return JsonResponse({'status': 'success', 'message': 'Offers updated successfully.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)
    

@csrf_exempt
def update_client_offers(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            client_offers = data.get('offers', [])
            for offer_data in client_offers:
                supplier_name = offer_data.get('supplier')
                supplier, created = Supplier.objects.get_or_create(name=supplier_name)

                # Assume validity_offered is a string that needs to be converted to a date object, or None if not provided
                validity_str = offer_data.get('validity_offered')
                validity_date = None
                if validity_str:
                    try:
                        validity_date = datetime.strptime(validity_str, "%Y-%m-%d").date()
                    except ValueError:
                        # Invalid date format, keep validity_date as None
                        pass

                # Create new Offer_Client instances or update existing ones
                if 'id' not in offer_data or not offer_data['id']:
                    print("been here")
                    # Assuming 'request_id' is part of offer_data when creating a new offer
                    request_instance = Request.objects.get(id=offer_data.get('request_id'))
                    Offer_Client.objects.create(
                        request=request_instance,
                        supplier=supplier,
                        price_offered=offer_data.get('price_offered'),
                        payment_term_offered=offer_data.get('payment_term_offered'),
                        validity_offered=validity_date,  # Assuming this should be a DateField, adjust if it's a TextField
                        customer_feedback=offer_data.get('customer_feedback'),
                        notes=offer_data.get('notes'),
                    )
                else:
                    # For updating existing client offers
                    client_offer = Offer_Client.objects.get(id=offer_data['id'])
                    client_offer.supplier = supplier
                    client_offer.price_offered = offer_data.get('price_offered', client_offer.price_offered)
                    client_offer.payment_term_offered = offer_data.get('payment_term_offered', client_offer.payment_term_offered)
                    client_offer.validity_offered = validity_date
                    client_offer.customer_feedback = offer_data.get('customer_feedback', client_offer.customer_feedback)
                    client_offer.notes = offer_data.get('notes', client_offer.notes)
                    client_offer.save()

            return JsonResponse({'status': 'success', 'message': 'Client offers updated successfully.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
def update_requests(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body).get('requests', [])
            for req_data in data:
                req = Request.objects.get(id=req_data['id'])
                # Update request fields
                req.quantity = req_data.get('quantity', req.quantity)
                req.specs = req_data.get('specs', req.specs)
                req.size = req_data.get('size', req.size)
                req.payment_terms_requested = req_data.get('payment_terms_requested', req.payment_terms_requested)
                req.incoterms = req_data.get('incoterms', req.incoterms)
                req.discharge_port = req_data.get('discharge_port', req.discharge_port)
                req.packaging = req_data.get('packaging', req.packaging)
                req.notes = req_data.get('notes', req.notes)
                req.save()
            return JsonResponse({'status': 'success', 'message': 'Requests updated successfully.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


@csrf_exempt
def update_enquiry_details(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            enquiry_id = data.get('enquiry_id')  # Retrieve the enquiry ID from the data
            enquiry = get_object_or_404(Enquiry, pk=enquiry_id)
            
            # Update the fields based on data keys
            for key, value in data.items():
                if hasattr(enquiry, key) and key != 'enquiry_id':  # Exclude 'enquiry_id' from being treated as a field
                    # Special handling for date fields
                    if 'date' in key and value:
                        try:
                            value = datetime.strptime(value, '%d/%m/%Y').date()
                        except ValueError:
                            return JsonResponse({'error': 'Invalid date format'}, status=400)
                    setattr(enquiry, key, value)
            
            enquiry.save()
            return JsonResponse({'success': True, 'message': 'Enquiry updated successfully'})
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)



#def enquiry_list(request):
    #return render(request, 'app/enquiry_list.html')

#VARUN's CODE Below: 
def enquiry_list(request):
    # Fetch enquiries with prefetch_related for optimized queries on related objects
    enquiries = Enquiry.objects.prefetch_related(
        Prefetch('enquiry_requests', queryset=Request.objects.select_related('product'))
    ).select_related('manager', 'client').all()

    context = {
        'enquiries': enquiries
    }
    return render(request, 'app/enquiry_list.html', context)

from django.http import JsonResponse
from .models import Enquiry, Request

def get_enquiries(request):
    enquiries_list = []
    enquiries = Enquiry.objects.prefetch_related('enquiry_requests__product').select_related('client', 'manager').all()
    
    for enquiry in enquiries:
        enquiry_dict = {
            'id': enquiry.id,
            'status': enquiry.status,
            'manager': enquiry.manager.name if enquiry.manager else None,
            'client': {
                'name': enquiry.client.name,
                'country': enquiry.client.country if enquiry.client.country else 'Unknown Country',
                'person': enquiry.client.person if enquiry.client.person else 'Unknown Person',
            } if enquiry.client else 'Unknown Client',
            'received_date': enquiry.received_date.strftime('%Y-%m-%d') if enquiry.received_date else 'Unknown Date',
            'enquiry_requests': [],
        }

        for req in enquiry.enquiry_requests.all():
            # Fetching the product name directly from the Product related to the Request
            product_name = 'Unknown Product'
            if req.product_id and Product.objects.filter(id=req.product_id).exists():
                product_name = Product.objects.get(id=req.product_id).name

            request_dict = {
                'id': req.id,
                'quantity': req.quantity,
                'specs': req.specs,
                'product_name': product_name,  # Ensure you get the product name correctly
                # Add other relevant fields from Request as needed
            }
            
            enquiry_dict['enquiry_requests'].append(request_dict)

        enquiries_list.append(enquiry_dict)
    
    return JsonResponse(enquiries_list, safe=False)

#SUPPLIER PAGE-----------------------------------------------------------------------------------------------------------------------

def supplier_list(request):
    return render(request, 'app/supplier_list.html')

from django.http import JsonResponse
from .models import Supplier


def suppliers_api(request):
    suppliers = list(Supplier.objects.values('id','name', 'contact_person', 'email'))
    return JsonResponse({'suppliers': suppliers}, safe=False)


from django.shortcuts import render, get_object_or_404
from .models import Supplier, Offer
from django.db.models import Prefetch
from django.db.models import Avg, Count

def supplier_detail(request, id):
    supplier = get_object_or_404(Supplier, id=id)
    # Fetch recent offers related to this supplier
    offers = Offer.objects.filter(supplier=supplier).prefetch_related(Prefetch('request', queryset=Request.objects.select_related('product'))).order_by('-validity')[:5]

    product_stats = (
        Offer.objects.filter(supplier=supplier)
        .values('request__product__name')  # Group by product name
        .annotate(
            average_price=Avg('supplier_price'),
            total_offers=Count('id')
        )
    )

    return render(request, 'app/supplier_detail.html', {'supplier': supplier, 'offers': offers, 'product_stats': product_stats})
