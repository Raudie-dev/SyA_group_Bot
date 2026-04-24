from django.db import models
from app1.models import User


class User_admin(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128)
    bloqueado = models.BooleanField(default=False)
    email = models.EmailField(max_length=150, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return self.nombre

class IAAPI(models.Model):
    """Registra las APIs de IA disponibles en la plataforma."""
    NAMES = [
        ('deepseek', 'DeepSeek'),
        ('chatgpt', 'ChatGPT'),
        ('gemini', 'Gemini'),
        ('easybot', 'EasyBot (proxy)')
    ]
    nombre = models.CharField(max_length=30, choices=NAMES, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)
    url = models.CharField(max_length=200, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return dict(self.NAMES).get(self.nombre, self.nombre)

class UserIAAccess(models.Model):
    """Controla a qué APIs de IA tiene acceso cada usuario."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ia_access')
    api = models.ForeignKey(IAAPI, on_delete=models.CASCADE, related_name='user_access')
    enabled = models.BooleanField(default=True)
    # Si la API requiere una key personalizada para el usuario
    user_api_key = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        unique_together = ('user', 'api')

    def __str__(self):
        return f"{self.user.nombre} - {self.api.nombre} ({'on' if self.enabled else 'off'})"