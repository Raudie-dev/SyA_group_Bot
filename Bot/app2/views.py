from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.http import JsonResponse
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from .models import User_admin, IAAPI, UserIAAccess
from app1.models import User
from . import crud



def login_admin(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        password = request.POST.get('password', '')

        try:
            user = User_admin.objects.get(nombre=nombre)
            if user.bloqueado:
                messages.error(request, 'Usuario bloqueado')
            elif user.password == password or check_password(password, user.password):
                request.session['user_admin_id'] = user.id
                return redirect('usuarios_control')
            else:
                messages.error(request, 'Contraseña incorrecta')
            return render(request, 'login.html')
        except User_admin.DoesNotExist:
            messages.error(request, 'Usuario no encontrado')
            return render(request, 'login.html')

    return render(request, 'login.html')


def usuarios_control(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'bloquear':
            user_id = request.POST.get('user_id')
            if user_id:
                bloqueado = crud.bloquear_usuario(user_id)
                messages.success(request, f"Usuario {'bloqueado' if bloqueado else 'desbloqueado'}")
            else:
                messages.error(request, 'ID de usuario requerido')
        elif action == 'eliminar':
            user_id = request.POST.get('user_id')
            if user_id:
                crud.eliminar_usuario(user_id)
                messages.success(request, 'Usuario eliminado')
            else:
                messages.error(request, 'ID de usuario requerido')
        else:
            messages.error(request, 'Acción no válida')
        return redirect('usuarios_control')

    usuarios = User.objects.all()
    return render(request, 'usuarios_control.html', {'usuarios': usuarios})


def usuarios_edit_create(request, user_id=None):
    user_obj = None
    if user_id:
        try:
            user_obj = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, 'Usuario no encontrado')
            return redirect('usuarios_control')

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        password = request.POST.get('password', '')
        email = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        plan = request.POST.get('plan', user_obj.plan if user_obj else 'base')

        if not nombre:
            messages.error(request, 'El nombre es obligatorio')
        elif user_obj:
            try:
                crud.editar_usuario(user_obj.id, nombre, password, email, telefono, plan)
                messages.success(request, 'Usuario actualizado correctamente')
                return redirect('usuarios_control')
            except IntegrityError as e:
                messages.error(request, f'No se pudo actualizar el usuario: {e}')
        else:
            if not password:
                messages.error(request, 'Contraseña es obligatoria para crear un usuario')
            else:
                try:
                    crud.crear_usuario(nombre, password, email, telefono, plan)
                    messages.success(request, 'Usuario creado correctamente')
                    return redirect('usuarios_control')
                except IntegrityError as e:
                    messages.error(request, f'No se pudo crear el usuario: {e}')

    return render(request, 'usuarios_edit_create.html', {
        'user': user_obj,
        'plans': User.PLAN_CHOICES,
    })

@csrf_exempt
def iaapi_control(request):
    """
    Vista de administración de APIs de IA y acceso de usuarios.
    Permite:
    - Ver y editar las APIs disponibles (DeepSeek, ChatGPT, Gemini, EasyBot)
    - Asignar/quitar acceso a usuarios
    - Cargar la API EasyBot (proxy)
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'toggle_api':
            api_id = request.POST.get('api_id')
            api = IAAPI.objects.get(id=api_id)
            api.activo = not api.activo
            api.save()
            return JsonResponse({'success': True, 'activo': api.activo})
        elif action == 'set_user_access':
            user_id = request.POST.get('user_id')
            api_id = request.POST.get('api_id')
            enabled = request.POST.get('enabled') == 'true'
            user = User.objects.get(id=user_id)
            api = IAAPI.objects.get(id=api_id)
            access, _ = UserIAAccess.objects.get_or_create(user=user, api=api)
            access.enabled = enabled
            access.save()
            return JsonResponse({'success': True, 'enabled': access.enabled})
        elif action == 'set_user_api_key':
            user_id = request.POST.get('user_id')
            api_id = request.POST.get('api_id')
            user_api_key = request.POST.get('user_api_key', '').strip()
            user = User.objects.get(id=user_id)
            api = IAAPI.objects.get(id=api_id)
            access, _ = UserIAAccess.objects.get_or_create(user=user, api=api)
            access.user_api_key = user_api_key
            access.save()
            return JsonResponse({'success': True})
        elif action == 'set_easybot_api':
            # Permite cargar la API EasyBot (proxy)
            api = IAAPI.objects.get(nombre='easybot')
            api.url = request.POST.get('url', '').strip()
            api.save()
            return JsonResponse({'success': True, 'url': api.url})
        else:
            return JsonResponse({'success': False, 'msg': 'Acción no válida'})
    # GET: mostrar panel
    apis = list(IAAPI.objects.all())
    usuarios = list(User.objects.all())
    # Generar una lista de accesos por usuario, para evitar filtros en el template
    user_access_list = []
    all_access = {(a.user_id, a.api_id): a for a in UserIAAccess.objects.all()}
    for user in usuarios:
        access_row = {'user': user, 'apis': []}
        for api in apis:
            acc = all_access.get((user.id, api.id))
            access_row['apis'].append({
                'api': api,
                'enabled': acc.enabled if acc else False,
                'user_api_key': acc.user_api_key if acc else ''
            })
        user_access_list.append(access_row)
    return render(request, 'iaapi_control.html', {
        'apis': apis,
        'user_access_list': user_access_list
    })
