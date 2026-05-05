# 04 — Algoritmo de Asignación de Agentes

## Contexto

Una vez que el bot ha recopilado el contexto inicial del cliente y determina que debe transferir el caso a un humano, el sistema necesita seleccionar al agente más adecuado para atender esa conversación. Este módulo aún no está implementado en el código actual y se documenta aquí como diseño funcional.

---

## Modelo de datos requerido

Para implementar la asignación de agentes se necesita extender el modelo de datos actual con las siguientes entidades:

### `Agente`
```
- id
- user (FK → User)            # usuario de la plataforma al que pertenece este agente
- nombre (CharField)
- disponible (Boolean)         # disponibilidad manual (activo/ausente)
- max_chats_simultaneos (int)  # límite de chats que puede atender a la vez
- especialidad (CharField)     # área de conocimiento: ventas, soporte, facturación, etc.
- activo (Boolean)             # habilitado en el sistema
- created_at (DateTimeField)
```

### `ChatAsignado`
```
- id
- agente (FK → Agente)
- remote_jid (CharField)       # número del cliente
- bot (FK → ConfigBot)
- estado (CharField)           # pendiente, activo, cerrado
- contexto_json (TextField)    # resumen generado por IA (JSON)
- asignado_at (DateTimeField)
- cerrado_at (DateTimeField)
```

---

## Algoritmo de asignación

El algoritmo propuesto es **round-robin con peso por carga**. Se elige el agente disponible con menor carga activa relativa a su capacidad.

### Pseudocódigo

```python
def asignar_agente(bot, especialidad=None):
    # 1. Filtrar agentes del bot que estén disponibles y activos
    agentes = Agente.objects.filter(
        user=bot.owner,
        disponible=True,
        activo=True
    )

    # 2. Filtrar por especialidad si se provee
    if especialidad:
        agentes = agentes.filter(especialidad=especialidad)

    if not agentes.exists():
        return None  # No hay agentes disponibles

    # 3. Calcular carga actual de cada agente
    # carga = chats activos / max_chats_simultaneos (ratio 0.0 a 1.0)
    candidatos = []
    for agente in agentes:
        chats_activos = ChatAsignado.objects.filter(
            agente=agente,
            estado='activo'
        ).count()

        if chats_activos >= agente.max_chats_simultaneos:
            continue  # Agente a capacidad máxima, omitir

        ratio_carga = chats_activos / agente.max_chats_simultaneos
        candidatos.append((agente, ratio_carga))

    if not candidatos:
        return None  # Todos a capacidad máxima

    # 4. Seleccionar el agente con menor ratio de carga
    agente_seleccionado = min(candidatos, key=lambda x: x[1])[0]

    return agente_seleccionado


def crear_asignacion(bot, remote_jid, contexto_json, especialidad=None):
    agente = asignar_agente(bot, especialidad)

    if agente is None:
        # Encolar en lista de espera o notificar al supervisor
        encolar_en_espera(bot, remote_jid, contexto_json)
        return None

    chat = ChatAsignado.objects.create(
        agente=agente,
        remote_jid=remote_jid,
        bot=bot,
        estado='activo',
        contexto_json=contexto_json,
        asignado_at=now()
    )

    return chat
```

---

## Casos de uso

### Caso 1: Agente disponible con menor carga
- Agente A: 2 chats activos / 5 máximo → ratio 0.40
- Agente B: 1 chat activo / 3 máximo → ratio 0.33
- **Resultado**: Se asigna a Agente B (menor ratio)

### Caso 2: Todos los agentes a capacidad máxima
- Agente A: 5/5 → ratio 1.0
- Agente B: 3/3 → ratio 1.0
- **Resultado**: El cliente queda en cola de espera. El bot le informa que será atendido en breve.

### Caso 3: Ningún agente disponible (todos en modo ausente)
- **Resultado**: El bot informa un horario de atención o deja el caso en cola para cuando alguien active su disponibilidad.

### Caso 4: Asignación por especialidad
- El bot detecta (via IA) que el cliente quiere hablar de facturación
- Solo se evalúan agentes con `especialidad='facturacion'`
- Si no hay, se cae al pool general

---

## Estrategias alternativas

### Round-robin simple
Asignar de forma rotativa ignorando la carga actual. Más justo en tiempo, menos óptimo en distribución.

```python
ultimo_agente_id = cache.get('ultimo_agente_bot_{bot.id}', 0)
agentes_list = list(agentes.order_by('id'))
siguiente = (ultimo_agente_id + 1) % len(agentes_list)
cache.set('ultimo_agente_bot_{bot.id}', siguiente)
agente = agentes_list[siguiente]
```

### Asignación manual
El supervisor ve los chats en cola y arrastra el chat al agente que prefiera. Útil para equipos pequeños.

### Asignación por reglas configurables
El administrador define reglas: "si el mensaje contiene 'factura' → asignar al equipo de cobranza". Se implementa con un motor de reglas simple sobre el JSON de contexto generado por el bot.

---

## Endpoint propuesto

```
POST /api/asignar-chat/
Body:
{
  "remote_jid": "573001234567@s.whatsapp.net",
  "bot_id": 1,
  "contexto": { ...resumen generado por el bot... },
  "especialidad": "ventas"  // opcional
}

Response 200:
{
  "agente_id": 3,
  "agente_nombre": "María López",
  "chat_id": 42,
  "estado": "activo"
}

Response 503:
{
  "estado": "en_cola",
  "posicion": 4,
  "mensaje": "Todos los agentes están ocupados. Será atendido en breve."
}
```

---

## Integración con el flujo general

Después de la asignación, el sistema debe:
1. Actualizar el `ChatAsignado` con el agente y el estado
2. Notificar al agente vía WebSocket con el contexto completo (ver [05_WebSockets.md](05_WebSockets.md))
3. Bloquear las respuestas automáticas del bot para ese `remote_jid` (agregar flag `transferido=True` en `ChatAsignado`)
4. Permitir que el agente envíe mensajes manuales usando el endpoint `/send` del gateway
