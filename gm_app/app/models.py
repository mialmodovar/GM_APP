from django.db import models

class Manager(models.Model):
    name = models.TextField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)

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
    price_offered = models.TextField(blank=True, null=True)
    payment_term_offered = models.TextField(blank=True, null=True)
    validity_offered = models.TextField(blank=True, null=True)
    offer_selected = models.ForeignKey('Offer', related_name='enquiry_requests', on_delete=models.SET_NULL, null=True, blank=True)
    customer_feedback = models.TextField(blank=True, null=True)
    
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


