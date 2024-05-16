from django.db import models
from django.contrib.auth.models import User
import uuid
from django.core.files.storage import FileSystemStorage


    
   
class Manager(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE,default=1)
    name = models.TextField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)
    division = models.TextField(blank=True, null=True)
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    expiry_token = models.DateTimeField(blank=True, null=True)



class Enquiry(models.Model):
    manager = models.ForeignKey(Manager, on_delete=models.SET_NULL, null=True, blank=True)
    client = models.ForeignKey('Client', on_delete=models.SET_NULL, null=True, blank=True)
    received_date = models.DateField(blank=True, null=True)
    submission_deadline = models.DateField(blank=True, null=True)
    submission_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=100, choices=[
        ('ACTIVE', 'Active'),
        ('CLOSED', 'Closed'),
        ('ORDER', 'Order'),
    ], blank=True, null=True)

class Product(models.Model):
    name = models.TextField(blank=True, null=True)
    specifications = models.TextField(blank=True, null=True)

class Supplier(models.Model):
    name = models.TextField(blank=True, null=True)
    country = models.TextField(blank=True, null=True)
    contact_person = models.TextField(blank=True, null=True)
    email = models.TextField(blank=True, null=True)

    
class Client(models.Model):
    name = models.TextField(blank=True, null=True)
    country = models.TextField(blank=True, null=True)
    person = models.TextField(blank=True, null=True)

class Request(models.Model):
    enquiry = models.ForeignKey('Enquiry', related_name='enquiry_requests', on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    specs = models.TextField(blank=True, null=True)
    size = models.TextField(blank=True, null=True)
    quantity = models.TextField(blank=True, null=True)
    incoterms = models.TextField(blank=True, null=True)
    packaging = models.TextField(blank=True, null=True)
    discharge_port = models.TextField(blank=True, null=True)
    payment_terms_requested = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

class Offer(models.Model):
    request = models.ForeignKey(Request, related_name='offers', on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    supplier_price = models.TextField(blank=True, null=True)
    incoterms = models.TextField(blank=True, null=True)
    specs = models.TextField(blank=True, null=True)  
    size = models.TextField(blank=True, null=True)
    packaging = models.TextField(blank=True, null=True)
    payment_terms = models.TextField(blank=True, null=True)
    validity = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

class Offer_Client(models.Model):
    request = models.ForeignKey('Request', related_name='offers_client', on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    price_offered = models.TextField(blank=True, null=True)
    payment_term_offered = models.TextField(blank=True, null=True)
    validity_offered = models.TextField(blank=True, null=True)
    customer_feedback = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

class Division(models.Model):
    name = models.TextField(blank=True, null=True)

class Email(models.Model):
    # A unique identifier for each email, using UUID
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # Foreign key linking to the Manager model
    manager = models.ForeignKey(Manager, on_delete=models.CASCADE)
    request = models.ForeignKey(Request, on_delete=models.CASCADE)
    # Foreign key linking to the Supplier model since emails are sent to suppliers
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True,related_name='emails')
    subject = models.TextField()
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    # You might want to store whether the email was successfully sent or not
    status = models.CharField(max_length=10, choices=[
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('DRAFT', 'Draft')
    ], default='Draft')
    # Optional: Track responses or follow-up emails
    response_received = models.BooleanField(default=False)
    response_details = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Email from {self.manager.name} to {self.supplier.name} on {self.sent_at.strftime('%Y-%m-%d %H:%M')}"

class Attachment(models.Model):
    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name='attachments')
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='request')
    file = models.FileField(upload_to='email_attachments/%Y/%m/%d/', storage=FileSystemStorage(location='/media/email_attachments'))
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.email.subject} uploaded on {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"