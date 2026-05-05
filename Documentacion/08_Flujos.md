# 08 — Flujos del Sistema

## Flujo 1: Primer mensaje de un cliente nuevo

Este es el flujo principal del sistema actual.

```
╔══════════════════════════════════════════════════════════════════╗
║  CLIENTE FINAL (WhatsApp)                                        ║
╚══════════════════════════════════════════════════════════════════╝
│
│  1. Cliente escribe: "Hola, quiero información"
│     al número vinculado al bot
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  GATEWAY NODE.JS — messages.upsert                               ║
╚══════════════════════════════════════════════════════════════════╝
│
│  2. Baileys emite evento messages.upsert
│  3. extractMessageText(message) → "Hola, quiero información"
│  4. Ignora mensajes propios (key.fromMe === true)
│
│  5. POST http://127.0.0.1:8000/api/whatsapp/webhook/
│     {
│       remoteJid: "573001234567@s.whatsapp.net",
│       pushName: "Carlos",
│       messageText: "Hola, quiero información",
│       session: "1:0",
│       owner: "1"
│     }
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  DJANGO — whatsapp_webhook()                                     ║
╚══════════════════════════════════════════════════════════════════╝
│
│  6. Parsear session "1:0" → owner_id=1, slot=0
│  7. ConfigBot.objects.get(owner_id=1) → config del bot
│  8. WhatsAppMessage.objects.create(
│       bot=config, remote_jid=..., push_name="Carlos",
│       message_text="Hola, quiero información"
│     )
│
│  9. Construir prompt:
│     system: config.instrucciones_ia
│     user:   config.mensaje_bienvenida + "\nUsuario: Hola, quiero información"
│
│  10. POST https://api.deepseek.com/v1/chat/completions
│      Authorization: Bearer {config.api_key}
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  DEEPSEEK API                                                    ║
╚══════════════════════════════════════════════════════════════════╝
│
│  11. Genera respuesta basada en instrucciones del bot
│      → "¡Hola Carlos! Con gusto te ayudo. ¿Buscas comprar o arrendar?"
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  DJANGO — continúa whatsapp_webhook()                           ║
╚══════════════════════════════════════════════════════════════════╝
│
│  12. WhatsAppMessage.reply_text = respuesta
│      WhatsAppMessage.replied = True
│      WhatsAppMessage.replied_at = now()
│      .save()
│
│  13. return JsonResponse({
│        "remoteJid": "573001234567@s.whatsapp.net",
│        "reply": "¡Hola Carlos! Con gusto te ayudo. ¿Buscas comprar o arrendar?"
│      })
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  GATEWAY NODE.JS — continúa messages.upsert                      ║
╚══════════════════════════════════════════════════════════════════╝
│
│  14. sock.sendMessage("573001234567@s.whatsapp.net", {
│        text: "¡Hola Carlos! Con gusto te ayudo. ¿Buscas comprar o arrendar?"
│      })
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  CLIENTE FINAL                                                   ║
╚══════════════════════════════════════════════════════════════════╝
│
│  15. Cliente recibe la respuesta del bot en WhatsApp
```

---

## Flujo 2: Vinculación de número por QR

```
╔══════════════════════════════════╗
║  USUARIO DEL PANEL (navegador)   ║
╚══════════════════════════════════╝
│
│  1. Accede a /configuracion/whatsapp/
│  2. La página hace GET /qr-json/ a Django
│
▼
╔══════════════════════════════════╗
║  DJANGO                          ║
╚══════════════════════════════════╝
│
│  3. Django hace GET /qr?user=1&slot=0 al Gateway
│
▼
╔══════════════════════════════════╗
║  GATEWAY NODE.JS                 ║
╚══════════════════════════════════╝
│
│  4. Si no hay sesión activa: startSocketFor("1:0")
│  5. Baileys inicia conexión con servidores WhatsApp
│  6. Evento connection.update → qr generado
│  7. sessions["1:0"].qr = qrString
│
│  8. Response: { status: "qr", qr: "2@abc123..." }
│
▼
╔══════════════════════════════════╗
║  DJANGO → NAVEGADOR              ║
╚══════════════════════════════════╝
│
│  9. Retorna { qr: "...", status: "qr" }
│  10. JavaScript renderiza el QR como imagen
│
│  (El navegador hace polling cada 3s al /qr-json/)
│
▼
╔══════════════════════════════════╗
║  USUARIO DEL PANEL               ║
╚══════════════════════════════════╝
│
│  11. Escanea el QR con su teléfono (WhatsApp → Dispositivos vinculados)
│
▼
╔══════════════════════════════════╗
║  GATEWAY NODE.JS                 ║
╚══════════════════════════════════╝
│
│  12. Evento connection.update → connection: "open"
│  13. sessions["1:0"].status = "connected"
│  14. Credenciales guardadas en ./auth_info/1:0/
│
▼
╔══════════════════════════════════╗
║  NAVEGADOR (siguiente poll)      ║
╚══════════════════════════════════╝
│
│  15. GET /qr-json/ → { status: "connected" }
│  16. UI muestra "✓ WhatsApp vinculado correctamente"
```

---

## Flujo 3: Reconexión automática tras caída

```
╔══════════════════════════════════╗
║  GATEWAY NODE.JS                 ║
╚══════════════════════════════════╝
│
│  1. Evento connection.update → connection: "close"
│     lastDisconnect.error.output.statusCode = 408 (timeout)
│
│  2. ¿Es logout intencional?
│     DisconnectReason.loggedOut → NO
│
│  3. reconnectAttempts["1:0"]++ (intento 1 de 6)
│
│  4. delay = Math.min(1000 * 2^intento, 30000)
│     = Math.min(2000, 30000) = 2000ms
│
│  5. setTimeout(() => startSocketFor("1:0"), 2000)
│
│  6. Nueva conexión → Baileys usa credenciales en ./auth_info/1:0/
│     (no necesita QR de nuevo si las credenciales son válidas)
│
│  7. Evento connection.update → connection: "open"
│  8. reconnectAttempts["1:0"] = 0  (reset)
│
│  → Reconexión exitosa, bot operativo nuevamente

Si tras 6 intentos no conecta:
│
│  9. sessions["1:0"].status = "failed"
│  10. Log de error
│  (El usuario debe generar nuevo QR desde el panel)
```

---

## Flujo 4: Transferencia a agente humano (diseño propuesto)

```
╔══════════════════════════════════════════════════════════════════╗
║  CONVERSACIÓN INICIAL (bot automático)                           ║
╚══════════════════════════════════════════════════════════════════╝
│
│  Turno 1: Cliente "Hola" → Bot "¿En qué puedo ayudarte?"
│  Turno 2: Cliente "Quiero arrendar" → Bot "¿Qué ciudad?"
│  Turno 3: Cliente "Bogotá" → Bot "¿Cuántas habitaciones?"
│  Turno 4: Cliente "2 hab, presupuesto $1.5M"
│
│  → Bot detecta condición de transferencia:
│    (N mensajes alcanzado O intención confirmada)
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  DJANGO — genera resumen                                         ║
╚══════════════════════════════════════════════════════════════════╝
│
│  1. Llama a DeepSeek con instrucción especial:
│     "Resume esta conversación en JSON con campos:
│      nombre_cliente, necesidad, urgencia, resumen"
│
│  2. Respuesta:
│     {
│       "nombre_cliente": "Carlos",
│       "necesidad": "Arrendar apartamento 2 hab en Bogotá, presupuesto $1.5M",
│       "urgencia": "media",
│       "resumen": "Cliente busca apartamento para arrendar. Ya tiene presupuesto definido."
│     }
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  DJANGO — asigna agente                                          ║
╚══════════════════════════════════════════════════════════════════╝
│
│  3. asignar_agente(bot, especialidad="arriendos")
│     → Agente: María López (ratio de carga: 0.33)
│
│  4. ChatAsignado.objects.create(
│       agente=María, bot=config,
│       remote_jid="573001234567@s.whatsapp.net",
│       estado="activo",
│       contexto_json=resumen_json,
│       transferido=True
│     )
│
│  5. Bot envía mensaje al cliente:
│     "En un momento te atenderá uno de nuestros asesores.
│      Tu referencia es #42."
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  DJANGO CHANNELS — notifica al agente                            ║
╚══════════════════════════════════════════════════════════════════╝
│
│  6. channel_layer.group_send("agente_3", {
│       "type": "nuevo_chat",
│       "payload": { ...contexto del cliente... }
│     })
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  NAVEGADOR DEL AGENTE (bandeja)                                  ║
╚══════════════════════════════════════════════════════════════════╝
│
│  7. WebSocket recibe evento
│  8. UI muestra: "Nuevo cliente: Carlos — Arriendos — Urgencia media"
│     con el resumen completo de la conversación
│
│  9. Agente hace clic → ve el historial completo
│  10. Agente escribe su respuesta en la bandeja
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  DJANGO — POST /send/                                            ║
╚══════════════════════════════════════════════════════════════════╝
│
│  11. Llama al gateway: POST /send
│      { number: "573001234567", message: "Hola Carlos, soy María..." }
│
▼
╔══════════════════════════════════════════════════════════════════╗
║  CLIENTE FINAL (WhatsApp)                                        ║
╚══════════════════════════════════════════════════════════════════╝
│
│  12. Recibe el mensaje del agente humano
│      (en el mismo chat, sin cambio de número)
│
│  [El bot no responde más automáticamente mientras transferido=True]
```

---

## Flujo 5: Alta de usuario y configuración inicial

```
Admin de plataforma
│
│  1. Accede a /app2/usuarios/crear/
│  2. Crea usuario: nombre, plan=especial
│  3. User.objects.create(nombre=..., plan='especial')
│
Usuario nuevo (empresa)
│
│  4. Accede a /login/ con sus credenciales
│  5. Sesión iniciada
│
│  6. Accede a /configuracion/crear/
│  7. Configura su primer bot:
│     - nombre: "Bot Inmobiliaria XYZ"
│     - instrucciones_ia: "Eres un asistente de..."
│     - mensaje_bienvenida: "Bienvenido a..."
│     - api_key: "sk-deepseek-xxx"
│
│  8. Sube archivos de contexto (catálogo de propiedades.pdf)
│
│  9. Accede a /configuracion/whatsapp/
│  10. Escanea QR → número vinculado
│
│  → Bot operativo: recibe y responde mensajes en WhatsApp
```

---

## Resumen de responsabilidades por componente

| Evento | Gateway | Django | DeepSeek | WebSocket |
|---|---|---|---|---|
| Mensaje entrante | Recibe y envía al webhook | Procesa y consulta IA | Genera respuesta | — |
| Respuesta al cliente | Envía a WhatsApp | Ordena el envío | — | — |
| QR de vinculación | Genera y expone | Solicita y retorna al panel | — | — |
| Reconexión | Reintenta con backoff | — | — | — |
| Transferencia a agente | — | Asigna y notifica | Genera resumen | Entrega contexto |
| Mensaje del agente | Envía a WhatsApp | Recibe del panel | — | — |
| Actualización de estado | — | Actualiza BD | — | Notifica al panel |
