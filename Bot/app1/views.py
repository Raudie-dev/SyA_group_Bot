from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import requests
from .models import User as User_admin, ConfigBot, WhatsAppSession, WhatsAppMessage, ContextFile
import os
import PyPDF2
import docx
import pandas as pd
from .models import User as User_admin, ConfigBot, WhatsAppSession, WhatsAppMessage, ContextFile, Departamento, Agente
from django_ratelimit.decorators import ratelimit

from django.core.mail import EmailMessage
from django.views.decorators.http import require_POST

def _get_session_user(request):
    uid = request.session.get('user_admin_id')
    if not uid:
        return None
    try:
        return User_admin.objects.get(id=uid)
    except User_admin.DoesNotExist:
        return None

# Create your views here.
def index(request):
    user = _get_session_user(request)
    bot = _get_public_bot()
    mensaje_bienvenida = bot.mensaje_bienvenida if bot else ''
    return render(request, 'index.html', {
        'user': user,
        'mensaje_bienvenida': mensaje_bienvenida,
    })

# Vista para recibir y enviar reclamos por correo
@require_POST
@csrf_exempt
def enviar_reclamo(request):
    nombre = request.POST.get('nombre', '').strip()
    telefono = request.POST.get('telefono', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    if not nombre or not descripcion:
        return JsonResponse({'ok': False, 'error': 'Nombre y descripción son obligatorios.'})
    # Construir mensaje
    cuerpo = f"""
    Se ha recibido un nuevo reclamo/reporte desde la web:

    Nombre: {nombre}
    Teléfono: {telefono}
    Descripción: {descripcion}
    """
    email = EmailMessage(
        subject='Nuevo reclamo o reporte desde la web',
        body=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=['sergio@syagroupchile.com', 'contacto@syagroup-chile.com']
    )
    try:
        email.send()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'No se pudo enviar el correo. ' + str(e)})

def login(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        password = request.POST.get('password', '')

        try:
            user = User_admin.objects.get(nombre=nombre)
            if user.bloqueado:
                messages.error(request, 'Usuario bloqueado')
            elif user.password == password or check_password(password, user.password):
                request.session['user_admin_id'] = user.id
                return redirect('estado')
            else:
                messages.error(request, 'Contraseña incorrecta')
            return render(request, 'login.html')
        except User_admin.DoesNotExist:
            messages.error(request, 'Usuario no encontrado')
            return render(request, 'login.html')

    user = _get_session_user(request)
    return render(request, 'login.html', {'user': user})

def estado(request):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        messages.error(request, 'Debe iniciar sesión primero')
        return redirect('login')
    try:
        user = User_admin.objects.get(id=user_id)
    except User_admin.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('login')

    bot = ConfigBot.objects.filter(owner=user).first()
    bot_statuses = []
    gateway = settings.WHATSAPP_GATEWAY_URL

    if bot:
        bot_status = 'unknown'
        try:
            sresp = requests.get(f"{gateway}/status", params={'user': user.id, 'slot': bot.id}, timeout=3)
            if sresp.status_code == 200:
                bot_status = sresp.json().get('status', 'unknown')
        except Exception:
            bot_status = 'unknown'

        bot_statuses.append({
            'bot': bot,
            'status': bot_status
        })

    return render(request, 'control.html', {'bot_statuses': bot_statuses, 'user': user})

def configuracion(request):
    user = _get_session_user(request)
    if not user:
        messages.error(request, 'Debe iniciar sesión primero')
        return redirect('login')

    bot = ConfigBot.objects.filter(owner=user).first()

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        mensaje_bienvenida = request.POST.get('mensaje_bienvenida', '').strip()
        instrucciones_ia = request.POST.get('instrucciones_ia', '').strip()
        api_key = request.POST.get('api_key', '').strip()
        api_provider = request.POST.get('api_provider', 'deepseek')

        if bot:
            bot.nombre = nombre
            bot.mensaje_bienvenida = mensaje_bienvenida
            bot.instrucciones_ia = instrucciones_ia
            bot.api_key = api_key
            bot.api_provider = api_provider
            bot.save()
        else:
            bot = ConfigBot.objects.create(
                nombre=nombre,
                owner=user,
                mensaje_bienvenida=mensaje_bienvenida,
                instrucciones_ia=instrucciones_ia,
                api_key=api_key,
                api_provider=api_provider
            )

        allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx']
        if 'context_files' in request.FILES:
            for file in request.FILES.getlist('context_files'):
                if any(file.name.lower().endswith(ext) for ext in allowed_extensions):
                    ContextFile.objects.create(bot=bot, file=file)
                else:
                    messages.error(request, f'Archivo {file.name} no permitido. Solo PDF, Word y Excel.')

        for file_id in request.POST.getlist('delete_files'):
            try:
                context_file = ContextFile.objects.get(id=file_id, bot=bot)
                context_file.file.delete()
                context_file.delete()
            except ContextFile.DoesNotExist:
                pass

        messages.success(request, 'Configuración guardada correctamente.')
        return redirect('configuracion')

    bot_status = 'unknown'
    # Filtrar solo archivos que existen en disco
    context_files = []
    if bot:
        for cf in bot.context_files.all():
            try:
                if cf.file and os.path.exists(cf.file.path):
                    context_files.append(cf)
                else:
                    cf.delete()  # limpiar registro huérfano
            except Exception:
                cf.delete()

    return render(request, 'configuracion.html', {
        'bot': bot,
        'bot_status': bot_status,
        'user': user,
        'context_files': context_files
    })


def whatsapp_configuracion(request):
    user = _get_session_user(request)
    if not user:
        messages.error(request, 'Debe iniciar sesión primero')
        return redirect('login')

    bot = ConfigBot.objects.filter(owner=user).first()
    if not bot:
        messages.error(request, 'Guarda primero la configuración general del bot antes de conectar WhatsApp.')
        return redirect('configuracion')

    gateway = settings.WHATSAPP_GATEWAY_URL
    qr = None
    bot_status = 'unknown'

    try:
        resp = requests.get(f"{gateway}/status", params={'user': user.id, 'slot': bot.id}, timeout=3)
        if resp.status_code == 200:
            bot_status = resp.json().get('status', 'unknown')
    except Exception:
        bot_status = 'unknown'

    if request.method == 'POST' and 'generate_qr' in request.POST:
        if bot_status == 'connected':
            messages.info(request, 'El bot ya esta conectado.')
        else:
            try:
                resp = requests.post(f"{gateway}/generate", params={'user': user.id, 'slot': bot.id}, timeout=5)
                if resp.status_code == 200:
                    messages.info(request, 'Se ha solicitado la generacion de un nuevo QR. Espere unos segundos.')
                else:
                    messages.error(request, f'Error al solicitar QR: {resp.text}')
            except Exception as e:
                messages.error(request, f'Error solicitando QR: {e}')

    if request.method == 'POST' and 'unlink' in request.POST:
        try:
            resp = requests.post(f"{gateway}/unlink", params={'user': user.id, 'slot': bot.id}, timeout=5)
            if resp.status_code == 200:
                messages.success(request, 'Teléfono desvinculado correctamente.')
            else:
                messages.error(request, f'Error al desvincular: {resp.text}')
        except Exception as e:
            messages.error(request, f'Error al desvincular: {e}')

    try:
        resp = requests.get(f"{gateway}/qr", params={'user': user.id, 'slot': bot.id}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            qr = data.get('qr')
    except Exception:
        qr = None

    return render(request, 'whatsapp_configuracion.html', {
        'bot': bot,
        'qr': qr,
        'bot_status': bot_status,
        'user': user
    })


def create_edit_bot(request, bot_id=None):
    return redirect('configuracion')


def delete_bot(request, bot_id):
    user = _get_session_user(request)
    if not user:
        messages.error(request, 'Debe iniciar sesión primero')
        return redirect('login')

    try:
        bot = ConfigBot.objects.get(id=bot_id, owner=user)
        bot.delete()
        messages.success(request, 'Bot eliminado correctamente')
    except ConfigBot.DoesNotExist:
        messages.error(request, 'Bot no encontrado')

    return redirect('configuracion')


def qr_json(request):
    user = _get_session_user(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)

    bot_id = request.GET.get('bot_id')
    if not bot_id:
        return JsonResponse({'error': 'bot_id requerido'}, status=400)

    try:
        bot = ConfigBot.objects.get(id=bot_id, owner=user)
    except ConfigBot.DoesNotExist:
        return JsonResponse({'error': 'Bot no encontrado'}, status=404)

    gateway = settings.WHATSAPP_GATEWAY_URL
    try:
        resp = requests.get(f"{gateway}/qr", params={'user': user.id, 'slot': bot.id}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return JsonResponse({
                'qr': data.get('qr'),
                'status': data.get('status', 'unknown')
            })
    except Exception:
        pass

    return JsonResponse({'qr': None, 'status': 'unknown'})

def _get_public_bot():
    bot = ConfigBot.objects.filter(owner__isnull=True).first()
    if bot:
        return bot
    return ConfigBot.objects.first()


def _load_context_from_bot(bot):
    context_items = []
    allowed_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx']
    for context_file in bot.context_files.all():
        file_path = context_file.file.path
        filename = os.path.basename(context_file.file.name)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in allowed_exts:
            continue
        try:
            if ext == '.pdf':
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ''
                    for page in reader.pages[:3]:
                        text += page.extract_text() or ''
                    text = text.strip().replace('\r', '')
                    if text:
                        context_items.append(f"[PDF: {filename}]\n{text[:1500]}")
            elif ext in ['.docx']:
                doc = docx.Document(file_path)
                text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
                if text:
                    context_items.append(f"[Word: {filename}]\n{text[:1500]}")
            elif ext in ['.xls', '.xlsx']:
                df = pd.read_excel(file_path, nrows=20)
                text = df.to_string(index=False)
                if text:
                    context_items.append(f"[Excel: {filename}]\n{text[:1500]}")
            # .doc (antiguo) no soportado directamente
        except Exception as e:
            context_items.append(f"[Error leyendo {filename}]: {e}")
    context_str = "\n\n".join(context_items)
    return context_str

def _extraer_datos_y_resumen(conv_texto, api_key):
    """Una sola llamada DeepSeek que extrae datos Y genera resumen."""
    try:
        resp = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": (
                        "Eres un extractor de datos de conversaciones comerciales. "
                        "Responde SOLO con un JSON válido, sin markdown, sin explicaciones. "
                        "El JSON debe tener exactamente estas claves: "
                        "nombre, correo, telefono, empresa, plan_interes, volumen_reportes, resumen. "
                        "resumen: 2-3 oraciones del perfil del cliente y su necesidad principal. "
                        "Si un dato no aparece usa string vacío."
                    )},
                    {"role": "user", "content": conv_texto}
                ]
            },
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            timeout=15
        )
        if resp.status_code == 200:
            import json as json_mod
            raw = resp.json()['choices'][0]['message']['content']
            raw = raw.strip().strip('```json').strip('```').strip()
            return json_mod.loads(raw)
    except Exception as ex:
        print('[Extraccion+Resumen error]', ex)
    return {
        'nombre': '', 'correo': '', 'telefono': '',
        'empresa': '', 'plan_interes': '', 'volumen_reportes': '', 'resumen': ''
    }

@ratelimit(key='ip', rate='20/m', method='POST', block=True)
def public_chat(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST allowed')

    message = request.POST.get('message', '').strip()
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key

    if not message:
        return JsonResponse({'ok': False, 'error': 'Mensaje vacio'}, status=400)

    bot = _get_public_bot()
    if not bot:
        return JsonResponse({'ok': False, 'error': 'No hay bot configurado.'}, status=500)

    if not bot.api_key or not bot.instrucciones_ia:
        return JsonResponse({'ok': False, 'error': 'Bot sin configuracion de IA.'}, status=500)

    # Verificar conexion WhatsApp activa
    gateway = settings.WHATSAPP_GATEWAY_URL
    try:
        status_resp = requests.get(
            f"{gateway}/status",
            params={'user': bot.owner_id, 'slot': bot.id},
            timeout=3
        )
        if status_resp.status_code != 200 or status_resp.json().get('status') != 'connected':
            return JsonResponse({
                'ok': False,
                'error': 'El servicio de atencion no esta disponible en este momento. Intentalo mas tarde.'
            }, status=503)
    except Exception:
        return JsonResponse({
            'ok': False,
            'error': 'El servicio de atencion no esta disponible en este momento. Intentalo mas tarde.'
        }, status=503)

    # Verificar si ya fue transferido
    ya_transferido = WhatsAppMessage.objects.filter(
        bot=bot,
        remote_jid=session_key,
        transferido=True
    ).exists()

    if ya_transferido:
        return JsonResponse({
            'ok': True,
            'reply': 'Tu consulta ya fue transferida a un asesor. En breve te contactaran.'
        })

    # Sanitizar mensaje — eliminar flags de transferencia inyectados por el usuario
    import re
    PATRON_CONTROL = re.compile(
        r'(<<[A-Z_]+[^>]*>>|TRANSFER_JSON\s*:\s*\{[^}]*\}|<<TRANSFERIR[^>]*>>)',
        re.IGNORECASE
    )
    message = PATRON_CONTROL.sub('', message).strip()

    if not message:
        return JsonResponse({'ok': False, 'error': 'Mensaje invalido.'}, status=400)

    # Guardar mensaje entrante
    WhatsAppMessage.objects.create(
        bot=bot,
        remote_jid=session_key,
        push_name='Web',
        message_text=message
    )

    # Cargar historial completo
    historial = WhatsAppMessage.objects.filter(
        bot=bot,
        remote_jid=session_key
    ).order_by('received_at')

    # Contexto de archivos
    context_text = _load_context_from_bot(bot)

    # Cargar departamentos disponibles desde BD
    departamentos_disponibles = Departamento.objects.filter(owner=bot.owner)
    dptos_texto = ""
    if departamentos_disponibles.exists():
        dptos_texto = "\n\nDEPARTAMENTOS DISPONIBLES PARA TRANSFERENCIA:\n"
        for dpto in departamentos_disponibles:
            desc = f" — {dpto.descripcion}" if dpto.descripcion else ""
            dptos_texto += f"- {dpto.nombre.lower()}{desc}\n"
        dptos_texto += (
            "\nCuando debas transferir usa exactamente:\n"
            "<<TRANSFERIR:nombre_departamento>>\n"
            "Donde nombre_departamento es uno de los listados arriba en minuscula."
        )

    system_content = bot.instrucciones_ia.strip()
    if context_text:
        system_content += f"\n\nArchivos de contexto:\n{context_text}"
    if dptos_texto:
        system_content += dptos_texto

    # Construir messages con historial
    messages_ia = [{"role": "system", "content": system_content}]
    for msg in historial:
        if msg.message_text:
            messages_ia.append({"role": "user", "content": msg.message_text})
        if msg.reply_text:
            messages_ia.append({"role": "assistant", "content": msg.reply_text})

    # Llamar a DeepSeek
    try:
        resp = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={"model": "deepseek-chat", "messages": messages_ia},
            headers={
                'Authorization': f'Bearer {bot.api_key}',
                'Content-Type': 'application/json'
            },
            timeout=15
        )
        resp.raise_for_status()
        raw_reply = resp.json()['choices'][0]['message']['content'].strip()
        max_chars = getattr(bot, 'max_response_chars', 1000)
        if max_chars and len(raw_reply) > max_chars:
            raw_reply = raw_reply[:max_chars].rsplit(' ', 1)[0] + '…'
    except Exception as e:
        print('[DeepSeek error]', e)
        return JsonResponse({'ok': False, 'error': f'Error IA: {e}'}, status=500)

    # Detectar flag de transferencia
    import re
    import json as json_mod
    import base64

    import json as json_mod, base64
    match_json   = re.search(r'TRANSFER_JSON\s*:\s*(\{[^}]+\})', raw_reply)
    match_flag   = re.search(r'<<TRANSFERIR:([^>]+)>>', raw_reply)
    match_simple = re.search(r'<<TRANSFERIR>>', raw_reply)

    reply_limpio = re.sub(r'TRANSFER_JSON\s*:\s*\{[^}]*\}', '', raw_reply)
    reply_limpio = re.sub(r'<<TRANSFERIR[^>]*>>', '', reply_limpio).strip()

    transferir   = bool(match_json or match_flag or match_simple)
    dpto_nombre  = ''
    if match_json:
        try:
            tj = json_mod.loads(match_json.group(1))
            dpto_nombre = tj.get('dept', '')
            transferir  = tj.get('ok', False)
        except Exception:
            transferir = False
    elif match_flag:
        dpto_nombre = match_flag.group(1).strip()

    # Guardar respuesta en el ultimo mensaje sin reply
    ultimo = WhatsAppMessage.objects.filter(
        bot=bot,
        remote_jid=session_key,
        reply_text__isnull=True
    ).order_by('-received_at').first()
    if ultimo:
        from django.utils.timezone import now
        ultimo.reply_text = reply_limpio
        ultimo.replied = True
        ultimo.replied_at = now()
        ultimo.save()

    # Procesar transferencia
    if transferir:
        # dpto_nombre ya viene definido arriba
        print('[DEBUG] Transferencia activada, dpto:', dpto_nombre)

        try:
            # Un solo recorrido: check + texto
            conv_check = ""
            conv_texto = ""
            for msg in WhatsAppMessage.objects.filter(
                bot=bot, remote_jid=session_key
            ).order_by('received_at'):
                if msg.message_text:
                    conv_check += msg.message_text + " "
                    conv_texto += f"Cliente: {msg.message_text}\n"
                if msg.reply_text:
                    conv_check += msg.reply_text + " "
                    conv_texto += f"Bot: {msg.reply_text}\n"

            tiene_correo   = bool(re.search(r'[\w.-]+@[\w.-]+\.\w+', conv_check))
            tiene_telefono = bool(re.search(r'\+?\d[\d\s\-]{7,}', conv_check))
            tiene_nombre   = len(conv_check.strip().split()) > 10

            if not (tiene_correo and tiene_telefono and tiene_nombre):
                print('[Transferencia] Datos insuficientes, bloqueando.')
                return JsonResponse({'ok': True, 'reply': reply_limpio})

            # Una sola llamada DeepSeek para datos + resumen
            datos_cliente = _extraer_datos_y_resumen(conv_texto, bot.api_key)
            resumen_ia    = datos_cliente.pop('resumen', '')
            plan_interes  = datos_cliente.get('plan_interes') or 'No especificado'

            # Generar PDF
            pdf_b64  = None
            filename = 'consulta.pdf'
            try:
                historial_completo = WhatsAppMessage.objects.filter(
                    bot=bot, remote_jid=session_key
                ).order_by('received_at')
                pdf_bytes = _generar_pdf_consulta(
                    historial_completo, datos_cliente, plan_interes,
                    dpto_nombre or 'General', resumen_ia
                )
                pdf_b64  = base64.b64encode(pdf_bytes).decode('utf-8')
                filename = f"consulta_{datos_cliente.get('nombre', 'cliente').replace(' ', '_')}.pdf"
                print(f'[DEBUG] PDF generado: {len(pdf_bytes)} bytes')
            except Exception as ex:
                print('[PDF error]', ex)

            # Buscar agentes
            agentes_destino = []
            if dpto_nombre:
                agentes_destino = list(Agente.objects.filter(
                    departamentos__nombre__iexact=dpto_nombre,
                    activo=True, owner=bot.owner
                ).prefetch_related('departamentos'))
            if not agentes_destino:
                agentes_destino = list(Agente.objects.filter(
                    activo=True, owner=bot.owner
                ).prefetch_related('departamentos'))

            if agentes_destino:
                from django.utils.timezone import now as tz_now
                fecha = tz_now().strftime('%d/%m/%Y %H:%M')
                mensaje_agente = (
                    f"NUEVA CONSULTA — {plan_interes}\n"
                    f"Fecha: {fecha}\n"
                    f"Departamento: {dpto_nombre or 'General'}\n\n"
                    f"DATOS DEL CLIENTE\n"
                    f"Nombre:   {datos_cliente.get('nombre') or 'No proporcionado'}\n"
                    f"Correo:   {datos_cliente.get('correo') or 'No proporcionado'}\n"
                    f"Telefono: {datos_cliente.get('telefono') or 'No proporcionado'}\n"
                    f"Empresa:  {datos_cliente.get('empresa') or 'Particular'}\n\n"
                    f"PERFIL COMERCIAL\n"
                    f"Plan de interes:  {plan_interes}\n"
                    f"Resumen:          {resumen_ia or 'No disponible'}\n\n"
                    f"Historial completo adjunto en PDF."
                )
                for agente in agentes_destino:
                    numero = agente.numero_whatsapp.strip().replace('+','').replace(' ','').replace('-','')
                    if not numero.isdigit() or len(numero) < 8:
                        print(f'[Transferencia] Numero invalido: {numero}')
                        continue
                    try:
                        if pdf_b64:
                            requests.post(f"{gateway}/send-doc", json={
                                'number': numero, 'message': mensaje_agente,
                                'filename': filename, 'filedata': pdf_b64,
                                'user': str(bot.owner_id), 'slot': str(bot.id)
                            }, timeout=20)
                        else:
                            requests.post(f"{gateway}/send", json={
                                'number': numero, 'message': mensaje_agente,
                                'user': str(bot.owner_id), 'slot': str(bot.id)
                            }, timeout=10)
                        print(f'[DEBUG] Enviado a {agente.nombre}')
                    except Exception as ex:
                        print(f'[Transferencia] Error enviando a {agente.nombre}:', ex)

        except Exception as e:
            import traceback
            print('[Transferencia web error]', traceback.format_exc())

        # Marcar como transferido siempre
        WhatsAppMessage.objects.filter(
            bot=bot,
            remote_jid=session_key
        ).update(transferido=True)

    return JsonResponse({'ok': True, 'reply': reply_limpio})

@csrf_exempt
def whatsapp_webhook(request):
    secret = request.headers.get('X-Webhook-Secret', '')
    if secret != getattr(settings, 'WEBHOOK_SECRET', ''):
        return JsonResponse({'error': 'No autorizado'}, status=401)

    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST allowed')

    import json, re
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    remoteJid   = data.get('remoteJid', '')
    pushName    = data.get('pushName', '')
    messageText = data.get('messageText', '').strip()

    # Parsear owner_id y slot desde session "userId_slotId"
    owner_id = None
    slot     = None
    try:
        owner_id = data.get('owner') or None
        session  = data.get('session', '')
        if session:
            parts    = str(session).split('_', 1)
            owner_id = parts[0]
            slot     = parts[1] if len(parts) > 1 else None
        owner_id = int(owner_id) if owner_id else None
        slot     = int(slot)     if slot     else None
    except Exception:
        owner_id = slot = None

    # Resolver ConfigBot
    config = None
    if owner_id and slot:
        config = ConfigBot.objects.filter(owner__id=owner_id, id=slot).first()
    elif owner_id:
        config = ConfigBot.objects.filter(owner__id=owner_id).first()
    if not config:
        config = ConfigBot.objects.filter(owner__isnull=True).first()

    if not config:
        return JsonResponse({'remoteJid': remoteJid, 'reply': ''})

    # Verificar si ya fue transferido ANTES de guardar
    ya_transferido = WhatsAppMessage.objects.filter(
        bot=config, remote_jid=remoteJid, transferido=True
    ).exists()
    if ya_transferido:
        return JsonResponse({'remoteJid': remoteJid, 'reply': ''})

    # Sanitizar input
    PATRON_CONTROL = re.compile(
        r'(<<[A-Z_]+[^>]*>>|TRANSFER_JSON\s*:\s*\{[^}]*\})',
        re.IGNORECASE
    )
    messageText = PATRON_CONTROL.sub('', messageText).strip()
    if not messageText:
        return JsonResponse({'remoteJid': remoteJid, 'reply': ''})

    # Guardar mensaje entrante
    WhatsAppMessage.objects.create(
        bot=config,
        remote_jid=remoteJid,
        push_name=pushName,
        message_text=messageText
    )

    # Cargar historial (ultimos 20, excluyendo el recien guardado)
    historial = WhatsAppMessage.objects.filter(
        bot=config, remote_jid=remoteJid
    ).order_by('received_at')

    total = historial.count()
    if total > 1:
        historial_previo = historial[max(0, total - 21): total - 1]
    else:
        historial_previo = []

    # Construir system prompt con contexto de archivos y departamentos
    instrucciones = config.instrucciones_ia or ''
    context_text  = _load_context_from_bot(config)

    departamentos_disponibles = Departamento.objects.filter(owner=config.owner)
    dptos_texto = ''
    if departamentos_disponibles.exists():
        dptos_texto = '\n\nDEPARTAMENTOS DISPONIBLES PARA TRANSFERENCIA:\n'
        for dpto in departamentos_disponibles:
            desc = f' — {dpto.descripcion}' if dpto.descripcion else ''
            dptos_texto += f'- {dpto.nombre.lower()}{desc}\n'
        dptos_texto += (
            '\nCuando debas transferir usa exactamente:\n'
            '<<TRANSFERIR:nombre_departamento>>\n'
            'Donde nombre_departamento es uno de los listados arriba en minuscula.'
        )

    system_content = instrucciones.strip()
    if context_text:
        system_content += f'\n\nArchivos de contexto:\n{context_text}'
    if dptos_texto:
        system_content += dptos_texto

    # Construir messages con historial previo + mensaje actual
    messages_ia = [{'role': 'system', 'content': system_content}]
    for msg in historial_previo:
        if msg.message_text:
            messages_ia.append({'role': 'user',      'content': msg.message_text})
        if msg.reply_text:
            messages_ia.append({'role': 'assistant', 'content': msg.reply_text})
    messages_ia.append({'role': 'user', 'content': messageText})

    # Llamar DeepSeek
    api_key = config.api_key or ''
    reply   = 'Gracias por tu mensaje. En breve te respondemos.'

    if api_key and instrucciones:
        try:
            resp = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                json={'model': 'deepseek-chat', 'messages': messages_ia},
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                timeout=20
            )
            if resp.status_code == 200:
                reply = resp.json()['choices'][0]['message']['content'].strip()
                max_chars = getattr(config, 'max_response_chars', 1000)
                if max_chars and len(reply) > max_chars:
                    reply = reply[:max_chars].rsplit(' ', 1)[0] + '…'
            else:
                print(f'[DeepSeek] Error {resp.status_code}: {resp.text}')
        except Exception:
            import traceback
            print('[DeepSeek Exception]', traceback.format_exc())

    # Limpiar flags de transferencia del reply
    match_flag   = re.search(r'<<TRANSFERIR:([^>]+)>>', reply)
    match_simple = re.search(r'<<TRANSFERIR>>', reply)
    reply_limpio = re.sub(r'<<TRANSFERIR[^>]*>>', '', reply).strip()

    transferir  = bool(match_flag or match_simple)
    dpto_nombre = match_flag.group(1).strip() if match_flag else ''

    # Guardar respuesta en BD
    from django.utils.timezone import now
    ultimo = WhatsAppMessage.objects.filter(
        bot=config, remote_jid=remoteJid, reply_text__isnull=True
    ).order_by('-received_at').first()
    if ultimo:
        ultimo.reply_text = reply_limpio
        ultimo.replied    = True
        ultimo.replied_at = now()
        ultimo.save()

    # Procesar transferencia
    if transferir:
        try:
            agentes_destino = []
            if dpto_nombre:
                agentes_destino = list(Agente.objects.filter(
                    departamentos__nombre__iexact=dpto_nombre,
                    activo=True, owner=config.owner
                ))
            if not agentes_destino:
                agentes_destino = list(Agente.objects.filter(
                    activo=True, owner=config.owner
                ))

            historial_completo = WhatsAppMessage.objects.filter(
                bot=config, remote_jid=remoteJid
            ).order_by('received_at')

            resumen_lines = []
            for msg in historial_completo:
                if msg.message_text:
                    resumen_lines.append(f'Cliente: {msg.message_text}')
                if msg.reply_text:
                    resumen_lines.append(f'Bot: {msg.reply_text}')

            mensaje_agente = (
                f'NUEVA CONSULTA — {dpto_nombre or "General"}\n'
                f'Cliente: {pushName or remoteJid}\n'
                f'Numero: {remoteJid.replace("@s.whatsapp.net", "") if remoteJid else ""}\n\n'
                f'Resumen:\n' + '\n'.join(resumen_lines)
            )

            gateway = settings.WHATSAPP_GATEWAY_URL
            for agente in agentes_destino:
                numero = agente.numero_whatsapp.strip().replace('+','').replace(' ','').replace('-','')
                if not numero.isdigit() or len(numero) < 8:
                    continue
                try:
                    requests.post(
                        f'{gateway}/send',
                        json={
                            'number':  numero,
                            'message': mensaje_agente,
                            'user':    str(owner_id),
                            'slot':    str(slot) if slot else '0'
                        },
                        timeout=8
                    )
                    print(f'[Transferencia] Enviado a {agente.nombre}')
                except Exception as ex:
                    print(f'[Transferencia] Error enviando a {agente.nombre}:', ex)

            # Marcar como transferido
            WhatsAppMessage.objects.filter(
                bot=config, remote_jid=remoteJid
            ).update(transferido=True)

        except Exception:
            import traceback
            print('[Transferencia error]', traceback.format_exc())

    return JsonResponse({'remoteJid': remoteJid, 'reply': reply_limpio})

def send_message(request):
    """Recibe número y mensaje desde el panel y reenvía al gateway Node (/send).

    Soporta POST desde formulario tradicional o AJAX. Retorna JSON si es AJAX,
    o redirige de vuelta al panel con mensajes flash.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST allowed')

    number = request.POST.get('number')
    message = request.POST.get('message')
    from_url = request.META.get('HTTP_REFERER', '')
    is_config = 'configuracion' in from_url

    if not number or not message:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'Faltan campos number o message'}, status=400)
        messages.error(request, 'Faltan campos: número y mensaje')
        if is_config:
            return redirect('configuracion')
        return redirect('panel_control')

    gateway = settings.WHATSAPP_GATEWAY_URL
    try:
        resp = requests.post(f"{gateway}/send", json={'number': number, 'message': message}, timeout=8)
        resp.raise_for_status()
    except Exception as e:
        err = str(e)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': err}, status=500)
        messages.error(request, f'Error enviando mensaje: {err}')
        if is_config:
            return redirect('configuracion')
        return redirect('panel_control')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})

    messages.success(request, 'Mensaje enviado correctamente')
    if is_config:
        return redirect('configuracion')
    return redirect('panel_control')

def logout(request):
    request.session.flush()
    messages.info(request, 'Sesión cerrada')
    return redirect('login') 

def departamentos(request):
    user = _get_session_user(request)
    if not user:
        return redirect('login')
    dptos = Departamento.objects.filter(owner=user)
    return render(request, 'departamentos.html', {'departamentos': dptos, 'user': user})

def departamento_crear(request):
    user = _get_session_user(request)
    if not user:
        return redirect('login')
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        if nombre:
            Departamento.objects.create(nombre=nombre, descripcion=descripcion, owner=user)
            messages.success(request, 'Departamento creado.')
        return redirect('departamentos')
    return render(request, 'departamento_form.html', {'user': user})

def departamento_editar(request, dpto_id):
    user = _get_session_user(request)
    if not user:
        return redirect('login')
    try:
        dpto = Departamento.objects.get(id=dpto_id, owner=user)
    except Departamento.DoesNotExist:
        messages.error(request, 'Departamento no encontrado.')
        return redirect('departamentos')
    if request.method == 'POST':
        dpto.nombre = request.POST.get('nombre', '').strip()
        dpto.descripcion = request.POST.get('descripcion', '').strip()
        dpto.save()
        messages.success(request, 'Departamento actualizado.')
        return redirect('departamentos')
    return render(request, 'departamento_form.html', {'dpto': dpto, 'user': user})

def departamento_eliminar(request, dpto_id):
    user = _get_session_user(request)
    if not user:
        return redirect('login')
    try:
        dpto = Departamento.objects.get(id=dpto_id, owner=user)
        dpto.delete()
        messages.success(request, 'Departamento eliminado.')
    except Departamento.DoesNotExist:
        messages.error(request, 'Departamento no encontrado.')
    return redirect('departamentos')


def agentes(request):
    user = _get_session_user(request)
    if not user:
        return redirect('login')
    agentes_list = Agente.objects.filter(owner=user).prefetch_related('departamentos')
    return render(request, 'agentes.html', {'agentes': agentes_list, 'user': user})

def agente_crear(request):
    user = _get_session_user(request)
    if not user:
        return redirect('login')
    dptos = Departamento.objects.filter(owner=user)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        numero = request.POST.get('numero_whatsapp', '').strip()
        activo = request.POST.get('activo') == 'on'
        dptos_ids = request.POST.getlist('departamentos')
        agente = Agente.objects.create(
            nombre=nombre,
            numero_whatsapp=numero,
            activo=activo,
            owner=user
        )
        dptos = Departamento.objects.filter(id__in=dptos_ids, owner=user)
        agente.departamentos.set(dptos)
        messages.success(request, 'Agente creado.')
        return redirect('agentes')
    return render(request, 'agente_form.html', {'departamentos': dptos, 'user': user})

def agente_editar(request, agente_id):
    user = _get_session_user(request)
    if not user:
        return redirect('login')
    try:
        agente = Agente.objects.get(id=agente_id, owner=user)
    except Agente.DoesNotExist:
        messages.error(request, 'Agente no encontrado.')
        return redirect('agentes')
    dptos = Departamento.objects.filter(owner=user)
    if request.method == 'POST':
        agente.nombre = request.POST.get('nombre', '').strip()
        agente.numero_whatsapp = request.POST.get('numero_whatsapp', '').strip()
        agente.activo = request.POST.get('activo') == 'on'
        dptos_ids = request.POST.getlist('departamentos')
        dptos = Departamento.objects.filter(id__in=dptos_ids, owner=user)
        agente.departamentos.set(dptos)
        agente.save()
        messages.success(request, 'Agente actualizado.')
        return redirect('agentes')
    return render(request, 'agente_form.html', {'agente': agente, 'departamentos': dptos, 'user': user})

def agente_eliminar(request, agente_id):
    user = _get_session_user(request)
    if not user:
        return redirect('login')
    try:
        agente = Agente.objects.get(id=agente_id, owner=user)
        agente.delete()
        messages.success(request, 'Agente eliminado.')
    except Agente.DoesNotExist:
        messages.error(request, 'Agente no encontrado.')
    return redirect('agentes')

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def reset_chat(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST allowed')
    
    session_key = request.session.session_key
    if session_key:
        bot = _get_public_bot()
        if bot:
            WhatsAppMessage.objects.filter(
                bot=bot,
                remote_jid=session_key
            ).delete()
    
    return JsonResponse({'ok': True})

def _generar_pdf_consulta(historial, datos_cliente, plan, departamento, resumen_ia=''):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from io import BytesIO
    from django.utils.timezone import now
    import random

    buffer = BytesIO()
    fecha = now().strftime('%d/%m/%Y %H:%M')
    referencia = now().strftime('%Y%m%d') + str(random.randint(100, 999))

    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=0.75*inch, leftMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)

    AZUL  = colors.HexColor("#1B3D6E")
    VERDE = colors.HexColor("#4A9A3C")
    GRIS  = colors.HexColor("#F5F5F5")

    estilos = getSampleStyleSheet()
    h1    = ParagraphStyle('h1', fontSize=14, textColor=AZUL,
                           fontName='Helvetica-Bold', spaceAfter=4, alignment=TA_CENTER)
    h2    = ParagraphStyle('h2', fontSize=11, textColor=VERDE,
                           fontName='Helvetica-Bold', spaceAfter=3, spaceBefore=8)
    body  = ParagraphStyle('body', fontSize=9, fontName='Helvetica',
                           leading=13, spaceAfter=3)
    small = ParagraphStyle('small', fontSize=8, fontName='Helvetica',
                           textColor=colors.grey, alignment=TA_CENTER)

    def hr():
        return HRFlowable(width='100%', thickness=1, color=VERDE, spaceAfter=6)

    story = []

    # Encabezado
    story.append(Paragraph("SyA Group — Resumen de Consulta", h1))
    story.append(Paragraph(f"Referencia: {referencia} · Fecha: {fecha}", small))
    story.append(hr())

    # Datos del cliente
    story.append(Paragraph("Datos del Cliente", h2))
    campos = [
        ("Nombre",    datos_cliente.get('nombre')    or 'No proporcionado'),
        ("Correo",    datos_cliente.get('correo')    or 'No proporcionado'),
        ("Teléfono",  datos_cliente.get('telefono')  or 'No proporcionado'),
        ("Empresa",   datos_cliente.get('empresa')   or 'Particular'),
        ("Departamento", departamento or 'General'),
        ("Interés",   plan or 'No especificado'),
    ]
    tbl = Table(campos, colWidths=[1.5*inch, 5.0*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(0,-1), colors.HexColor("#EAF4E8")),
        ("FONTNAME",      (0,0),(0,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("BOX",           (0,0),(-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, colors.HexColor("#DDDDDD")),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
    ]))
    story.append(tbl)

    # Resumen IA
    if resumen_ia:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Resumen del Perfil", h2))
        story.append(Paragraph(resumen_ia, body))

    # Historial
    story.append(Spacer(1, 8))
    story.append(hr())
    story.append(Paragraph("Historial de Conversación", h2))
    for msg in historial:
        if msg.message_text:
            story.append(Paragraph(
                f"<b>Cliente:</b> {msg.message_text[:300]}", body))
        if msg.reply_text:
            story.append(Paragraph(
                f"<b>Bot:</b> {msg.reply_text[:300]}", body))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Documento generado automáticamente por SyA Group Bot", small))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    if not pdf_bytes:
        raise Exception("PDF vacío generado")
    return pdf_bytes


@require_POST
def queue_drain(request):
    """Fuerza el drenado de la cola de mensajes pendientes del gateway."""
    user = _get_session_user(request)
    if not user:
        return JsonResponse({'ok': False, 'error': 'No autenticado'}, status=401)

    bot = ConfigBot.objects.filter(owner=user).first()
    if not bot:
        return JsonResponse({'ok': False, 'error': 'No hay bot configurado'}, status=400)

    gateway = settings.WHATSAPP_GATEWAY_URL
    try:
        resp = requests.post(
            f"{gateway}/queue/drain",
            params={'user': user.id, 'slot': bot.id},
            timeout=5
        )
        data = resp.json()
        return JsonResponse({'ok': data.get('ok', False), 'message': data.get('message', '')})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def queue_status(request):
    """Devuelve el número de mensajes pendientes en la cola del gateway."""
    user = _get_session_user(request)
    if not user:
        return JsonResponse({'ok': False, 'error': 'No autenticado'}, status=401)

    bot = ConfigBot.objects.filter(owner=user).first()
    if not bot:
        return JsonResponse({'ok': False, 'pending': 0})

    gateway = settings.WHATSAPP_GATEWAY_URL
    try:
        resp = requests.get(
            f"{gateway}/status",
            params={'user': user.id, 'slot': bot.id},
            timeout=3
        )
        data = resp.json()
        return JsonResponse({
            'ok': True,
            'status': data.get('status', 'unknown'),
            'pending': data.get('pending_messages', 0),
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'pending': 0, 'error': str(e)})
    
def conversaciones(request):
    user = _get_session_user(request)
    if not user:
        return redirect('login')

    bot = ConfigBot.objects.filter(owner=user).first()
    if not bot:
        return render(request, 'conversaciones.html', {'conversaciones': [], 'user': user})

    from django.db.models import Max, Count
    convs = WhatsAppMessage.objects.filter(bot=bot).values(
        'remote_jid', 'push_name'
    ).annotate(
        ultimo_mensaje=Max('received_at'),
        total_mensajes=Count('id'),
        transferido=Max('transferido')
    ).order_by('-ultimo_mensaje')

    return render(request, 'conversaciones.html', {
        'conversaciones': convs,
        'user': user,
        'bot': bot
    })


def conversacion_detalle(request, remote_jid):
    user = _get_session_user(request)
    if not user:
        return redirect('login')

    bot = ConfigBot.objects.filter(owner=user).first()
    if not bot:
        return redirect('conversaciones')

    import urllib.parse
    remote_jid_decoded = urllib.parse.unquote(remote_jid)

    mensajes = WhatsAppMessage.objects.filter(
        bot=bot, remote_jid=remote_jid_decoded
    ).order_by('received_at')

    return render(request, 'conversacion_detalle.html', {
        'mensajes': mensajes,
        'remote_jid': remote_jid_decoded,
        'user': user,
        'bot': bot
    })
    
def perfil(request):
    user = _get_session_user(request)
    if not user:
        return redirect('login')

    if request.method == 'POST':
        nuevo_nombre = request.POST.get('nombre', '').strip()
        password_actual = request.POST.get('password_actual', '')
        nuevo_password = request.POST.get('nuevo_password', '').strip()
        confirmar_password = request.POST.get('confirmar_password', '').strip()

        if nuevo_nombre and nuevo_nombre != user.nombre:
            if User_admin.objects.filter(nombre=nuevo_nombre).exclude(id=user.id).exists():
                messages.error(request, 'Ese nombre de usuario ya está en uso.')
                return redirect('perfil')
            user.nombre = nuevo_nombre
            user.save()
            messages.success(request, 'Nombre actualizado correctamente.')

        if nuevo_password:
            from django.contrib.auth.hashers import check_password, make_password
            if not (check_password(password_actual, user.password) or user.password == password_actual):
                messages.error(request, 'Contraseña actual incorrecta.')
                return redirect('perfil')
            if nuevo_password != confirmar_password:
                messages.error(request, 'Las contraseñas nuevas no coinciden.')
                return redirect('perfil')
            if len(nuevo_password) < 6:
                messages.error(request, 'La contraseña debe tener al menos 6 caracteres.')
                return redirect('perfil')
            user.password = make_password(nuevo_password)
            user.save()
            messages.success(request, 'Contraseña actualizada correctamente.')

        return redirect('perfil')

    return render(request, 'perfil.html', {'user': user})