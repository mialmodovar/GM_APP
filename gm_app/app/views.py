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
                     Offer_Client, Product, Request, Supplier, Attachment)


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
                'inquiry_received_date'), '%d/%m/%Y').date() if data.get('inquiry_received_date') else None
            deadline_date = datetime.strptime(data.get(
                'inquiry_deadline_date'), '%d/%m/%Y').date() if data.get('inquiry_deadline_date') else None
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid date format.'}, status=400)

        enquiry = Enquiry.objects.create(
            client=client,
            manager=manager,
            received_date=received_date,
            submission_deadline=deadline_date,
            status='ACTIVE'
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
                packaging=product_detail.get('packaging', ''),
                incoterms=data.get('incoterm_wanted'),
                discharge_port=data.get('port_of_discharge')
            )

            # Check if there's a file to attach
            file_key = f'files[{index}]'
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
                supplier, _ = Supplier.objects.get_or_create(name=supplier_name)
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
            'size': req.size or "",
            'quantity': req.quantity or "",
            'incoterms': req.incoterms or "",
            'packaging': req.packaging or "",
            'discharge_port': req.discharge_port or "",
            'payment_terms_requested': req.payment_terms_requested or "",
            'notes': req.notes or "",
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

        for email in emails:
            email_dict = {
                'uuid': email.uuid,
                'manager': email.manager.name if email.manager else "Not available",
                'supplier_id': email.supplier.id if email.supplier else None,
                'recipient': email.recipient,
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
def update_offers(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            offers = data.get('offers', [])
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
                    request_instance = Request.objects.get(
                        id=offer_data.get('request_id'))
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

            return JsonResponse({'status': 'success', 'message': 'Offers updated successfully.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


@csrf_exempt
@login_required
def update_client_offers(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            client_offers = data.get('offers', [])
            for offer_data in client_offers:
                supplier_name = offer_data.get('supplier')
                supplier, created = Supplier.objects.get_or_create(
                    name=supplier_name)

                # Assume validity_offered is a string that needs to be converted to a date object, or None if not provided
                validity_str = offer_data.get('validity_offered')
                validity_date = None
                if validity_str:
                    try:
                        validity_date = datetime.strptime(
                            validity_str, "%Y-%m-%d").date()
                    except ValueError:
                        # Invalid date format, keep validity_date as None
                        pass

                # Create new Offer_Client instances or update existing ones
                if 'id' not in offer_data or not offer_data['id']:
                    print("been here")
                    # Assuming 'request_id' is part of offer_data when creating a new offer
                    request_instance = Request.objects.get(
                        id=offer_data.get('request_id'))
                    Offer_Client.objects.create(
                        request=request_instance,
                        supplier=supplier,
                        price_offered=offer_data.get('price_offered'),
                        payment_term_offered=offer_data.get(
                            'payment_term_offered'),
                        # Assuming this should be a DateField, adjust if it's a TextField
                        validity_offered=validity_date,
                        customer_feedback=offer_data.get('customer_feedback'),
                        notes=offer_data.get('notes'),
                    )
                else:
                    # For updating existing client offers
                    client_offer = Offer_Client.objects.get(
                        id=offer_data['id'])
                    client_offer.supplier = supplier
                    client_offer.price_offered = offer_data.get(
                        'price_offered', client_offer.price_offered)
                    client_offer.payment_term_offered = offer_data.get(
                        'payment_term_offered', client_offer.payment_term_offered)
                    client_offer.validity_offered = validity_date
                    client_offer.customer_feedback = offer_data.get(
                        'customer_feedback', client_offer.customer_feedback)
                    client_offer.notes = offer_data.get(
                        'notes', client_offer.notes)
                    client_offer.save()

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
            data = json.loads(request.body).get('requests', [])
            for req_data in data:
                req = Request.objects.get(id=req_data['id'])
                # Update request fields
                req.quantity = req_data.get('quantity', req.quantity)
                req.specs = req_data.get('specs', req.specs)
                req.size = req_data.get('size', req.size)
                req.payment_terms_requested = req_data.get(
                    'payment_terms_requested', req.payment_terms_requested)
                req.incoterms = req_data.get('incoterms', req.incoterms)
                req.discharge_port = req_data.get(
                    'discharge_port', req.discharge_port)
                req.packaging = req_data.get('packaging', req.packaging)
                req.notes = req_data.get('notes', req.notes)
                req.save()
            return JsonResponse({'status': 'success', 'message': 'Requests updated successfully.'})
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
            # Retrieve the enquiry ID from the data
            enquiry_id = data.get('enquiry_id')
            enquiry = get_object_or_404(Enquiry, pk=enquiry_id)
            print(data.items())
            # Update the fields based on data keys
            for key, value in data.items():
                # Exclude 'enquiry_id' from being treated as a field
                if hasattr(enquiry, key) and key != 'enquiry_id':
                    # Special handling for date fields
                    if 'date' in key and value:
                        try:
                            value = datetime.strptime(value, '%d/%m/%Y').date()

                        except ValueError:
                            return JsonResponse({'error': 'Invalid date format'}, status=400)
                    setattr(enquiry, key, value)
            try:
                enquiry.save()
            except Exception as e:
                print(
                    f"Failed to set attribute {key} to {value} on enquiry: {e}")
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
    enquiries_list = []
    enquiries = Enquiry.objects.prefetch_related(
        'enquiry_requests__product').select_related('client').all()

    for enquiry in enquiries:
        # Fetch manager's name if available
        manager_name = None
        if enquiry.manager:
            try:
                manager = Manager.objects.get(
                    name=enquiry.manager)  # Usinas identifier
                manager_name = manager.name
            except Manager.DoesNotExist:
                manager_name = None

        enquiry_dict = {
            'id': enquiry.id,
            'status': enquiry.status,
            'manager': manager_name,
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

# SUPPLIER PAGE-----------------------------------------------------------------------------------------------------------------------


@login_required
def supplier_list(request):
    return render(request, 'app/supplier_list.html')


@login_required
def suppliers_api(request):
    suppliers = list(Supplier.objects.values(
        'id', 'name', 'contact_person', 'email'))
    return JsonResponse({'suppliers': suppliers}, safe=False)


@login_required
def supplier_detail(request, id):
    supplier = get_object_or_404(Supplier, id=id)
    # Fetch recent offers related to this supplier
    offers = Offer.objects.filter(supplier=supplier).prefetch_related(Prefetch(
        'request', queryset=Request.objects.select_related('product'))).order_by('-validity')[:5]
    product_stats = (
        Offer.objects.filter(supplier=supplier)
        .values('request__product__name')  # Group by product name
        .annotate(
            average_price=Avg('supplier_price'),
            total_offers=Count('id')
        )
    )
    return render(request, 'app/supplier_detail.html', {'supplier': supplier, 'offers': offers, 'product_stats': product_stats})


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
    suppliers = Supplier.objects.filter(id__in=int_supplier_ids)
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

    emails = []
    # Retrieve or create Email objects for each supplier
    for supplier in suppliers:
        email = Email.objects.filter(
            supplier=supplier, request=request_obj).first()
        if not email:
            email = Email.objects.create(
                supplier=supplier, request=request_obj, manager=manager)
            print(
                f"Created new Email instance for supplier {supplier.id}, request {request_obj.id}, and manager {manager.id}")
        emails.append(email)

    # Prepare the context with the email objects and their attachments
    emails_with_attachments = []
    for email in emails:
        attachments = Attachment.objects.filter(email=email)
        emails_with_attachments.append({
            'email': email,
            'attachments': attachments,
        })

    # Prepare the context with the email objects
    context = {
        'emails_with_attachments': emails_with_attachments,
        'enquiry': request_obj.enquiry,
        'request_obj': request_obj,
    }

    return render(request, 'app/draft-email.html', context)


@login_required
def upload_attachment(request):
    if request.method == 'POST' and request.FILES.getlist('files[]'):
        files = request.FILES.getlist('files[]')
        email_ids = request.POST.getlist('email_id')

        if not email_ids:
            return JsonResponse({'success': False, 'error': 'No email IDs provided'})

        for email_id in email_ids:
            try:
                email = Email.objects.get(id=email_id)
            except Email.DoesNotExist:
                return JsonResponse({'success': False, 'error': f'Email with id {email_id} not found'})

            for file in files:
                attachment = Attachment.objects.create(
                    email=email, request=email.request, file=file)
                print(f"Attachment created: {attachment.file.path}")

        return JsonResponse({'success': True})

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
        recipient = request.POST.get('recipient')
        print(recipient)

        # Extract email object from database
        email = get_object_or_404(Email, id=email_id)

        # Process recipient(s)
        recipients = [email.strip()
                      for email in recipient.split(';') if email.strip()]

        # Update email object with new information
        email.subject = subject
        email.message = message
        email.recipient = recipient
        email.save()

        # Get the supplier associated with the email object
        supplier = email.supplier
        stripped_supplier_email = supplier.email.strip() if supplier.email else ""
        stripped_recipient = recipient.strip()

        if supplier and stripped_supplier_email != stripped_recipient:
            supplier.email = stripped_recipient
            supplier.save()

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
        email_payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": message
                },
                "toRecipients": to_recipients,
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
            email.status = 'FAILED'  # Assuming you want to update the status to SENT after sending
            email.save()
            return JsonResponse({'error': 'Failed to send email', 'details': response.json()}, status=response.status_code)
    return JsonResponse({'error': 'Invalid request method'}, status=400)
