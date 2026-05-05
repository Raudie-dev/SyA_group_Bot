# 07 — API Reference

## Convenciones

- Base URL Django: `http://localhost:8000`
- Base URL Gateway: `http://localhost:3000`
- Autenticación: sesión Django (cookie) para endpoints del panel. Los endpoints del gateway son internos (red local).
- Formato: JSON en request y response donde aplica.
- Errores: HTTP 400 para datos inválidos, 404 para recurso no encontrado, 500 para error interno.

---

## Gateway Node.js (puerto 3000)

### GET `/qr`
Obtiene el QR actual de una sesión o su estado de conexión.

**Query params:**
| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| user | string | Sí | ID del usuario propietario |
| slot | string | Sí | Número de slot del bot (0, 1, 2...) |

**Response 200 — QR disponible:**
```json
{
  "status": "qr",
  "qr": "2@abc123xyz...=="
}
```

**Response 200 — Sesión conectada:**
```json
{
  "status": "connected"
}
```

**Response 200 — Sin sesión activa:**
```json
{
  "status": "not_started"
}
```

---

### POST `/generate`
Inicia o reinicia una sesión de WhatsApp. Genera un nuevo QR.

**Query params:** igual que `/qr` (user, slot)

**Response 200:**
```json
{
  "status": "generating",
  "message": "Socket iniciado. Espere el QR."
}
```

---

### POST `/unlink`
Cierra y desvincula una sesión de WhatsApp (logout).

**Query params:** igual que `/qr` (user, slot)

**Response 200:**
```json
{
  "status": "unlinked",
  "message": "Sesión cerrada correctamente."
}
```

---

### POST `/send`
Envía un mensaje de WhatsApp manualmente (útil para que los agentes humanos respondan).

**Body (JSON):**
```json
{
  "number": "573001234567",
  "message": "Texto del mensaje a enviar",
  "user": "1",
  "slot": "0"
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| number | string | Sí | Número destino (sin @, solo dígitos) |
| message | string | Sí | Texto a enviar |
| user | string | No | ID del usuario (si se omite, usa sesión por defecto) |
| slot | string | No | Slot del bot |

**Response 200:**
```json
{
  "status": "sent",
  "to": "573001234567@s.whatsapp.net"
}
```

**Response 400:**
```json
{
  "error": "No hay sesión activa para este usuario/slot"
}
```

---

### GET `/status`
Retorna el estado de conexión de una sesión.

**Query params:** igual que `/qr` (user, slot)

**Response 200:**
```json
{
  "session": "1:0",
  "status": "connected"
}
```

Valores posibles de `status`: `connected`, `qr`, `reconnecting`, `unlinked`, `not_started`

---

## Webhook interno (Gateway → Django)

### POST `/api/whatsapp/webhook/`
Llamado por el gateway cada vez que llega un mensaje de un cliente. Django procesa la IA y responde.

**Body (JSON) — enviado por el gateway:**
```json
{
  "remoteJid": "573001234567@s.whatsapp.net",
  "pushName": "Carlos Rodríguez",
  "messageText": "Hola, quiero información sobre propiedades",
  "session": "1:0",
  "owner": "1"
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| remoteJid | string | JID completo del remitente en WhatsApp |
| pushName | string | Nombre de perfil del remitente |
| messageText | string | Texto del mensaje |
| session | string | Identificador de sesión: `{user_id}:{slot}` |
| owner | string | ID del usuario propietario de la sesión |

**Response 200:**
```json
{
  "remoteJid": "573001234567@s.whatsapp.net",
  "reply": "¡Hola Carlos! Con gusto te ayudo. ¿Estás buscando para arrendar o comprar?"
}
```

**Response 200 — Sin bot configurado:**
```json
{
  "remoteJid": "573001234567@s.whatsapp.net",
  "reply": ""
}
```

---

## Endpoints del panel web Django

### Autenticación

#### POST `/login/`
**Body (form-data):**
```
nombre=usuario1&password=mi_password
```

**Response:** Redirect a `/estado/` si exitoso. Misma página con error si falla.

#### GET `/logout/`
Cierra la sesión activa. Redirect a `/login/`.

---

### Panel de usuario

#### GET `/estado/`
Dashboard principal. Muestra bots del usuario y su estado de conexión.

#### GET `/configuracion/`
Lista todos los bots del usuario autenticado con opciones de edición.

#### GET/POST `/configuracion/crear/`
Crea un nuevo bot.

**POST body (form-data):**
```
nombre=Mi Bot&mensaje_bienvenida=Hola...&instrucciones_ia=Eres un...&api_key=sk-xxx
```

**Reglas de negocio:**
- Plan `base`: máximo 1 bot
- Plan `especial`: máximo 3 bots
- Plan `premium`: sin límite
- Si se supera el límite, retorna error HTTP 403.

#### GET/POST `/configuracion/editar/<id>/`
Edita un bot existente. Misma estructura que crear.

#### POST `/configuracion/eliminar/<id>/`
Elimina un bot y sus archivos de contexto asociados.

#### GET `/configuracion/whatsapp/`
Página de vinculación de WhatsApp. Muestra el QR para escanear. Hace polling al gateway vía JavaScript.

---

### QR y estado de WhatsApp

#### GET `/qr-json/`
Retorna el QR actual del bot activo del usuario.

**Response 200:**
```json
{
  "qr": "2@abc123...",
  "status": "qr"
}
```

---

### Chat público

#### POST `/chat/`
Endpoint de demostración: envía un mensaje al bot público (sin owner) y retorna la respuesta de IA.

**Body (JSON o form):**
```json
{
  "message": "¿Cuáles son sus horarios de atención?"
}
```

**Response 200:**
```json
{
  "ok": true,
  "reply": "Nuestro horario de atención es de lunes a viernes de 8am a 6pm."
}
```

**Response 400:**
```json
{
  "ok": false,
  "error": "No hay bot configurado"
}
```

---

### Envío manual de mensaje WhatsApp

#### POST `/send/`
Permite al usuario enviar un mensaje directamente a un número desde el panel.

**Body (JSON):**
```json
{
  "number": "573001234567",
  "message": "Mensaje del agente"
}
```

**Response 200:**
```json
{
  "status": "sent"
}
```

---

## Endpoints de administración (app2)

#### POST `/app2/login_admin/`
Login del administrador de plataforma.

#### GET `/app2/usuarios/`
Lista todos los usuarios de la plataforma con opciones de bloqueo/eliminación.

#### GET/POST `/app2/usuarios/crear/`
Crea un nuevo usuario de la plataforma.

**Body (form-data):**
```
nombre=empresa1&password=pass&email=empresa@mail.com&telefono=57300...&plan=especial
```

#### GET/POST `/app2/usuarios/editar/<id>/`
Edita datos o plan de un usuario existente.

#### GET/POST `/app2/iaapi/`
Gestiona las APIs de IA disponibles: activa/desactiva APIs, asigna acceso a usuarios, configura URLs.

---

## Endpoints propuestos (por implementar)

### POST `/api/asignar-chat/`
Asigna un chat a un agente humano.
Ver detalles en [04_Asignacion_Agentes.md](04_Asignacion_Agentes.md).

### GET `/api/agentes/`
Lista agentes disponibles de un usuario/bot.

**Response 200:**
```json
{
  "agentes": [
    { "id": 1, "nombre": "María López", "disponible": true, "chats_activos": 2, "max_chats": 5 },
    { "id": 2, "nombre": "Pedro Gómez", "disponible": true, "chats_activos": 4, "max_chats": 5 }
  ]
}
```

### PATCH `/api/agentes/<id>/disponibilidad/`
Actualiza disponibilidad de un agente.

**Body:**
```json
{ "disponible": false }
```

### POST `/api/chats/<id>/cerrar/`
Cierra un chat asignado y lo marca como resuelto.

### GET `/api/historial/<remote_jid>/`
Obtiene el historial completo de mensajes de un cliente en un bot.

**Response 200:**
```json
{
  "remote_jid": "573001234567@s.whatsapp.net",
  "mensajes": [
    { "texto": "Hola", "de": "cliente", "timestamp": "2025-06-01T10:00:00Z" },
    { "texto": "¡Hola! ¿En qué puedo ayudarte?", "de": "bot", "timestamp": "2025-06-01T10:00:01Z" }
  ]
}
```
