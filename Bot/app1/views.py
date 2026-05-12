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
    gateway = getattr(settings, 'WHATSAPP_GATEWAY_URL', 'http://127.0.0.1:3000')

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
            messages.success(request, 'Configuración del bot actualizada correctamente.')
            return redirect('configuracion')
        else:
            bot = ConfigBot.objects.create(
                nombre=nombre,
                owner=user,
                mensaje_bienvenida=mensaje_bienvenida,
                instrucciones_ia=instrucciones_ia,
                api_key=api_key,
                api_provider=api_provider
            )
            messages.success(request, 'Bot configurado correctamente. Ahora puedes conectar WhatsApp cuando quieras.')

        if 'context_files' in request.FILES:
            files = request.FILES.getlist('context_files')
            for file in files:
                allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx']
                if not any(file.name.lower().endswith(ext) for ext in allowed_extensions):
                    messages.error(request, f'Archivo {file.name} no permitido. Solo PDF, Word y Excel.')
                    continue
                ContextFile.objects.create(bot=bot, file=file)
            messages.success(request, f'Subidos {len([f for f in files if any(f.name.lower().endswith(ext) for ext in allowed_extensions)])} archivos de contexto.')

        delete_files = request.POST.getlist('delete_files')
        for file_id in delete_files:
            try:
                context_file = ContextFile.objects.get(id=file_id, bot=bot)
                context_file.file.delete()
                context_file.delete()
                messages.success(request, f'Archivo {context_file.file.name} eliminado.')
            except ContextFile.DoesNotExist:
                pass

    bot_status = 'unknown'
    return render(request, 'configuracion.html', {
        'bot': bot,
        'bot_status': bot_status,
        'user': user,
        'context_files': bot.context_files.all() if bot else []
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

    gateway = getattr(settings, 'WHATSAPP_GATEWAY_URL', 'http://127.0.0.1:3000')
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

    gateway = getattr(settings, 'WHATSAPP_GATEWAY_URL', 'http://127.0.0.1:3000')
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

def _generar_pdf_consulta(historial, datos_cliente, plan, departamento, resumen_ia=''):
    from weasyprint import HTML
    from io import BytesIO
    from django.template.loader import render_to_string
    from django.utils.timezone import now
    import random

    fecha = now().strftime('%d/%m/%Y %H:%M')
    referencia = now().strftime('%Y%m%d') + str(random.randint(100, 999))

    html = render_to_string('pdf_consulta.html', {
        'datos': datos_cliente,
        'plan': plan,
        'departamento': departamento,
        'resumen_ia': resumen_ia,
        'historial': historial,
        'fecha': fecha,
        'referencia': referencia,
    })

    try:
        pdf_bytes = HTML(string=html).write_pdf()
    except Exception as e:
        raise Exception(f"Error generando PDF (weasyprint): {e}")

    if not pdf_bytes:
        raise Exception("PDF vacío generado")
    
    return pdf_bytes

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
    gateway = getattr(settings, 'WHATSAPP_GATEWAY_URL', 'http://127.0.0.1:3000')
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
    message = re.sub(r'<<TRANSFERIR[^>]*>>', '', message).strip()
    message = re.sub(r'<<[A-Z_]+[^>]*>>', '', message).strip()

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
    except Exception as e:
        print('[DeepSeek error]', e)
        return JsonResponse({'ok': False, 'error': f'Error IA: {e}'}, status=500)

    # Detectar flag de transferencia
    import re
    import json as json_mod
    import base64

    match = re.search(r'<<TRANSFERIR:([^>]+)>>', raw_reply)
    match_simple = re.search(r'<<TRANSFERIR>>', raw_reply)
    reply_limpio = re.sub(r'<<TRANSFERIR:[^>]+>>', '', raw_reply).strip()
    reply_limpio = re.sub(r'<<TRANSFERIR>>', '', reply_limpio).strip()

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
    if match or match_simple:
        dpto_nombre = match.group(1).strip() if match else ''
        print('[DEBUG] Transferencia activada, dpto:', dpto_nombre)

        try:
            # Validar que la IA haya recopilado los datos minimos
            # Revisar en el historial si existen nombre, correo y telefono
            conv_check = ""
            for msg in WhatsAppMessage.objects.filter(
                bot=bot, remote_jid=session_key
            ).order_by('received_at'):
                if msg.message_text:
                    conv_check += msg.message_text + " "
                if msg.reply_text:
                    conv_check += msg.reply_text + " "

            tiene_correo   = bool(re.search(r'[\w.-]+@[\w.-]+\.\w+', conv_check))
            tiene_telefono = bool(re.search(r'[\+\d][\d\s\-]{7,}', conv_check))
            tiene_nombre   = len(conv_check.strip().split()) > 10  # al menos una conversacion real

            if not (tiene_correo and tiene_telefono and tiene_nombre):
                print('[Transferencia] Datos insuficientes, bloqueando transferencia.')
                WhatsAppMessage.objects.filter(
                    bot=bot, remote_jid=session_key
                ).filter(reply_text__isnull=True).update(
                    reply_text=reply_limpio, replied=True
                )
                return JsonResponse({'ok': True, 'reply': reply_limpio})
            # Buscar todos los agentes activos del departamento
            agentes_destino = []
            if dpto_nombre:
                agentes_destino = list(Agente.objects.filter(
                    departamentos__nombre__iexact=dpto_nombre,
                    activo=True,
                    owner=bot.owner
                ).prefetch_related('departamentos'))
                print(f'[DEBUG] Agentes en dpto "{dpto_nombre}":', [a.nombre for a in agentes_destino])

            # Fallback: todos los agentes activos del owner
            if not agentes_destino:
                agentes_destino = list(Agente.objects.filter(
                    activo=True,
                    owner=bot.owner
                ).prefetch_related('departamentos'))
                print('[DEBUG] Agentes fallback:', [a.nombre for a in agentes_destino])

            if not agentes_destino:
                print('[Transferencia] Sin agentes activos disponibles')
            else:
                # Recargar historial completo para resumen y PDF
                historial_completo = WhatsAppMessage.objects.filter(
                    bot=bot,
                    remote_jid=session_key
                ).order_by('received_at')

                # Construir texto de conversacion para extraccion de datos
                conv_texto = ""
                for msg in historial_completo:
                    if msg.message_text:
                        conv_texto += f"Cliente: {msg.message_text}\n"
                    if msg.reply_text:
                        conv_texto += f"Bot: {msg.reply_text}\n"

                # Extraer datos del cliente via IA
                datos_cliente = {
                    'nombre': '', 'correo': '', 'telefono': '',
                    'empresa': '', 'plan_interes': '', 'volumen_reportes': ''
                }
                try:
                    extraction_resp = requests.post(
                        'https://api.deepseek.com/v1/chat/completions',
                        json={
                            "model": "deepseek-chat",
                            "messages": [
                                {"role": "system", "content": (
                                    "Eres un extractor de datos. A partir de la conversacion extrae "
                                    "los datos del cliente en JSON con claves exactas: "
                                    "nombre, correo, telefono, empresa, plan_interes, volumen_reportes. "
                                    "Si un dato no aparece usa string vacio. "
                                    "Responde SOLO el JSON sin markdown ni explicaciones."
                                )},
                                {"role": "user", "content": conv_texto}
                            ]
                        },
                        headers={
                            'Authorization': f'Bearer {bot.api_key}',
                            'Content-Type': 'application/json'
                        },
                        timeout=15
                    )
                    if extraction_resp.status_code == 200:
                        raw = extraction_resp.json()['choices'][0]['message']['content']
                        raw = raw.strip().strip('```json').strip('```').strip()
                        datos_cliente = json_mod.loads(raw)
                        print('[DEBUG] Datos extraidos:', datos_cliente)
                except Exception as ex:
                    print('[Extraccion datos error]', ex)

                plan_interes = datos_cliente.get('plan_interes') or 'No especificado'

                # Generar PDF
                pdf_b64 = None
                filename = 'consulta.pdf'
                resumen_ia = ''
                try:
                    resumen_resp = requests.post(
                        'https://api.deepseek.com/v1/chat/completions',
                        json={
                            "model": "deepseek-chat",
                            "messages": [
                                {"role": "system", "content": (
                                    "Eres un asistente de ventas. Resume en 2-3 oraciones "
                                    "el perfil del cliente y su necesidad principal, "
                                    "destacando urgencia y oportunidad comercial. "
                                    "Sin markdown, texto plano."
                                )},
                                {"role": "user", "content": conv_texto}
                            ]
                        },
                        headers={
                            'Authorization': f'Bearer {bot.api_key}',
                            'Content-Type': 'application/json'
                        },
                        timeout=10
                    )
                    if resumen_resp.status_code == 200:
                        resumen_ia = resumen_resp.json()['choices'][0]['message']['content'].strip()
                        print('[DEBUG] Resumen IA:', resumen_ia)
                except Exception as ex:
                    print('[Resumen IA error]', ex)

                try:
                    pdf_bytes = _generar_pdf_consulta(
                        historial_completo, datos_cliente, plan_interes,
                        dpto_nombre or 'General', resumen_ia
                    )
                    pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
                    nombre_archivo = datos_cliente.get('nombre', 'cliente').replace(' ', '_')
                    filename = f"consulta_{nombre_archivo}.pdf"
                    print(f'[DEBUG] PDF generado: {len(pdf_bytes)} bytes')
                except Exception as ex:
                    print('[PDF error]', ex)

                # Construir mensaje estructurado
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
                    f"Plan de interes:    {plan_interes}\n"
                    f"Volumen reportes:   {datos_cliente.get('volumen_reportes') or 'No especificado'}\n\n"
                    f"Historial completo adjunto en PDF."
                )

                # Enviar a todos los agentes del departamento
                for agente in agentes_destino:
                    numero = agente.numero_whatsapp.strip().replace('+', '').replace(' ', '').replace('-', '')
                    if not numero.isdigit() or len(numero) < 8:
                        print(f'[Transferencia] Numero invalido para {agente.nombre}: {numero}')
                        continue

                    print(f'[DEBUG] Enviando a {agente.nombre} — {numero}')
                    try:
                        if pdf_b64:
                            gw_resp = requests.post(
                                f"{gateway}/send-doc",
                                json={
                                    'number': numero,
                                    'message': mensaje_agente,
                                    'filename': filename,
                                    'filedata': pdf_b64,
                                    'user': str(bot.owner_id),
                                    'slot': str(bot.id)
                                },
                                timeout=20
                            )
                        else:
                            gw_resp = requests.post(
                                f"{gateway}/send",
                                json={
                                    'number': numero,
                                    'message': mensaje_agente,
                                    'user': str(bot.owner_id),
                                    'slot': str(bot.id)
                                },
                                timeout=10
                            )
                        print(f'[DEBUG] Gateway resp para {agente.nombre}: {gw_resp.status_code} {gw_resp.text}')
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
    """Webhook que recibe mensajes desde el servicio Node.js.

    Espera un POST JSON con: remoteJid, pushName, messageText
    Retorna JSON con la respuesta que Node.js deberá reenviar al usuario.
    """

    secret = request.headers.get('X-Webhook-Secret', '')
    if secret != getattr(settings, 'WEBHOOK_SECRET', ''):
        return JsonResponse({'error': 'No autorizado'}, status=401)

    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST allowed')

    try:
        payload = request.body
        data = request.json if False else None
    except Exception:
        data = None

    # prefer json parsing via request.POST or request.body
    try:
        data = request.headers.get('Content-Type', '').startswith('application/json') and request.json if hasattr(request, 'json') else None
    except Exception:
        data = None

    # fallback: use Django's json parsing
    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    remoteJid = data.get('remoteJid')
    pushName = data.get('pushName')
    messageText = data.get('messageText', '')

    owner_id = None
    slot = None
    try:
        owner_id = data.get('owner') or None
        session = data.get('session')
        if session:
            parts = str(session).split('_', 1)
            owner_id = parts[0]
            if len(parts) > 1:
                slot = parts[1]
        if owner_id is not None:
            try:
                owner_id = int(owner_id)
            except Exception:
                owner_id = None
        if slot is not None:
            try:
                slot = int(slot)
            except Exception:
                slot = None
    except Exception:
        owner_id = None
        slot = None

    config = None
    if owner_id and slot:
        config = ConfigBot.objects.filter(owner__id=owner_id, id=slot).first()
    elif owner_id:
        config = ConfigBot.objects.filter(owner__id=owner_id).first()
    if not config:
        config = ConfigBot.objects.filter(owner__isnull=True).first()

    # Guardar mensaje entrante en la base de datos para revisión desde el panel
    try:
        if config:
            WhatsAppMessage.objects.create(bot=config, remote_jid=remoteJid or '', push_name=pushName or '', message_text=messageText or '')
    except Exception:
        # no bloquear el webhook por fallos de persistencia
        pass

    instrucciones = config.instrucciones_ia if config else ''
    bienvenida = config.mensaje_bienvenida if config else 'Hola'
    api_key = config.api_key if config else ''

    # Historial de conversacion
    historial = WhatsAppMessage.objects.filter(
        bot=config,
        remote_jid=remoteJid
    ).order_by('received_at')

    # Verificar si ya fue transferido
    if historial.filter(transferido=True).exists():
        return JsonResponse({'remoteJid': remoteJid, 'reply': ''})

    # Construir mensajes con historial
    messages_ia = [{"role": "system", "content": instrucciones}]
    for msg in historial:
        if msg.message_text:
            messages_ia.append({"role": "user", "content": msg.message_text})
        if msg.reply_text:
            messages_ia.append({"role": "assistant", "content": msg.reply_text})
    messages_ia.append({"role": "user", "content": messageText})

    # Siempre responder usando DeepSeek API
    reply = 'Gracias por tu mensaje. En breve te respondemos.'
    if api_key and instrucciones:
        try:
            deepseek_url = 'https://api.deepseek.com/v1/chat/completions'
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }
            payload = {
                "model": "deepseek-chat",
                "messages": messages_ia
            }
            resp = requests.post(deepseek_url, json=payload, headers=headers, timeout=15)
            # Log para depuración
            print("[DeepSeek] status:", resp.status_code)
            print("[DeepSeek] response:", resp.text)
            if resp.status_code == 200:
                data = resp.json()
                if 'choices' in data and data['choices'] and 'message' in data['choices'][0]:
                    reply = data['choices'][0]['message']['content'].strip()
                else:
                    reply = '[DeepSeek error] Respuesta inesperada: ' + str(data)
            else:
                reply = f"[DeepSeek error {resp.status_code}] {resp.text}"
        except Exception as e:
            import traceback
            print('[DeepSeek Exception]', traceback.format_exc())
            reply = f"[Error DeepSeek] {e}"

    # Detectar si la IA decidio transferir
    TRANSFER_FLAG = '<<TRANSFERIR>>'
    transferir = TRANSFER_FLAG in reply
    reply_limpio = reply.replace(TRANSFER_FLAG, '').strip()

    if transferir and config:
        try:
            # Buscar departamento y agente
            from .models import Agente
            import json as json_module

            # Extraer nombre de departamento del reply si la IA lo indica
            # Formato esperado: <<TRANSFERIR:nombre_departamento>>
            dpto_nombre = None
            import re
            match = re.search(r'<<TRANSFERIR:([^>]+)>>', reply)
            if match:
                dpto_nombre = match.group(1).strip()
                reply_limpio = re.sub(r'<<TRANSFERIR:[^>]+>>', '', reply).strip()

            agentes_destino = []
            if dpto_nombre:
                agentes_destino = list(Agente.objects.filter(
                    departamentos__nombre__iexact=dpto_nombre,
                    activo=True,
                    owner=config.owner
                ))
            if not agentes_destino:
                agentes_destino = list(Agente.objects.filter(
                    activo=True,
                    owner=config.owner
                ))

            # Construir resumen para el agente
            resumen_lines = []
            for msg in historial:
                if msg.message_text:
                    resumen_lines.append(f"Cliente: {msg.message_text}")
                if msg.reply_text:
                    resumen_lines.append(f"Bot: {msg.reply_text}")
            resumen_lines.append(f"Cliente: {messageText}")

            mensaje_agente = (
                f"NUEVA CONSULTA — {dpto_nombre or 'General'}\n"
                f"Cliente: {pushName or remoteJid}\n"
                f"Numero: {remoteJid.replace('@s.whatsapp.net', '') if remoteJid else ''}\n\n"
                f"Resumen:\n" + "\n".join(resumen_lines)
            )

            gateway = getattr(settings, 'WHATSAPP_GATEWAY_URL', 'http://127.0.0.1:3000')

            for agente in agentes_destino:
                numero = agente.numero_whatsapp.strip().replace('+','').replace(' ','').replace('-','')
                if not numero.isdigit() or len(numero) < 8:
                    continue
                try:
                    requests.post(
                        f"{gateway}/send",
                        json={
                            'number': numero,
                            'message': mensaje_agente,
                            'user': str(owner_id),
                            'slot': str(slot) if slot else '0'
                        },
                        timeout=8
                    )
                    print(f'[DEBUG] Enviado a {agente.nombre} — {numero}')
                except Exception as ex:
                    print(f'[Transferencia] Error enviando a {agente.nombre}:', ex)

            # Marcar conversacion como transferida
            WhatsAppMessage.objects.filter(
                bot=config,
                remote_jid=remoteJid
            ).update(transferido=True)

        except Exception as e:
            print('[Transferencia error]', e)

    response = {
        'remoteJid': remoteJid,
        'reply': reply_limpio,
    }

    return JsonResponse(response)

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

    gateway = getattr(settings, 'WHATSAPP_GATEWAY_URL', 'http://127.0.0.1:3000')
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