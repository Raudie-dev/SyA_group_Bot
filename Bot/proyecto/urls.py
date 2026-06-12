from django.contrib import admin
from django.urls import path, include
from app1 import views as app1_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app1.urls')),
    path('api/whatsapp/webhook/', app1_views.whatsapp_webhook, name='api_whatsapp_webhook'),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)