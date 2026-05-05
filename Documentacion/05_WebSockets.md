# 05 — WebSockets

## Rol del WebSocket en el sistema

El WebSocket tiene una responsabilidad única y acotada: **entregar al agente humano el contexto de la conversación en tiempo real**, en el momento en que le es asignado un cliente. No maneja lógica de negocio, no toma decisiones de asignación, y no accede directamente a la base de datos.

Esto mantiene el WebSocket como una capa de transporte pura, fácil de reemplazar o escalar de forma independiente.

---

## Estado actual

El proyecto actualmente **no tiene WebSocket implementado**. La comunicación en tiempo real entre Django y el frontend del agente es la funcionalidad a construir. Esta sección documenta el diseño propuesto.

---

## Opciones de implementación

### Opción A: Django Channels (recomendada)
Integra WebSocket nativo en Django usando `channels` y un backend Redis. Mantiene todo el stack en Python y reutiliza la autenticación de Django.

Dependencias:
```
channels==4.x
channels-redis==4.x
daphne==4.x         # servidor ASGI
redis               # broker de mensajes
```

### Opción B: Servidor WebSocket separado en Node.js
Aprovechar que el gateway ya corre en Node.js y agregar soporte `ws` o `socket.io`. Django notifica al servidor Node mediante HTTP interno; Node retransmite a los agentes conectados.

Dependencias: `ws` o `socket.io` en el gateway existente.

**Elección recomendada**: Opción A (Django Channels) para mantener la autenticación y la lógica centralizada en el backend Python.

---

## Configuración con Django Channels

### Instalación
```bash
pip install channels channels-redis daphne
```

### `proyecto/settings.py`
```python
INSTALLED_APPS = [
    ...
    'channels',
]

ASGI_APPLICATION = 'proyecto.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    },
}
```

### `proyecto/asgi.py`
```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from app1.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

### `app1/routing.py`
```python
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/agente/(?P<agente_id>\d+)/$', consumers.AgenteConsumer.as_asgi()),
]
```

### `app1/consumers.py`
```python
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AgenteConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.agente_id = self.scope['url_route']['kwargs']['agente_id']
        self.group_name = f'agente_{self.agente_id}'

        # Unirse al grupo del agente
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # El agente no envía datos por WS en este flujo; solo recibe
        pass

    # Handler para mensajes enviados al grupo desde Django
    async def nuevo_chat(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'nuevo_chat',
            'payload': event['payload']
        }))
```

---

## Flujo de eventos

### 1. Agente abre la bandeja de trabajo
```
Navegador del agente
    │  GET /agente/bandeja/
    ▼
Django sirve la página HTML con JS del cliente WS

Navegador establece WebSocket:
    ws://localhost:8000/ws/agente/{agente_id}/
    │
    ▼
AgenteConsumer.connect()
  - Agente unido al grupo 'agente_{id}'
  - Conexión abierta, esperando eventos
```

### 2. Bot transfiere un caso al agente
```
Django (whatsapp_webhook o servicio de asignación)
    │
    │  Después de asignar_agente():
    ▼
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()
async_to_sync(channel_layer.group_send)(
    f'agente_{agente.id}',
    {
        'type': 'nuevo_chat',
        'payload': {
            'chat_id': chat.id,
            'remote_jid': chat.remote_jid,
            'nombre_cliente': contexto.get('nombre_cliente'),
            'necesidad': contexto.get('necesidad'),
            'urgencia': contexto.get('urgencia'),
            'resumen': contexto.get('resumen'),
            'session': f'{bot.owner_id}:{slot}'
        }
    }
)
    │
    ▼
AgenteConsumer.nuevo_chat() recibe el evento
    │
    ▼
WebSocket envía JSON al navegador del agente
    │
    ▼
Frontend muestra notificación: "Nuevo cliente asignado"
```

### 3. Mensaje nuevo del cliente (mientras el agente atiende)
Cuando el cliente envía un mensaje mientras un agente lo está atendiendo, el gateway lo recibe, Django lo registra, y se puede emitir un evento WS al agente para que el mensaje aparezca en tiempo real en su bandeja.

```python
# En whatsapp_webhook(), después de guardar el mensaje:
if chat_asignado:
    async_to_sync(channel_layer.group_send)(
        f'agente_{chat_asignado.agente_id}',
        {
            'type': 'nuevo_mensaje',
            'payload': {
                'chat_id': chat_asignado.id,
                'remote_jid': remoteJid,
                'texto': messageText,
                'timestamp': str(now())
            }
        }
    )
```

---

## Formato de mensajes WS (cliente ↔ servidor)

### Servidor → Cliente (agente)

**Nuevo chat asignado:**
```json
{
  "tipo": "nuevo_chat",
  "payload": {
    "chat_id": 42,
    "remote_jid": "573001234567@s.whatsapp.net",
    "nombre_cliente": "Carlos Rodríguez",
    "necesidad": "Quiere arrendar un apartamento de 2 habitaciones",
    "urgencia": "alta",
    "resumen": "El cliente lleva 3 meses buscando, tiene presupuesto definido y necesita mudarse antes del 1 de junio.",
    "session": "1:0"
  }
}
```

**Nuevo mensaje del cliente:**
```json
{
  "tipo": "nuevo_mensaje",
  "payload": {
    "chat_id": 42,
    "remote_jid": "573001234567@s.whatsapp.net",
    "texto": "¿Tienen algo disponible en el norte de la ciudad?",
    "timestamp": "2025-06-01T14:23:00Z"
  }
}
```

**Actualización de estado del agente:**
```json
{
  "tipo": "estado_agente",
  "payload": {
    "disponible": false,
    "razon": "En reunión"
  }
}
```

---

## Buenas prácticas

### Separación de responsabilidades
El consumer WebSocket solo recibe y retransmite eventos. Nunca hace consultas a la base de datos ni llama a servicios externos. Toda la lógica de negocio se ejecuta antes de llamar a `group_send`.

### Autenticación
Usar `AuthMiddlewareStack` de Channels para validar que la conexión WS proviene de un agente autenticado. Rechazar conexiones sin sesión válida en `connect()`.

```python
async def connect(self):
    user = self.scope['user']
    if not user.is_authenticated:
        await self.close()
        return
    ...
```

### Reconexión automática en el cliente
El cliente JavaScript debe intentar reconectarse automáticamente si la conexión se pierde:

```javascript
function conectarWS(agenteId) {
    const ws = new WebSocket(`ws://${location.host}/ws/agente/${agenteId}/`);

    ws.onclose = () => {
        setTimeout(() => conectarWS(agenteId), 3000); // reconecta en 3s
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        manejarEvento(data);
    };
}
```

### Grupos por agente, no por bot
Cada agente tiene su propio grupo de Channel Layer (`agente_{id}`). Esto permite que el mismo agente pueda atender bots de diferentes clientes de la plataforma sin confundir los eventos.

### Escalabilidad
Con Redis como backend de Channel Layer, múltiples instancias del servidor Django pueden compartir los grupos y los eventos se enrutarán correctamente sin importar en qué instancia está el consumer conectado.
