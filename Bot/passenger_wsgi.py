import os
import sys

# Ruta al proyecto
sys.path.insert(0, '/home/sbxp03tfgozj/repos/SyA_group_Bot-master/Bot')

# Variables de entorno
os.environ['DJANGO_SETTINGS_MODULE'] = 'proyecto.settings'

# WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()