from django.db.models import Avg, Count
from django.db.models import Prefetch
from .models import Supplier, Offer
from django.shortcuts import render, get_object_or_404
from .models import Supplier
import json
import os
import pprint
import re
import requests
import time
import base64
from datetime import datetime, timedelta
from django.db.models import Q
from django.conf import settings
from django.contrib.auth import login as auth_login, logout as auth_logout, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.core import serializers
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Avg, Count, F, Prefetch
from django.db.models.functions import Greatest
from django.dispatch import receiver
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from dotenv import load_dotenv

from .models import (Client, Email, Enquiry, Manager, Offer,
                     Offer_Client, Product, Request, Supplier, Attachment, Division, CompanyContact)
from django.core.paginator import Paginator


def microsoft_login(request):
    # Step 1: Redirect user to Microsoft's OAuth 2.0 authorization endpoint
    scope = 'openid profile email User.Read Mail.Read Mail.Read.Shared Mail.ReadBasic Mail.ReadBasic.Shared Mail.ReadWrite Mail.ReadWrite.Shared Mail.Send Mail.Send.Shared MailboxSettings.Read MailboxSettings.ReadWrite offline_access'
    return redirect(
        f"https://login.microsoftonline.com/{settings.MICROSOFT_AUTH_TENANT_ID}/oauth2/v2.0/authorize"
        f"?client_id={settings.MICROSOFT_AUTH_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={settings.MICROSOFT_AUTH_REDIRECT_URI}"
        f"&response_mode=query"
        f"&scope={scope}"
        f"&state=12345"
    )


def microsoft_callback(request):
    # Step 2: Get the authorization code from the callback
    code = request.GET.get('code')

    # Step 3: Exchange authorization code for access and refresh tokens
    token_url = f"https://login.microsoftonline.com/{settings.MICROSOFT_AUTH_TENANT_ID}/oauth2/v2.0/token"
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': settings.MICROSOFT_AUTH_REDIRECT_URI,
        'client_id': settings.MICROSOFT_AUTH_CLIENT_ID,
        'client_secret': settings.MICROSOFT_AUTH_CLIENT_SECRET,
    }
    token_response = requests.post(token_url, data=token_data)
    token_json = token_response.json()

    print(token_json)
    access_token = token_json.get('access_token')
    refresh_token = token_json.get('refresh_token')
    expires_in = token_json.get('expires_in')

    # Handle the case where expires_in is None
    if expires_in is not None:
        expiry_date = datetime.now() + timedelta(seconds=expires_in)
    else:
        expiry_date = datetime.now() + timedelta(days=1)  # Default to 1 day

    # Step 4: Use the access token to get user info
    user_info_url = 'https://graph.microsoft.com/v1.0/me'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    user_info_response = requests.get(user_info_url, headers=headers)
    user_info = user_info_response.json()

    email = user_info.get('mail') or user_info.get('userPrincipalName')

    # Step 5: Check if the user exists, create if not
    user, created = User.objects.get_or_create(
        username=email, defaults={'email': email})
    if created:
        # Since this is an OAuth login, the user won't have a usable password
        user.set_unusable_password()
        user.save()

    # Step 6: Create or update the user profile
    manager, created = Manager.objects.get_or_create(user=user)
    manager.access_token = access_token
    manager.refresh_token = refresh_token
    manager.expiry_token = expiry_date
    manager.save()

    # Step 7: Log the user in
    login(request, user)

    # Redirect to the default login redirect URL
    return redirect(settings.LOGIN_REDIRECT_URL)


@login_required
def ms_logout(request):
    logout(request)
    # Redirect to a success page or homepage
    return redirect('/')


def login_view(request):
    # Check if the user is already authenticated
    if request.user.is_authenticated:
        return redirect('/')
    # Redirect to the dashboard or appropriate page
    return render(request, 'app/login.html')


@login_required
def send_email(request):
    recipient = "miguel.almodovar@globalmonarchuae.com"
    subject = "Hello from Django!"
    content = "This is a test email sent from our Django application using Microsoft Graph API."

    # Get the access token
    token = get_access_token(request)
    if not token:
        return JsonResponse({'error': 'Authentication token is missing or invalid'}, status=403)

    # Construct the email message payload
    email_payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": content
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": recipient
                    }
                }
            ]
        },
        "saveToSentItems": "true"
    }

    # Send the email using Microsoft Graph API
    email_url = 'https://graph.microsoft.com/v1.0/me/sendMail'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(email_url, headers=headers, json=email_payload)

    if response.status_code == 202:
        return JsonResponse({'message': 'Email sent successfully'}, status=202)
    else:
        return JsonResponse({'error': 'Failed to send email', 'details': response.json()}, status=response.status_code)


def refresh_access_token(manager):
    token_url = f"https://login.microsoftonline.com/{settings.MICROSOFT_AUTH_TENANT_ID}/oauth2/v2.0/token"
    token_data = {
        'grant_type': 'refresh_token',
        'refresh_token': manager.refresh_token,
        'client_id': settings.MICROSOFT_AUTH_CLIENT_ID,
        'client_secret': settings.MICROSOFT_AUTH_CLIENT_SECRET,
        'redirect_uri': settings.MICROSOFT_AUTH_REDIRECT_URI,
    }
    token_response = requests.post(token_url, data=token_data)
    token_json = token_response.json()

    access_token = token_json.get('access_token')
    refresh_token = token_json.get('refresh_token')
    expires_in = token_json.get('expires_in')
    expiry_date = timezone.now() + timedelta(seconds=expires_in)

    # Update the user profile with new tokens and expiry date
    manager.access_token = access_token
    manager.refresh_token = refresh_token
    manager.expiry_token = expiry_date
    manager.save()

    return access_token


def get_access_token(request):
    manager = Manager.objects.get(user=request.user)
    if manager.expiry_token and manager.expiry_token > timezone.now():
        return manager.access_token
    else:
        return refresh_access_token(manager)


@login_required
def index(request):
    # Fetch all client names
    clients = Client.objects.all().order_by('name').values_list('name', flat=True)

    # Fetch all product names
    products = Product.objects.all().order_by(
        'name').values_list('name', flat=True)

    # Fetch all supplier names
    suppliers = Supplier.objects.all().order_by(
        'name').values_list('name', flat=True)

    manager = Manager.objects.filter(user=request.user).first()

    # Prepare context to be passed to the template
    context = {
        'manager': manager,
        'clients': list(clients),
        'products': list(products),
        'suppliers': list(suppliers)
    }
    print(manager)
    return render(request, 'app/new_enquiry.html', context)


@login_required
def enquiry(request, pk):
    enquiry = get_object_or_404(Enquiry, pk=pk)
    # Fetch all client names
    clients = Client.objects.all().order_by('name').values_list('name', flat=True)

    # Fetch all product names
    products = Product.objects.all().order_by(
        'name').values_list('name', flat=True)

    # Fetch all supplier names
    suppliers = Supplier.objects.all().order_by(
        'name').values_list('name', flat=True)
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
@login_required
def create_enquiry_ajax(request):
    if request.method == 'POST':
        data = json.loads(request.POST.get('data'))
        print(data)
        # Ensure client name is provided
        client_name = data.get('client')
        if not client_name:
            return JsonResponse({'success': False, 'message': 'Client name is required.'}, status=400)

        client, _ = Client.objects.get_or_create(name=client_name)
        manager = Manager.objects.filter(user=request.user).first()
        if not manager:
            return JsonResponse({'success': False, 'message': 'No manager associated with this user.'}, status=404)

        # Assuming data contains the necessary date information
        try:
            received_date = datetime.strptime(data.get(
                'inquiry_received_date'), '%Y-%m-%d').date() if data.get('inquiry_received_date') else None
            deadline_date = datetime.strptime(data.get(
                'inquiry_deadline_date'), '%Y-%m-%d').date() if data.get('inquiry_deadline_date') else None
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid date format.'}, status=400)

        enquiry = Enquiry.objects.create(
            client=client,
            manager=manager,
            received_date=received_date,
            submission_deadline=deadline_date,
            status='ACTIVE'
        )

        # Process enquiry files
        for file in request.FILES.getlist('enquiry_files[]'):
            Attachment.objects.create(
                enquiry=enquiry,
                file=file
            )

        # Process each product detail
        for index, product_detail in enumerate(data.get('products_details', [])):
            product_name = product_detail.get('product_name')
            product, _ = Product.objects.get_or_create(name=product_name)

            # Create request for each product in the enquiry
            request_instance = Request.objects.create(
                enquiry=enquiry,
                product=product,
                specs=product_detail.get('specs', ''),
                size=product_detail.get('size', ''),
                quantity=product_detail.get('quantity', ''),
                quantity_unit=product_detail.get(
                    'quantity_unit', ''),  # New field
                packaging=product_detail.get('packaging', ''),
                incoterms=data.get('incoterm_wanted'),
                target_price=product_detail.get(
                    'target_price', ''),  # New field
                delivery_schedule=product_detail.get(
                    'delivery_schedule', [])  # New field
            )

            # Check if there's a file to attach for this product
            file_key = f'product_files[{index}]'
            if file_key in request.FILES:
                file = request.FILES[file_key]
                # Save the file
                attachment = Attachment.objects.create(
                    request=request_instance,
                    file=file
                )
                # Update specs to reference the attachment
                request_instance.specs = f"//attach:{attachment.id}"
                request_instance.save()

            # Process suppliers for this product
            for supplier_name in product_detail.get('suppliers', []):
                supplier, _ = Supplier.objects.get_or_create(
                    name=supplier_name)
                # Create an offer or a similar relation between the supplier and the request
                Offer.objects.create(
                    request=request_instance,
                    supplier=supplier,
                )

        return JsonResponse({'success': True, 'message': 'Enquiry and related data successfully processed.', 'pk': enquiry.id})
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)


@csrf_exempt
@login_required
def requests_offers_for_enquiry(request, enquiry_id):
    requests = Request.objects.filter(
        enquiry_id=enquiry_id).prefetch_related('offers', 'offers__supplier')

    data = []
    for req in requests:
        product_name = req.product.name if req.product and req.product.name else "Not available"

        specs = req.specs or ""
        if specs.startswith("//attach:"):
            try:
                attachment_id = int(specs.split(":")[1])
                attachment = Attachment.objects.get(id=attachment_id)
                specs = request.build_absolute_uri(attachment.file.url)
            except (Attachment.DoesNotExist, ValueError):
                specs = "Attachment not found"

        req_dict = {
            'product': product_name,
            'id': req.id,
            'specs': specs,
            'quantity_unit': req.quantity_unit or "",
            'size': req.size or "",
            'quantity': req.quantity or "",
            'incoterms': req.incoterms or "",
            'packaging': req.packaging or "",
            'payment_terms_requested': req.payment_terms_requested or "",
            'notes': req.notes or "",
            'target_price': req.target_price,
            'delivery_schedule': req.delivery_schedule or "",
            'offers': [],
            'offers_client': [],
            'emails': []
        }

        offers = req.offers.all()
        offers_client = req.offers_client.all()
        emails = Email.objects.filter(request=req)

        for offer in offers:
            supplier_name = offer.supplier.name if offer.supplier and offer.supplier.name else "Not available"

            offer_dict = {
                'id': offer.id,
                'supplier': supplier_name,
                'supplier_id': offer.supplier.id,
                'supplier_price': offer.supplier_price or "",
                'incoterms': offer.incoterms or "",
                'specs': offer.specs or "",
                'size': offer.size or "",
                'packaging': offer.packaging or "",
                'payment_terms': offer.payment_terms or "",
                'validity': offer.validity.strftime("%d/%m/%Y") if offer.validity else "DD/MM/YYYY",
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
                'incoterms': offer_client.incoterms or "",
                'margin': offer_client.margin or "",
                'notes': offer_client.notes or "",
            }
            req_dict['offers_client'].append(offer_client_dict)

        for email in emails:
            email_dict = {
                'uuid': email.uuid,
                'manager': email.manager.name if email.manager else "Not available",
                'supplier_id': email.supplier.id if email.supplier else None,
                'recipient': email.recipients,
                'subject': email.subject,
                'message': email.message,
                'sent_at': email.sent_at.strftime("%Y-%m-%d %H:%M") if email.sent_at else "DD/MM/YYYY HH:MM",
                'read_at': email.read_at.strftime("%Y-%m-%d %H:%M") if email.read_at else "DD/MM/YYYY HH:MM",
                'status': email.status,
                'response_received': email.response_received,
                'response_details': email.response_details or "",
            }
            print(email_dict)
            req_dict['emails'].append(email_dict)

        data.append(req_dict)

    return JsonResponse(data, safe=False)


@csrf_exempt
@login_required
def update_client_offers(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print(data)

            # Extract request_id
            if 'request_id' in data[0]:
                request_id = data[0]['request_id']
            else:
                return JsonResponse({'status': 'error', 'message': 'Request ID is required.'}, status=400)

            # Extract offers
            client_offers = data[1].get('offers', [])

            request_instance = Request.objects.get(id=request_id)

            # Get existing client offers for the request
            existing_client_offers = Offer_Client.objects.filter(
                request=request_instance)
            existing_client_offer_ids = set(
                existing_client_offers.values_list('id', flat=True))
            received_client_offer_ids = set()

            for offer_data in client_offers:
                supplier_name = offer_data.get('supplier')
                supplier, created = Supplier.objects.get_or_create(
                    name=supplier_name)

                # Convert validity string to date object, set to None if invalid or not provided
                validity_str = offer_data.get('validity_offered')
                validity_date = None

                if validity_str:
                    try:
                        validity_date = datetime.strptime(
                            validity_str, "%Y-%m-%d").date()
                    except ValueError:
                        # Invalid date format, keep validity_date as None
                        pass

                if 'id' not in offer_data or not offer_data['id']:
                    # Create new Offer_Client instances
                    Offer_Client.objects.create(
                        request=request_instance,
                        supplier=supplier,
                        price_offered=offer_data.get('price_offered'),
                        payment_term_offered=offer_data.get(
                            'payment_term_offered'),
                        validity_offered=validity_date,
                        margin=offer_data.get('margin'),
                        incoterms=offer_data.get('incoterms'),
                        customer_feedback=offer_data.get('customer_feedback'),
                        notes=offer_data.get('notes'),
                    )
                else:
                    # Update existing client offers
                    client_offer = Offer_Client.objects.get(
                        id=offer_data['id'])
                    received_client_offer_ids.add(client_offer.id)
                    client_offer.supplier = supplier
                    client_offer.price_offered = offer_data.get(
                        'price_offered', client_offer.price_offered)
                    client_offer.payment_term_offered = offer_data.get(
                        'payment_term_offered', client_offer.payment_term_offered)
                    client_offer.validity_offered = validity_date
                    client_offer.margin = offer_data.get(
                        'margin', client_offer.margin)
                    client_offer.customer_feedback = offer_data.get(
                        'customer_feedback', client_offer.customer_feedback)
                    client_offer.incoterms = offer_data.get(
                        'incoterms', client_offer.incoterms)
                    client_offer.notes = offer_data.get(
                        'notes', client_offer.notes)
                    client_offer.save()

            # Delete offers that were not received in the AJAX request
            client_offers_to_delete = existing_client_offer_ids - received_client_offer_ids
            Offer_Client.objects.filter(
                id__in=client_offers_to_delete).delete()

            return JsonResponse({'status': 'success', 'message': 'Client offers updated successfully.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


@csrf_exempt
@login_required
def update_requests(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print(data)

            # Extract enquiry_id
            if 'enquiry_id' in data[0]:
                enquiry_id = data[0]['enquiry_id']
            else:
                return JsonResponse({'status': 'error', 'message': 'Enquiry ID is required.'}, status=400)

            # Extract requests
            requests = data[1].get('requests', [])

            enquiry_instance = Enquiry.objects.get(id=enquiry_id)

            # Get existing requests for the enquiry
            existing_requests = Request.objects.filter(
                enquiry=enquiry_instance)
            existing_request_ids = set(
                existing_requests.values_list('id', flat=True))
            received_request_ids = set()

            for req_data in requests:
                product_name = req_data.get('product')
                product = None
                if product_name:
                    product, _ = Product.objects.get_or_create(
                        name=product_name)

                if 'id' not in req_data or not req_data['id']:
                    # Creating a new request
                    new_request = Request.objects.create(
                        enquiry=enquiry_instance,
                        product=product,
                        quantity=req_data.get('quantity'),
                        quantity_unit=req_data.get('quantity_unit'),
                        size=req_data.get('size'),
                        payment_terms_requested=req_data.get(
                            'payment_terms_requested'),
                        incoterms=req_data.get('incoterms'),
                        packaging=req_data.get('packaging'),
                        notes=req_data.get('notes'),
                        specs=req_data.get('specs'),
                        delivery_schedule=req_data.get('delivery_schedule'),
                        target_price=req_data.get('target_price')
                    )
                    received_request_ids.add(new_request.id)
                else:
                    # Updating an existing request
                    req = Request.objects.get(id=req_data['id'])
                    received_request_ids.add(req.id)
                    if product:
                        req.product = product
                    if 'quantity' in req_data:
                        req.quantity = req_data['quantity']
                    if 'quantity_unit' in req_data:
                        req.quantity_unit = req_data['quantity_unit']
                    if 'size' in req_data:
                        req.size = req_data['size']
                    if 'payment_terms_requested' in req_data:
                        req.payment_terms_requested = req_data['payment_terms_requested']
                    if 'incoterms' in req_data:
                        req.incoterms = req_data['incoterms']
                    if 'packaging' in req_data:
                        req.packaging = req_data['packaging']
                    if 'notes' in req_data:
                        req.notes = req_data['notes']
                    if 'specs' in req_data:
                        req.specs = req_data['specs']
                    if 'delivery_schedule' in req_data:
                        req.delivery_schedule = req_data['delivery_schedule']
                    if 'target_price' in req_data:
                        req.target_price = req_data['target_price']
                    req.save()

            # Delete requests that were not received in the AJAX request
            requests_to_delete = existing_request_ids - received_request_ids
            Request.objects.filter(id__in=requests_to_delete).delete()

            return JsonResponse({'status': 'success', 'message': 'Requests updated successfully.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


@csrf_exempt
@login_required
def update_offers(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print(data)

            # Extract request_id
            if 'request_id' in data[0]:
                request_id = data[0]['request_id']
            else:
                return JsonResponse({'status': 'error', 'message': 'Request ID is required.'}, status=400)

            # Extract offers
            offers = data[1].get('offers', [])

            request_instance = Request.objects.get(id=request_id)

            # Get existing offers for the request
            existing_offers = Offer.objects.filter(request=request_instance)
            existing_offer_ids = set(
                existing_offers.values_list('id', flat=True))
            received_offer_ids = set()

            for offer_data in offers:
                supplier_name = offer_data.get('supplier')
                supplier, created = Supplier.objects.get_or_create(
                    name=supplier_name)

                # Convert validity string to date object, set to None if invalid or not provided
                validity_str = offer_data.get('validity')
                validity_date = None

                if validity_str:
                    try:
                        validity_date = datetime.strptime(
                            validity_str, "%Y-%m-%d").date()
                    except ValueError:
                        # Invalid date format, keep validity_date as None
                        pass

                if 'id' not in offer_data or not offer_data['id']:
                    # Create new offer
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
                    # Update existing offer
                    offer = Offer.objects.get(id=offer_data['id'])
                    received_offer_ids.add(offer.id)
                    offer.supplier = supplier
                    offer.supplier_price = offer_data.get(
                        'supplier_price', offer.supplier_price)
                    offer.payment_terms = offer_data.get(
                        'payment_terms', offer.payment_terms)
                    offer.incoterms = offer_data.get(
                        'incoterms', offer.incoterms)
                    offer.specs = offer_data.get('specs', offer.specs)
                    offer.size = offer_data.get('size', offer.size)
                    offer.packaging = offer_data.get(
                        'packaging', offer.packaging)
                    offer.validity = validity_date
                    offer.notes = offer_data.get('notes', offer.notes)
                    offer.save()

            # Delete offers that were not received in the AJAX request
            offers_to_delete = existing_offer_ids - received_offer_ids
            Offer.objects.filter(id__in=offers_to_delete).delete()

            return JsonResponse({'status': 'success', 'message': 'Offers updated successfully.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


@csrf_exempt
@login_required
def update_enquiry_details(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            enquiry_id = data.get('enquiry_id').strip()
            enquiry = get_object_or_404(Enquiry, pk=enquiry_id)

            # Update the fields individually
            if 'status' in data:
                enquiry.status = data['status']

            if 'received_date' in data:
                try:
                    enquiry.received_date = datetime.strptime(
                        data['received_date'], '%d/%m/%Y').date()
                except ValueError:
                    return JsonResponse({'error': 'Invalid date format for received_date'}, status=400)

            if 'submission_deadline' in data:
                try:
                    enquiry.submission_deadline = datetime.strptime(
                        data['submission_deadline'], '%d/%m/%Y').date()
                except ValueError:
                    return JsonResponse({'error': 'Invalid date format for submission_deadline'}, status=400)

            if 'submission_date' in data:
                try:
                    enquiry.submission_date = datetime.strptime(
                        data['submission_date'], '%d/%m/%Y').date()
                except ValueError:
                    return JsonResponse({'error': 'Invalid date format for submission_date'}, status=400)

            try:
                enquiry.save()
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)

            return JsonResponse({'success': True, 'message': 'Enquiry updated successfully'})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


# def enquiry_list(request):
    # return render(request, 'app/enquiry_list.html')

# VARUN's CODE Below:


@login_required
def enquiry_list(request):
    # Fetch enquiries with prefetch_related for optimized queries on related objects
    enquiries = Enquiry.objects.prefetch_related(
        Prefetch('enquiry_requests',
                 queryset=Request.objects.select_related('product'))
    ).select_related('manager', 'client').all()

    context = {
        'enquiries': enquiries
    }
    return render(request, 'app/enquiry_list.html', context)


@login_required
def get_enquiries(request):
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    search_query = request.GET.get('search', None)
    status_filter = request.GET.get('status', None)
    manager_filter = request.GET.get('manager', None)
    client_filter = request.GET.get('client', None)
    product_filter = request.GET.get('product', None)
    division_filter = request.GET.get('division', None)
    received_date_from = request.GET.get('received_date_from', None)
    received_date_to = request.GET.get('received_date_to', None)

    enquiries = Enquiry.objects.select_related(
        'client', 'manager').prefetch_related('enquiry_requests__product')

    if search_query:
        enquiries = enquiries.filter(
            Q(client__name__icontains=search_query) |
            Q(manager__name__icontains=search_query)
        )

    if status_filter:
        enquiries = enquiries.filter(status=status_filter)

    if manager_filter:
        enquiries = enquiries.filter(manager__name=manager_filter)

    if client_filter:
        enquiries = enquiries.filter(client__name__icontains=client_filter)

    if product_filter:
        enquiries = enquiries.filter(
            enquiry_requests__product__name__icontains=product_filter)

    if division_filter:
        managers_in_division = Manager.objects.filter(division=division_filter)
        enquiries = enquiries.filter(manager__in=managers_in_division)

    if received_date_from:
        enquiries = enquiries.filter(received_date__gte=received_date_from)

    if received_date_to:
        enquiries = enquiries.filter(received_date__lte=received_date_to)

    total_count = enquiries.count()
    enquiries = enquiries[(page-1)*page_size:page*page_size]

    enquiries_list = []
    for enquiry in enquiries:
        enquiry_dict = {
            'id': enquiry.id,
            'status': enquiry.status,
            'manager': enquiry.manager.name if enquiry.manager else 'N/A',
            'client': {
                'name': enquiry.client.name,
            } if enquiry.client else 'Unknown Client',
            'received_date': enquiry.received_date.strftime('%Y-%m-%d') if enquiry.received_date else 'Unknown Date',
            'enquiry_requests': [
                {
                    'id': req.id,
                    'product_name': req.product.name if req.product else 'Unknown Product',
                    'quantity': req.quantity,
                } for req in enquiry.enquiry_requests.all()
            ],
        }
        enquiries_list.append(enquiry_dict)

    return JsonResponse({
        'enquiries': enquiries_list,
        'page': page,
        'pages': (total_count + page_size - 1) // page_size,
    })


@login_required
def get_filter_values(request):
    status_values = Enquiry.objects.values_list('status', flat=True).distinct()
    manager_values = Enquiry.objects.values_list(
        'manager__name', flat=True).distinct()
    client_values = Enquiry.objects.values_list(
        'client__name', flat=True).distinct()
    product_values = Product.objects.values_list('name', flat=True).distinct()

    response = {
        'statuses': list(status_values),
        'managers': list(manager_values),
        'clients': list(client_values),
        'products': list(product_values),
    }

    return JsonResponse(response)


@login_required
def search_enquiries(request):
    query = request.GET.get('query', '').strip().lower()
    if not query:
        return JsonResponse({'error': 'No search query provided.'}, status=400)

    enquiries = Enquiry.objects.filter(
        Q(status__icontains=query) |
        Q(manager__name__icontains=query) |
        Q(client__name__icontains=query) |
        Q(received_date__icontains=query) |
        Q(enquiry_requests__product__name__icontains=query) |
        Q(enquiry_requests__quantity__icontains=query)
    ).distinct()

    results = []
    for enquiry in enquiries:
        results.append({
            'id': enquiry.id,
            'status': enquiry.status,
            'manager': enquiry.manager.name if enquiry.manager else 'N/A',
            'client': enquiry.client.name if enquiry.client else 'N/A',
            'products': [req.product.name for req in enquiry.enquiry_requests.all()],
            'received_date': enquiry.received_date.strftime('%Y-%m-%d') if enquiry.received_date else 'N/A',
            'quantity': sum(req.quantity for req in enquiry.enquiry_requests.all())
        })

    return JsonResponse({'results': results})
# SUPPLIER PAGE-----------------------------------------------------------------------------------------------------------------------


@login_required
def supplier_list(request):
    divisions = Division.objects.all()
    return render(request, 'app/supplier_list.html', {'divisions': divisions})


@login_required
def suppliers_api(request):
    divisions = Division.objects.all()
    divisions_data = []

    for division in divisions:
        suppliers = Supplier.objects.filter(division=division)
        suppliers_list = []
        for supplier in suppliers:
            products = [product.name for product in supplier.products.all()]
            contacts = supplier.contacts.all()
            contact_person = contacts[0].name if contacts.exists() else None
            email = contacts[0].email if contacts.exists() else None
            suppliers_list.append({
                'id': supplier.id,
                'name': supplier.name,
                'contact_person': contact_person,
                'email': email,
                'products': ', '.join(products)
            })
        divisions_data.append({
            'id': division.id,
            'name': division.name,
            'suppliers': suppliers_list
        })

    return JsonResponse({'divisions': divisions_data}, safe=False)


@login_required
def supplier_detail(request, id):
    supplier = get_object_or_404(Supplier, id=id)
    supplier_country = supplier.country if supplier.country else ""
    supplier_contact_person = supplier.contacts.first(
    ).name if supplier.contacts.exists() else ""
    supplier_email = supplier.contacts.first(
    ).email if supplier.contacts.exists() else ""
    contacts = supplier.contacts.all()
    divisions = Division.objects.all()
    all_products = Product.objects.all()
    # Fetch recent offers related to this supplier
    offers = Offer.objects.filter(supplier=supplier).prefetch_related(Prefetch(
        'request', queryset=Request.objects.select_related('product'))).order_by('-validity')[:5]
    product_stats = (
        Offer.objects.filter(supplier=supplier)
        .values('request__product__name')  # Group by product name
        .annotate(
            total_offers=Count('id')
        )
    )
    return render(request, 'app/supplier_detail.html', {'supplier': supplier, 'offers': offers, 'product_stats': product_stats, 'divisions': divisions, 'all_products': all_products, 'contacts': contacts, 'supplier_contact_person': supplier_contact_person, 'supplier_email': supplier_email, 'selected_contact_id': supplier.contacts.first().id if supplier.contacts.exists() else None, 'selected_contact_email': supplier_email, 'supplier_country': supplier_country})


@login_required
def draft_email_display(request):
    supplier_ids = request.GET.getlist('supplier_ids[]')
    print("Supplier IDs (string):", supplier_ids)

    request_id = request.GET.get('request_id')

    # Convert supplier_ids to integers safely
    int_supplier_ids = []
    for sid in supplier_ids:
        try:
            int_supplier_ids.append(int(sid))
        except ValueError:
            print(f"Error converting {sid} to integer.")
            continue  # Skip invalid ids

    print("Supplier IDs (int):", int_supplier_ids)

    if not int_supplier_ids:
        print("No valid supplier IDs found after conversion.")
        return render(request, 'app/error.html', {'error': 'No valid supplier IDs provided'})

    # Retrieve suppliers based on the converted IDs
    suppliers = Supplier.objects.filter(
        id__in=int_supplier_ids)  # Corrected typo here
    print("Suppliers QuerySet:", suppliers)

    if not request_id:
        print("No request ID provided.")
        return render(request, 'app/error.html', {'error': 'No request ID provided'})

    try:
        request_obj = Request.objects.get(id=request_id)
    except Request.DoesNotExist:
        print("No Request matches the given query.")
        return render(request, 'app/error.html', {'error': 'No Request matches the given query.'})

    manager = request.user.manager  # Get the Manager object from the request.user
    # Retrieve the group_mail addresses from all divisions associated with the manager
    group_mail_list = manager.divisions.values_list('group_mail', flat=True)

    # Join the group_mail addresses into a single string, separated by commas
    group_mail_addresses = ', '.join(filter(None, group_mail_list))
    print(group_mail_addresses)
    emails = []
    # Retrieve or create Email objects for each supplier
    for supplier in suppliers:
        email = Email.objects.filter(
            supplier=supplier, request=request_obj).first()
        if not email:
            email = Email.objects.create(
                supplier=supplier, request=request_obj, manager=manager, cc=group_mail_addresses)
            print(
                f"Created new Email instance for supplier {supplier.id}, request {request_obj.id}, and manager {manager.id}")

            request_attachments = Attachment.objects.filter(
                request=request_obj, enquiry__isnull=True, email__isnull=True)
            for req_attachment in request_attachments:
                attachment = Attachment.objects.create(
                    email=email, request=request_obj, file=req_attachment.file
                )
                print(
                    f"Created new Attachment for email {email.uuid} with file {req_attachment.file.name}")

        emails.append(email)

    # Serialize the data to a JSON-friendly format
    emails_with_attachments = []
    for email in emails:
        attachments = list(email.attachments.values('id', 'file'))
        supplier_contacts = list(email.supplier.contacts.values('name', 'email')) if email.supplier else []
        emails_with_attachments.append({
            'email': {
                'id': email.id,
                'uuid': str(email.uuid),
                'supplier': email.supplier.name if email.supplier else None,
                'cc': email.cc,
                'subject': email.subject,
                'message': email.message,
                'status': email.status,
                'sent_at': email.sent_at.strftime('%Y-%m-%d %H:%M:%S') if email.sent_at else None,
                'read_at': email.read_at.strftime('%Y-%m-%d %H:%M:%S') if email.read_at else None,
                'response_received': email.response_received,
                'response_details': email.response_details
            },
            'attachments': attachments,
            'supplier_emails': [contact['email'] for contact in supplier_contacts],
            'supplier_contacts': supplier_contacts
        })

    # Prepare the context with the email objects
    context = {
        'emails_with_attachments': emails_with_attachments,
        'enquiry': {
            'id': request_obj.enquiry.id,
            'manager': request_obj.enquiry.manager.name if request_obj.enquiry.manager else None,
            'client': request_obj.enquiry.client.name if request_obj.enquiry.client else None,
            'received_date': request_obj.enquiry.received_date.strftime('%Y-%m-%d') if request_obj.enquiry.received_date else None,
            'submission_deadline': request_obj.enquiry.submission_deadline.strftime('%Y-%m-%d') if request_obj.enquiry.submission_deadline else None,
            'submission_date': request_obj.enquiry.submission_date.strftime('%Y-%m-%d') if request_obj.enquiry.submission_date else None,
            'status': request_obj.enquiry.status,
        },
        'request_obj': {
            'id': request_obj.id,
            'product': {'name': request_obj.product.name},
            'size': request_obj.size,
            'incoterms': request_obj.incoterms,
            'packaging': request_obj.packaging,
            'target_price': request_obj.target_price,
            'specs': request_obj.specs,
            'quantity': request_obj.quantity,
            'quantity_unit': request_obj.quantity_unit,
            'delivery_schedule': request_obj.delivery_schedule  # Assuming this is a JSONField
        }
    }

    return render(request, 'app/draft-email.html', context)


@login_required
def upload_attachment(request):
    if request.method == 'POST' and request.FILES.getlist('files[]'):
        files = request.FILES.getlist('files[]')
        email_ids = request.POST.getlist('email_id')

        if not email_ids:
            return JsonResponse({'success': False, 'error': 'No email IDs provided'})

        attachments_by_email = {}

        for email_id in email_ids:
            try:
                email = Email.objects.get(id=email_id)
            except Email.DoesNotExist:
                return JsonResponse({'success': False, 'error': f'Email with id {email_id} not found'})

            attachments_by_email[email_id] = []

            for file in files:
                attachment = Attachment.objects.create(
                    email=email, request=email.request, file=file)
                print(f"Attachment created: {attachment.file.path}")
                attachments_by_email[email_id].append(attachment.id)

        return JsonResponse({'success': True, 'attachments': attachments_by_email})

    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def remove_attachment(request):
    if request.method == 'POST':
        attachment_id = request.POST.get('attachment_id')
        try:
            attachment = Attachment.objects.get(id=attachment_id)
            attachment.delete()
            return JsonResponse({'success': True})
        except Attachment.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Attachment not found'})

    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
@login_required
def send_email_ajax(request):
    if request.method == 'POST':
        email_id = request.POST.get('email_id')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        recipients = request.POST.getlist('recipients[]')
        cc = request.POST.getlist('cc[]')

        # Extract email object from database
        email = get_object_or_404(Email, id=email_id)

        # Convert lists to semicolon-separated strings
        recipients_str = ';'.join(recipients)
        cc_str = ';'.join(cc)

        # Update email object with new information
        email.subject = subject
        email.message = message
        email.recipients = recipients_str
        email.cc = cc_str
        email.save()

        # Get the access token
        token = get_access_token(request)
        if not token:
            return JsonResponse({'error': 'Authentication token is missing or invalid'}, status=403)

        # Prepare attachments
        attachments = []
        for attachment in email.attachments.all():
            with open(attachment.file.path, 'rb') as f:
                content = f.read()
                attachments.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": attachment.file.name,
                    "contentBytes": base64.b64encode(content).decode('utf-8')
                })

        # Construct the email message payload
        to_recipients = [{"emailAddress": {"address": email}}
                         for email in recipients]
        cc_recipients_payload = [
            {"emailAddress": {"address": email}} for email in cc]

        email_payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": message
                },
                "toRecipients": to_recipients,
                "ccRecipients": cc_recipients_payload,
                "attachments": attachments
            },
            "saveToSentItems": "true"
        }

        # Send the email using Microsoft Graph API
        email_url = 'https://graph.microsoft.com/v1.0/me/sendMail'
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        response = requests.post(
            email_url, headers=headers, json=email_payload)

        if response.status_code == 202:
            email.status = 'SENT'  # Assuming you want to update the status to SENT after sending
            email.save()
            return JsonResponse({'message': 'Email sent successfully'}, status=202)
        else:
            email.status = 'FAILED'  # Assuming you want to update the status to FAILED after sending
            email.save()
            return JsonResponse({'error': 'Failed to send email', 'details': response.json()}, status=response.status_code)
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@csrf_exempt
def update_supplier(request, supplier_id):
    if request.method == 'POST':
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            supplier.name = request.POST.get('name')
            supplier.country = request.POST.get(
                'country')  # Update country field

            division_id = request.POST.get('division')
            if division_id:
                supplier.division = Division.objects.get(id=division_id)
            supplier.save()

            contact_id = request.POST.get('contact_id')
            contact_name = request.POST.get('contact_person')
            contact_email = request.POST.get('contact_email')
            if contact_id:
                contact = CompanyContact.objects.get(id=contact_id)
                contact.name = contact_name
                contact.email = contact_email
                contact.save()

            return JsonResponse({'status': 'success'})
        except Supplier.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Supplier not found'})
        except CompanyContact.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Contact not found'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@csrf_exempt
def add_product_to_supplier(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        supplier_id = request.POST.get('supplier_id')
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            product = Product.objects.get(id=product_id)
            supplier.products.add(product)
            return JsonResponse({'status': 'success'})
        except Supplier.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Supplier not found'})
        except Product.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Product not found'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@csrf_exempt
def delete_product_from_supplier(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        supplier_id = request.POST.get('supplier_id')
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            product = Product.objects.get(id=product_id)
            supplier.products.remove(product)
            return JsonResponse({'status': 'success'})
        except Supplier.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Supplier not found'})
        except Product.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Product not found'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


def get_contact_email(request, contact_id):
    contact = get_object_or_404(CompanyContact, id=contact_id)
    return JsonResponse({'email': contact.email})


@csrf_exempt
def update_contact(request, contact_id):
    if request.method == 'POST':
        try:
            contact = CompanyContact.objects.get(id=contact_id)
            data = json.loads(request.body)
            contact.name = data.get('name')
            contact.email = data.get('email')
            contact.phone = data.get('phone')
            contact.personal_phone = data.get('personal_phone')
            contact.job_title = data.get('job_title')
            contact.save()
            return JsonResponse({'status': 'success'})
        except CompanyContact.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Contact not found'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@csrf_exempt
def add_supplier_contact(request, supplier_id):
    if request.method == 'POST':
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            data = json.loads(request.body)
            contact_name = data.get('contact_person')
            contact_email = data.get('contact_email')
            contact_phone = data.get('contact_phone', '')
            personal_phone = data.get('personal_phone', '')
            job_title = data.get('job_title', '')

            new_contact = CompanyContact.objects.create(
                name=contact_name,
                email=contact_email,
                phone=contact_phone,
                personal_phone=personal_phone,
                job_title=job_title
            )
            supplier.contacts.add(new_contact)
            return JsonResponse({'status': 'success', 'contact_id': new_contact.id})
        except Supplier.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Supplier not found'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


def delete_contact(request, contact_id):
    if request.method == 'POST':
        try:
            contact = CompanyContact.objects.get(id=contact_id)
            contact.delete()
            return JsonResponse({'status': 'success'})
        except CompanyContact.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Contact not found'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
