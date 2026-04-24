from django.core.management.base import BaseCommand
from app2.models import IAAPI

class Command(BaseCommand):
    help = 'Crea las APIs de IA por defecto (DeepSeek, ChatGPT, Gemini, EasyBot) si no existen.'

    def handle(self, *args, **kwargs):
        defaults = [
            ('deepseek', 'DeepSeek', 'https://api.deepseek.com/v1/chat/completions'),
            ('chatgpt', 'ChatGPT', 'https://api.openai.com/v1/chat/completions'),
            ('gemini', 'Gemini', 'https://generativelanguage.googleapis.com/v1beta/models'),
            ('easybot', 'EasyBot (proxy)', ''),
        ]
        for nombre, desc, url in defaults:
            obj, created = IAAPI.objects.get_or_create(nombre=nombre, defaults={'descripcion': desc, 'url': url})
            if created:
                self.stdout.write(self.style.SUCCESS(f'API {nombre} creada'))
            else:
                self.stdout.write(f'API {nombre} ya existe')
