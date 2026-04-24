from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
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
]