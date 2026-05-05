# 03 — Bot Conversacional

## Rol del bot

El bot es el primer punto de contacto con el cliente final. Opera de forma completamente automática: recibe el mensaje, consulta la inteligencia artificial con el contexto configurado por el usuario de la plataforma, y responde directamente en WhatsApp. Su objetivo final es recopilar suficiente información para que, cuando el caso sea transferido a un agente humano, este tenga todo el contexto necesario sin tener que releer la conversación completa.

---

## Flujo de conversación actual

```
Cliente escribe en WhatsApp
          │
          ▼
Gateway detecta mensaje entrante
  extractMessageText() → texto plano
          │
          │ POST /api/whatsapp/webhook/
          ▼
Django identifica el bot
  session = "{user_id}:{slot}"
  ConfigBot.objects.get(owner_id=user_id, slot=slot)
          │
          ▼
Django registra el mensaje
  WhatsAppMessage.objects.create(...)
          │
          ▼
Django construye el prompt de IA
  ┌─────────────────────────────────────────────────┐
  │  system: config.instrucciones_ia                │
  │  user:   config.mensaje_bienvenida              │
  │          + "\nUsuario: " + messageText           │
  └─────────────────────────────────────────────────┘
          │
          ▼
DeepSeek API genera la respuesta
  model: deepseek-chat
  max_tokens: sin límite configurado actualmente
          │
          ▼
Django guarda la respuesta y la retorna al Gateway
  WhatsAppMessage.reply_text = respuesta
  return { "remoteJid": ..., "reply": respuesta }
          │
          ▼
Gateway envía la respuesta al cliente WhatsApp
```

---

## Configuración del bot (ConfigBot)

Cada bot tiene tres parámetros que determinan su comportamiento:

### `instrucciones_ia` (system prompt)
Define el rol y las reglas del bot. Ejemplo:

```
Eres un asistente de atención al cliente de una inmobiliaria.
Tu función es identificar si el cliente busca arrendar, comprar o vender.
Responde siempre en español, de forma cordial y concisa.
Si el cliente da su nombre, úsalo en la conversación.
Cuando hayas identificado su necesidad principal, díselo y espera confirmación.
```

### `mensaje_bienvenida`
Texto que se antepone al mensaje del usuario en cada llamada a la IA. Funciona como contexto inicial y guía el tono de respuesta. Ejemplo:

```
Bienvenido al servicio de atención de Inmobiliaria XYZ.
Estamos aquí para ayudarte con cualquier consulta sobre propiedades.
```

### Archivos de contexto (`ContextFile`)
El usuario puede subir documentos (PDF, Word, Excel) que el bot usa como base de conocimiento. El sistema extrae el texto de los primeros 3 fragmentos del documento y lo incluye en el prompt. Útil para catálogos de productos, manuales, FAQs, o listas de propiedades.

---

## Construcción del prompt completo

```python
# Sistema (instrucciones del bot)
system_content = config.instrucciones_ia  # texto libre configurado por el usuario

# Contexto de archivos subidos (si existen)
context_text = ""
for cf in context_files[:3]:  # máximo 3 archivos
    # extrae texto del PDF/Word/Excel
    context_text += extraido_del_archivo

# Mensaje del usuario
user_content = config.mensaje_bienvenida + "\nUsuario: " + mensaje_usuario + context_text

# Llamada a DeepSeek
{
  "model": "deepseek-chat",
  "messages": [
    { "role": "system", "content": system_content },
    { "role": "user",   "content": user_content }
  ]
}
```

---

## Manejo de contexto

### Contexto actual (stateless)
El sistema actual **no mantiene historial de conversación** entre turnos. Cada mensaje del cliente genera una llamada a la IA que solo ve el mensaje actual, el system prompt y el mensaje de bienvenida. No se pasa el historial de mensajes anteriores de esa conversación.

### Limitación y solución propuesta
Para que el bot pueda recordar lo que el cliente dijo antes (nombre, necesidad, datos), se debe cargar el historial de `WhatsAppMessage` de esa sesión y pasarlo como mensajes previos a la API:

```python
# Historial de la conversación (propuesta)
historial = WhatsAppMessage.objects.filter(
    bot=config,
    remote_jid=remoteJid
).order_by('received_at').values('message_text', 'reply_text')

messages = [{"role": "system", "content": system_content}]
for msg in historial:
    messages.append({"role": "user",      "content": msg['message_text']})
    messages.append({"role": "assistant", "content": msg['reply_text']})
messages.append({"role": "user", "content": mensaje_actual})
```

Esto da continuidad real a la conversación y permite al bot acumular información del cliente a lo largo de múltiples mensajes.

---

## Tipos de mensajes soportados

El gateway puede extraer texto de los siguientes tipos de mensajes de WhatsApp:

| Tipo de mensaje | Campo extraído |
|---|---|
| Texto plano | `message.conversation` |
| Texto extendido | `extendedTextMessage.text` |
| Imagen con caption | `imageMessage.caption` |
| Video con caption | `videoMessage.caption` |
| Respuesta de botón | `buttonsResponseMessage.selectedButtonId` |
| Respuesta de template | `templateButtonReplyMessage.selectedId` |
| Cualquier otro | JSON stringify completo del objeto mensaje |

---

## Flujo objetivo: bot como filtro hacia agente humano

El flujo completo que el sistema debe soportar es:

```
1. Cliente escribe → Bot responde (fase automática)
   - El bot hace preguntas clave: nombre, necesidad, urgencia
   - El bot acumula respuestas en el historial

2. Bot detecta condición de transferencia
   - Condición configurable: N mensajes, palabra clave, intención detectada
   - Ejemplo: "el cliente confirmó su necesidad principal"

3. Bot genera resumen estructurado
   - Llama a IA con instrucción especial: "resume esta conversación en formato JSON"
   - Formato sugerido:
     {
       "nombre_cliente": "...",
       "telefono": "...",
       "necesidad": "...",
       "urgencia": "alta | media | baja",
       "resumen": "..."
     }

4. Sistema asigna agente humano (ver 04_Asignacion_Agentes.md)

5. WebSocket notifica al agente con el contexto (ver 05_WebSockets.md)

6. Agente toma el control del chat desde su bandeja
```

---

## Extensión de tipos de IA soportados

La tabla `IAAPI` (app2) registra las APIs disponibles: DeepSeek, ChatGPT, Gemini, EasyBot. Actualmente el webhook solo llama a DeepSeek. Para soportar múltiples proveedores, la lógica de llamada debe consultar qué API tiene habilitada el usuario (`UserIAAccess`) y usar el endpoint y la clave correspondiente de la tabla `IAAPI`.
