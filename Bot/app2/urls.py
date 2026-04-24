from django.urls import path
from . import views

urlpatterns = [
    path('login_admin/', views.login_admin, name='login_admin'),
    path('usuarios/', views.usuarios_control, name='usuarios_control'),
    path('usuarios/crear/', views.usuarios_edit_create, name='usuarios_create'),
    path('usuarios/editar/<int:user_id>/', views.usuarios_edit_create, name='usuarios_edit'),
    path('iaapi/', views.iaapi_control, name='iaapi_control'),
]