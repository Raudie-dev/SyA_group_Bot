# 06 — Modelo de Datos

## Base de datos actual

**Motor**: SQLite (`Bot/db.sqlite3`)
**ORM**: Django ORM
**Migraciones**: 7 en `app1`, 6 en `app2`

Para producción con múltiples agentes concurrentes se recomienda migrar a **PostgreSQL**, que soporta escrituras concurrentes reales y permite usar `SELECT FOR UPDATE` para operaciones de asignación atómica.

---

## Diagrama de relaciones (ER simplificado)

```
User ──────────────────────────── UserIAAccess ──── IAAPI
 │  (1:N)                            (N:1)          (1:N)
 │
 └─── ConfigBot (1:N)
           │
           ├─── WhatsAppSession (1:1)
           │
           ├─── WhatsAppMessage (1:N)
           │
           └─── ContextFile (1:N)


User_admin    (tabla separada, sólo para administradores de plataforma)
```

---

## Tablas actuales

### `app1_user` — Usuarios de la plataforma

| Campo | Tipo | Restricciones | Descripción |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | Identificador |
| nombre | VARCHAR(150) | UNIQUE, NOT NULL | Nombre de usuario |
| password | VARCHAR(128) | NOT NULL | Contraseña (actualmente en texto plano) |
| bloqueado | BOOLEAN | DEFAULT False | Cuenta bloqueada |
| email | VARCHAR(254) | UNIQUE, NULL | Correo electrónico |
| telefono | VARCHAR(20) | NULL | Teléfono de contacto |
| plan | VARCHAR(20) | DEFAULT 'base' | Plan: base / especial / premium |

### `app1_configbot` — Configuración de bots

| Campo | Tipo | Restricciones | Descripción |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | Identificador |
| nombre | VARCHAR(100) | NOT NULL | Nombre descriptivo del bot |
| owner_id | INTEGER | FK → app1_user, NULL | Usuario propietario |
| mensaje_bienvenida | VARCHAR(500) | NOT NULL | Texto inicial para el prompt |
| instrucciones_ia | TEXT | NOT NULL | System prompt completo de la IA |
| api_key | VARCHAR(200) | NULL | API key de DeepSeek del usuario |

### `app1_whatsappsession` — Sesiones de WhatsApp

| Campo | Tipo | Restricciones | Descripción |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | Identificador |
| bot_id | INTEGER | FK → app1_configbot | Bot asociado |
| qr_string | TEXT | NULL | Último QR generado (string base64) |
| updated_at | DATETIME | auto_now | Última actualización |

### `app1_whatsappmessage` — Mensajes de WhatsApp

| Campo | Tipo | Restricciones | Descripción |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | Identificador |
| bot_id | INTEGER | FK → app1_configbot | Bot que recibió el mensaje |
| remote_jid | VARCHAR(100) | NOT NULL | ID del remitente (ej: 573001234567@s.whatsapp.net) |
| push_name | VARCHAR(100) | NULL | Nombre display del remitente en WhatsApp |
| message_text | TEXT | NULL | Texto del mensaje recibido |
| received_at | DATETIME | auto_now_add | Momento de recepción |
| replied | BOOLEAN | DEFAULT False | ¿Se respondió? |
| reply_text | TEXT | NULL | Texto de la respuesta enviada |
| replied_at | DATETIME | NULL | Momento de respuesta |

### `app1_contextfile` — Archivos de contexto del bot

| Campo | Tipo | Restricciones | Descripción |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | Identificador |
| bot_id | INTEGER | FK → app1_configbot | Bot al que pertenece |
| file | VARCHAR(100) | NOT NULL | Ruta del archivo (media/context_files/) |
| uploaded_at | DATETIME | auto_now_add | Fecha de carga |

Formatos soportados: PDF, DOCX, XLSX

### `app2_user_admin` — Administradores de la plataforma

| Campo | Tipo | Restricciones | Descripción |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | Identificador |
| nombre | VARCHAR(150) | UNIQUE, NOT NULL | Nombre de admin |
| password | VARCHAR(128) | NOT NULL | Contraseña |
| bloqueado | BOOLEAN | DEFAULT False | Cuenta bloqueada |
| email | VARCHAR(254) | UNIQUE, NULL | Correo |
| telefono | VARCHAR(20) | NULL | Teléfono |

### `app2_iaapi` — APIs de inteligencia artificial disponibles

| Campo | Tipo | Restricciones | Descripción |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | Identificador |
| nombre | VARCHAR(50) | UNIQUE, choices | Identificador: deepseek / chatgpt / gemini / easybot |
| descripcion | VARCHAR(200) | NULL | Descripción legible |
| url | VARCHAR(500) | NULL | Endpoint de la API |
| activo | BOOLEAN | DEFAULT True | ¿Disponible para nuevos usuarios? |

### `app2_useriaaccess` — Acceso de usuarios a APIs de IA

| Campo | Tipo | Restricciones | Descripción |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | Identificador |
| user_id | INTEGER | FK → app1_user | Usuario |
| api_id | INTEGER | FK → app2_iaapi | API habilitada |
| enabled | BOOLEAN | DEFAULT True | Acceso activo |
| user_api_key | VARCHAR(300) | NULL | API key personal del usuario para esa IA |

Restricción: `UNIQUE (user_id, api_id)`

---

## Tablas propuestas (pendientes de implementar)

### `app1_agente` — Agentes humanos

| Campo | Tipo | Restricciones | Descripción |
|---|---|---|---|
| id | INTEGER | PK | Identificador |
| user_id | INTEGER | FK → app1_user | Empresa a la que pertenece |
| nombre | VARCHAR(100) | NOT NULL | Nombre del agente |
| disponible | BOOLEAN | DEFAULT True | Disponibilidad manual |
| max_chats | INTEGER | DEFAULT 5 | Máximo de chats simultáneos |
| especialidad | VARCHAR(50) | NULL | Área: ventas, soporte, etc. |
| activo | BOOLEAN | DEFAULT True | Habilitado en el sistema |

### `app1_chatasignado` — Chats asignados a agentes

| Campo | Tipo | Restricciones | Descripción |
|---|---|---|---|
| id | INTEGER | PK | Identificador |
| agente_id | INTEGER | FK → app1_agente | Agente asignado |
| bot_id | INTEGER | FK → app1_configbot | Bot de la conversación |
| remote_jid | VARCHAR(100) | NOT NULL | Número del cliente |
| estado | VARCHAR(20) | choices | pendiente / activo / cerrado |
| contexto_json | TEXT | NULL | Resumen de la IA en JSON |
| transferido | BOOLEAN | DEFAULT False | Bot dejó de responder |
| asignado_at | DATETIME | auto_now_add | Momento de asignación |
| cerrado_at | DATETIME | NULL | Momento de cierre |

---

## Índices recomendados

```sql
-- Búsqueda de mensajes de un número en un bot
CREATE INDEX idx_mensaje_jid_bot ON app1_whatsappmessage (remote_jid, bot_id);

-- Búsqueda de chats activos por agente
CREATE INDEX idx_chat_agente_estado ON app1_chatasignado (agente_id, estado);

-- Búsqueda de sesión por bot
CREATE INDEX idx_session_bot ON app1_whatsappsession (bot_id);
```

---

## Ejemplo de consulta: cargar historial de conversación

```python
# Obtener los últimos 20 mensajes de un cliente en un bot
historial = WhatsAppMessage.objects.filter(
    bot=config,
    remote_jid="573001234567@s.whatsapp.net"
).order_by('-received_at')[:20].values(
    'message_text', 'reply_text', 'received_at'
)
```

## Ejemplo de consulta: agentes disponibles ordenados por carga

```python
from django.db.models import Count, Q

agentes = Agente.objects.filter(
    user=bot.owner,
    disponible=True,
    activo=True
).annotate(
    chats_activos=Count(
        'chatasignado',
        filter=Q(chatasignado__estado='activo')
    )
).order_by('chats_activos')
```

---

## Notas sobre seguridad

- Las contraseñas se almacenan actualmente en texto plano. Se debe migrar a `make_password` / `check_password` de Django o usar el sistema de auth nativo (`AbstractBaseUser`).
- Las API keys de usuarios se guardan en texto plano en la base de datos. En producción, cifrar con `django-encrypted-fields` o similar.
- El archivo `api.txt` en la raíz del proyecto contiene una API key activa y no debe estar en el repositorio.
