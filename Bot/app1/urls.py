from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('enviar-reclamo/', views.enviar_reclamo, name='enviar_reclamo'),
    path('login/', views.login, name='login'),
    path('estado/', views.estado, name='estado'),
    path('qr-json/', views.qr_json, name='qr_json'),
    path('webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('chat/', views.public_chat, name='public_chat'),
    path('send/', views.send_message, name='send_message'),
    path('logout/', views.logout, name='logout'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('configuracion/whatsapp/', views.whatsapp_configuracion, name='whatsapp_configuracion'),
    path('configuracion/crear/', views.create_edit_bot, name='create_bot'),
    path('configuracion/editar/<int:bot_id>/', views.create_edit_bot, name='edit_bot'),
    path('configuracion/eliminar/<int:bot_id>/', views.delete_bot, name='delete_bot'),
    path('agentes/', views.agentes, name='agentes'),
    path('agentes/crear/', views.agente_crear, name='agente_crear'),
    path('agentes/editar/<int:agente_id>/', views.agente_editar, name='agente_editar'),
    path('agentes/eliminar/<int:agente_id>/', views.agente_eliminar, name='agente_eliminar'),
    path('departamentos/', views.departamentos, name='departamentos'),
    path('departamentos/crear/', views.departamento_crear, name='departamento_crear'),
    path('departamentos/editar/<int:dpto_id>/', views.departamento_editar, name='departamento_editar'),
    path('departamentos/eliminar/<int:dpto_id>/', views.departamento_eliminar, name='departamento_eliminar'),
    path('reset-chat/', views.reset_chat, name='reset_chat'),
    path('queue/drain/', views.queue_drain, name='queue_drain'),
    path('queue/status/', views.queue_status, name='queue_status'),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)