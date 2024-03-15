from django.shortcuts import render, redirect
from django.db.models.functions import Greatest
from django.views.generic import TemplateView

from django.utils import timezone
from django.views.generic import TemplateView

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
load_dotenv()  # Load the .env file

gpt4_api_key = os.getenv('OPEN_AI')


def index(request):
    return render(request, 'app/empty.html')

def forms(request):
    return render(request, 'app/forms.html')

@csrf_exempt
def create_enquiry_ajax(request):
    if request.method == 'POST':
        # Decode the JSON payload
        data = json.loads(request.body)
        print(data)

        # Here, you would process the data to create or update your models.
        # For example, creating an enquiry, requests, etc.
        # Make sure to implement your logic for handling the data.
        
        # Once processing is complete, return a JsonResponse indicating success
        return JsonResponse({'success': True, 'message': 'Enquiry and related data successfully processed.'})

    # If the request method is not POST or if we're not returning within the POST block above,
    # it's a good practice to return a response indicating the request method is not allowed.
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
