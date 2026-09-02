from django.contrib import admin
from .models import CTe, Manifest, DeliveryMovement, DeliveryOccurrence
admin.site.register([CTe, Manifest, DeliveryMovement, DeliveryOccurrence])
