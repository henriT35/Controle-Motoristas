from django.contrib import admin
from .models import ImportRun, ImportStep
admin.site.register([ImportRun, ImportStep])
