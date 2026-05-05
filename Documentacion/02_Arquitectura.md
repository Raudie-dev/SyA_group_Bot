# 02 — Arquitectura del Sistema

## Visión general

El sistema sigue una arquitectura de **microservicios acoplados**: el gateway de WhatsApp (Node.js) y el backend de negocio (Django) son procesos separados que se comunican mediante HTTP. Esto permite escalar o reemplazar el componente de WhatsApp sin tocar la lógica de negocio.

---

## Diagrama de componentes

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENTE FINAL                                │
│                    (WhatsApp en el celular)                         │
└─────────────────────────┬───────────────────────────────────────────┘
                          │  Red WhatsApp (protocolo Baileys)
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  WHATSAPP GATEWAY (Node.js)                         │
│                       Puerto 3000                                   │
│                                                                     │
│  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────┐  │
│  │  Baileys Socket │   │  Express HTTP API│   │  Auth sessions  │  │
│  │  (por sesión)   │   │  /qr /send /status│  │  ./auth_info/   │  │
│  └────────┬────────┘   └──────────────────┘   └─────────────────┘  │
│           │ POST webhook                                            │
└───────────┼─────────────────────────────────────────────────────────┘
            │
            │  HTTP POST /api/whatsapp/webhook/
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DJANGO BACKEND (Python)                          │
│                       Puerto 8000                                   │
│                                                                     │
│  ┌───────────┐   ┌──────────────┐   ┌───────────────────────────┐  │
│  │   app1    │   │    app2      │   │      proyecto/            │  │
│  │ Control   │   │  Admin + IA  │   │  settings, urls, wsgi     │  │
│  │ de bots   │   │  APIs mgmt   │   │                           │  │
│  └─────┬─────┘   └──────────────┘   └───────────────────────────┘  │
│        │                                                            │
│  ┌─────▼─────────────────────────────────────────────────────────┐  │
│  │                   SQLite Database                             │  │
│  │   User │ ConfigBot │ WhatsAppSession │ WhatsAppMessage │ ...  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │  HTTPS / API Key
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  DEEPSEEK API (servicio externo)                    │
│            https://api.deepseek.com/v1/chat/completions             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Componentes en detalle

### 1. WhatsApp Gateway (`whatsapp-gateway/index.js`)

Responsabilidades:
- Mantener conexiones WebSocket con los servidores de WhatsApp mediante Baileys
- Gestionar múltiples sesiones simultáneas identificadas por `{user_id}:{slot}`
- Recibir mensajes entrantes y enviarlos al webhook de Django
- Recibir la respuesta de Django y enviarla al cliente de WhatsApp
- Exponer una API HTTP para operaciones de gestión (QR, estado, envío manual, desvinculación)
- Persistir credenciales de sesión en disco (`./auth_info/{user}:{slot}/`)

Tecnologías: Node.js, Express 4, @whiskeysockets/baileys, axios

### 2. Backend Django (`Bot/`)

Responsabilidades:
- Autenticación y gestión de usuarios de la plataforma
- CRUD de configuraciones de bot (`ConfigBot`)
- Procesamiento del webhook de WhatsApp: identificar bot, llamar IA, registrar mensaje
- Panel de administración de usuarios y APIs de IA
- Gestión de archivos de contexto (PDF, Word, Excel)
- Servir la interfaz web del panel de control

Estructura interna:
- `app1/`: Todo lo relacionado con usuarios regulares y bots (vistas, modelos, templates)
- `app2/`: Panel de administración de la plataforma y gestión de APIs de IA
- `proyecto/`: Settings, URLs raíz, configuración WSGI/ASGI

### 3. Base de Datos (SQLite)

Archivo: `Bot/db.sqlite3`

Actúa como única fuente de verdad para el estado del sistema. En producción se recomienda migrar a PostgreSQL para soportar concurrencia real de escritura.

### 4. DeepSeek API (Servicio externo)

Llamado sincrónicamente desde el webhook de Django. Recibe el prompt del sistema (instrucciones del bot) y el mensaje del usuario, y devuelve la respuesta del bot.

Modelo utilizado: `deepseek-chat`

---

## Flujo de datos detallado

### Mensaje entrante (cliente → bot)

```
1. Cliente envía mensaje en WhatsApp
2. Baileys entrega el mensaje al handler messages.upsert
3. Gateway extrae el texto con extractMessageText()
4. Gateway hace POST a Django: { remoteJid, pushName, messageText, session, owner }
5. Django identifica el ConfigBot asociado a la sesión
6. Django guarda el mensaje en WhatsAppMessage
7. Django construye el prompt (instrucciones + mensaje_bienvenida + mensaje_usuario)
8. Django llama a DeepSeek API con el prompt
9. Django recibe la respuesta de IA
10. Django guarda la respuesta en WhatsAppMessage.reply_text
11. Django responde al Gateway: { remoteJid, reply }
12. Gateway envía el reply al cliente WhatsApp
```

### Vinculación de número (QR Flow)

```
1. Usuario accede a /configuracion/whatsapp/ en el panel
2. Panel hace GET /qr?user=<id>&slot=<id> al Gateway
3. Gateway inicia startSocketFor() si no hay sesión activa
4. Baileys genera el QR → Gateway lo almacena en memoria
5. Panel recibe el QR string y lo renderiza como imagen
6. Usuario escanea el QR con su WhatsApp
7. Baileys emite evento 'open' → sesión marcada como 'connected'
8. Credenciales se persisten en ./auth_info/{user}:{slot}/
```

---

## Separación de responsabilidades

| Capa | Hace | No hace |
|---|---|---|
| Gateway Node.js | Mantener sesión WhatsApp, routing de mensajes | Lógica de negocio, acceso a BD |
| Django / app1 | Lógica del bot, IA, BD | Comunicación directa con WhatsApp |
| Django / app2 | Administración de plataforma | Lógica de bot o sesiones |
| DeepSeek API | Generación de respuestas IA | Contexto de negocio (lo recibe como prompt) |

---

## Consideraciones de escalabilidad

- El gateway actual es un proceso único Node.js. Para escalar horizontalmente, cada instancia necesitaría un registro compartido de sesiones (Redis) y un balanceador.
- SQLite limita la escritura concurrente. Para producción con múltiples agentes simultáneos, migrar a PostgreSQL.
- Las llamadas a DeepSeek son síncronas y bloquean el webhook. Implementar una cola de tareas (Celery + Redis) desacoplaría el procesamiento de mensajes y evitaría timeouts bajo carga.
- Los archivos de sesión de Baileys se guardan en disco local. En entornos en contenedores, usar un volumen persistente o almacenamiento externo (S3, Redis).
