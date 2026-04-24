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
    return render(request, 'index.html', {'user': user})

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

        if bot:
            bot.nombre = nombre
            bot.mensaje_bienvenida = mensaje_bienvenida
            bot.instrucciones_ia = instrucciones_ia
            bot.api_key = api_key
            bot.save()
            messages.success(request, 'Configuración del bot actualizada correctamente.')
        else:
            bot = ConfigBot.objects.create(
                nombre=nombre,
                owner=user,
                mensaje_bienvenida=mensaje_bienvenida,
                instrucciones_ia=instrucciones_ia,
                api_key=api_key
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
    return render(request, 'create_edit_bot.html', {
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
        try:
            resp = requests.post(f"{gateway}/generate", params={'user': user.id, 'slot': bot.id}, timeout=5)
            if resp.status_code == 200:
                messages.info(request, 'Se ha solicitado la generación de un nuevo QR. Espere unos segundos.')
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
    """Devuelve el último QR almacenado como JSON (útil para polling desde el frontend)."""
    user = _get_session_user(request)
    if not user:
        return JsonResponse({'error': 'No autorizado'}, status=401)

    bot_id = request.GET.get('bot_id')
    if not bot_id:
        return JsonResponse({'error': 'bot_id requerido'}, status=400)

    try:
        bot = ConfigBot.objects.get(id=bot_id, owner=user)
        session = WhatsAppSession.objects.filter(bot=bot).order_by('-updated_at').first()
        qr = session.qr_string if session else None
        return JsonResponse({'qr': qr})
    except ConfigBot.DoesNotExist:
        return JsonResponse({'error': 'Bot no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'qr': None, 'error': str(e)})


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


def public_chat(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST allowed')

    message = request.POST.get('message', '').strip()
    if not message:
        return JsonResponse({'ok': False, 'error': 'Mensaje vacío'}, status=400)

    bot = _get_public_bot()
    if not bot:
        return JsonResponse({'ok': False, 'error': 'No hay un bot configurado para chat público.'}, status=500)

    if not bot.api_key or not bot.instrucciones_ia:
        return JsonResponse({'ok': False, 'error': 'Chat no disponible: bot sin configuración de IA.'}, status=500)

    context_text = _load_context_from_bot(bot)
    system_prompt = bot.instrucciones_ia.strip() or 'Eres un asistente virtual enfocado en brindar asesoría ambiental.'
    user_prompt = f"Usuario: {message}"
    if bot.mensaje_bienvenida:
        user_prompt = f"{bot.mensaje_bienvenida}\n\n{user_prompt}"
    if context_text:
        user_prompt = f"{user_prompt}\n\nArchivos de contexto disponibles:\n{context_text}"

    payload = {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]
    }

    try:
        resp = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json=payload,
            headers={
                'Authorization': f'Bearer {bot.api_key}',
                'Content-Type': 'application/json'
            },
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Error en la API de IA: {e}'}, status=500)

    reply = None
    if isinstance(data, dict):
        choices = data.get('choices')
        if choices and isinstance(choices, list):
            choice = choices[0]
            if isinstance(choice, dict):
                if 'message' in choice and isinstance(choice['message'], dict):
                    reply = choice['message'].get('content')
                elif 'text' in choice:
                    reply = choice.get('text')
        if not reply:
            reply = data.get('reply') or data.get('output')

    if not reply:
        return JsonResponse({'ok': False, 'error': 'Respuesta inválida desde la API de IA.'}, status=500)

    return JsonResponse({'ok': True, 'reply': reply})


@csrf_exempt
def whatsapp_webhook(request):
    """Webhook que recibe mensajes desde el servicio Node.js.

    Espera un POST JSON con: remoteJid, pushName, messageText
    Retorna JSON con la respuesta que Node.js deberá reenviar al usuario.
    """
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
            parts = str(session).split(':', 1)
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

    # WhatsApp: NO usar contexto de archivos, solo instrucciones y mensaje
    system_prompt = instrucciones.strip() if instrucciones else 'Eres un asistente virtual enfocado en brindar asesoría ambiental.'
    user_prompt = f"Usuario: {messageText}"
    if bienvenida:
        user_prompt = f"{bienvenida}\n\n{user_prompt}"

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
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
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

    # Formato de respuesta que Node.js espera reenviar
    response = {
        'remoteJid': remoteJid,
        'reply': reply,
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