from django.urls import path
from . import views
urlpatterns=[path("",views.index,name="reports"),path("<str:kind>/",views.preview,name="report_preview"),path("<str:kind>/excel/",views.excel,name="report_excel"),path("<str:kind>/pdf/",views.pdf,name="report_pdf")]
