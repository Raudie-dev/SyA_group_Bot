# 01 — Descripción General del Sistema

## ¿Qué es SyA Group Bot?

SyA Group Bot es una plataforma multiusuario de atención al cliente sobre WhatsApp. Combina un bot conversacional con inteligencia artificial y una bandeja de trabajo para agentes humanos. El bot actúa como primer punto de contacto: recibe el mensaje del cliente, genera una respuesta automática basada en el contexto configurado, y —en la fase objetivo del sistema— transfiere el caso a un agente humano con el historial completo de la conversación.

El sistema está diseñado para que múltiples empresas (usuarios de la plataforma) puedan operar sus propios bots de WhatsApp de forma aislada, con configuraciones, bases de conocimiento y conversaciones independientes entre sí.

---

## Componentes principales

| Componente | Tecnología | Rol |
|---|---|---|
| Panel web de control | Django 5 (Python) | Configuración de bots, gestión de usuarios, historial de mensajes |
| Gateway de WhatsApp | Node.js + Baileys | Mantiene la sesión WhatsApp, recibe/envía mensajes |
| Motor de IA | DeepSeek API | Genera respuestas automatizadas |
| Base de datos | SQLite | Almacenamiento persistente de usuarios, bots, mensajes y sesiones |
| Interfaz web de QR | Django template | Vinculación del número de WhatsApp mediante QR |

---

## Flujo de alto nivel

```
Cliente WhatsApp
       │
       │  mensaje entrante
       ▼
Node.js Gateway (puerto 3000)
  Baileys / @whiskeysockets
       │
       │  POST /api/whatsapp/webhook/
       ▼
Django Backend (puerto 8000)
  - Identifica el bot asociado a la sesión
  - Registra el mensaje en BD
  - Llama a la API de IA (DeepSeek)
  - Devuelve la respuesta
       │
       │  { "reply": "..." }
       ▼
Node.js Gateway
  - Envía la respuesta al número del cliente
       │
       ▼
Cliente WhatsApp (recibe respuesta)
```

---

## Roles del sistema

### Usuario de la plataforma (empresa / agente)
Crea y configura su bot, sube documentos de contexto, vincula su número de WhatsApp y monitorea las conversaciones desde el panel.

### Administrador de la plataforma
Gestiona los usuarios registrados, controla el acceso a las APIs de IA disponibles (DeepSeek, ChatGPT, Gemini) y configura los planes de suscripción.

### Cliente final
Persona que escribe al número de WhatsApp vinculado al bot. Interactúa directamente con el bot y, en el flujo objetivo, es transferido a un agente humano.

---

## Planes de suscripción

| Plan | Bots permitidos |
|---|---|
| base | 1 |
| especial | 3 |
| premium | Ilimitados |

---

## Estado actual del sistema

El sistema ya tiene implementado:
- Vinculación de WhatsApp por QR (multi-sesión)
- Respuestas automáticas vía DeepSeek
- Registro de mensajes en base de datos
- Panel de control por usuario
- Gestión de usuarios y APIs por administrador
- Subida de archivos de contexto (PDF, Word, Excel)

Pendiente de implementar:
- Algoritmo de asignación de agentes humanos
- WebSocket para entrega de contexto al agente
- Bandeja de conversaciones tipo WhatsApp Web para agentes
- Resumen estructurado de conversación generado por IA antes de la transferencia
