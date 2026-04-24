
from app1.models import Prueba, User

def crear_prueba(nombre, fecha, socio=True):
    return Prueba.objects.create(nombre=nombre, fecha=fecha, socio=socio)

def obtener_pruebas():
    return Prueba.objects.all()

def eliminar_prueba(prueba_id):
    Prueba.objects.filter(id=prueba_id).delete()

def actualizar_prueba(prueba_id, nombre=None, fecha=None, socio=None):
    prueba = Prueba.objects.get(id=prueba_id)
    if nombre is not None:
        prueba.nombre = nombre
    if fecha is not None:
        prueba.fecha = fecha
    if socio is not None:
        prueba.socio = socio
    prueba.save()
    return prueba


# CRUD para usuarios de app1

def crear_usuario(nombre, password, email=None, telefono=None, plan='base'):
    return User.objects.create(nombre=nombre, password=password, email=email, telefono=telefono, plan=plan)


def editar_usuario(user_id, nombre=None, password=None, email=None, telefono=None, plan=None):
    user = User.objects.get(id=user_id)
    if nombre is not None:
        user.nombre = nombre
    if password:
        user.password = password
    if email is not None:
        user.email = email
    if telefono is not None:
        user.telefono = telefono
    if plan is not None:
        user.plan = plan
    user.save()
    return user

def bloquear_usuario(user_id):
    user = User.objects.get(id=user_id)
    user.bloqueado = not user.bloqueado
    user.save()
    return user.bloqueado

def eliminar_usuario(user_id):
    user = User.objects.get(id=user_id)
    user.delete()
    return True