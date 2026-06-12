from django.db import models
class User(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128)
    bloqueado = models.BooleanField(default=False)
    email = models.EmailField(max_length=150, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    
    def __str__(self):
        return self.nombre
    
class ConfigBot(models.Model):
    """Configuración del bot WhatsApp y contexto de negocio/IA."""
    nombre = models.CharField(max_length=150, help_text='Nombre identificador del bot')
    owner = models.ForeignKey('User', on_delete=models.CASCADE, related_name='bots', null=True, blank=True)
    mensaje_bienvenida = models.CharField(max_length=500, blank=True, help_text='Mensaje de bienvenida al usuario')
    instrucciones_ia = models.TextField(blank=True, help_text='Prompt o instrucciones para la IA / lógica de negocio')
    API_PROVIDERS = [
        ('deepseek', 'DeepSeek'),
        ('openai', 'OpenAI'),
        ('gemini', 'Gemini'),
    ]
    api_provider = models.CharField(max_length=20, choices=API_PROVIDERS, default='deepseek', help_text='Proveedor de IA')
    api_key = models.TextField(blank=True, null=True, help_text='API Key del proveedor seleccionado (cifrada)')
    max_response_chars = models.IntegerField(default=1000, help_text='Límite de caracteres en respuestas del bot')
    mensaje_cierre = models.CharField(max_length=500, blank=True, default='', help_text='Mensaje al cerrar conversación por inactividad')
    inactividad_minutos = models.IntegerField(default=0, help_text='Minutos de inactividad para cerrar conversación (0 = desactivado)')

    def __str__(self):
        return self.nombre
    
class ContextFile(models.Model):
    """Archivos de contexto para el bot (PDF, Word, Excel)."""
    bot = models.ForeignKey(ConfigBot, on_delete=models.CASCADE, related_name='context_files')
    file = models.FileField(upload_to='context_files/', help_text='Archivo de contexto (PDF, DOC, DOCX, XLS, XLSX)')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.bot.nombre} - {self.file.name}"


class WhatsAppSession(models.Model):
    """Almacena el último QR recibido (string) y marca de tiempo."""
    bot = models.ForeignKey('ConfigBot', on_delete=models.CASCADE, related_name='sessions', null=True, blank=True)
    qr_string = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"WhatsAppSession for {self.bot.nombre if self.bot else 'None'} (updated: {self.updated_at})"


class WhatsAppMessage(models.Model):
    """Registra mensajes entrantes desde WhatsApp y su estado de respuesta."""
    bot = models.ForeignKey('ConfigBot', on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    remote_jid = models.CharField(max_length=200)
    push_name = models.CharField(max_length=200, blank=True, null=True)
    message_text = models.TextField(blank=True, null=True)
    received_at = models.DateTimeField(auto_now_add=True)

    replied = models.BooleanField(default=False)
    reply_text = models.TextField(blank=True, null=True)
    replied_at = models.DateTimeField(blank=True, null=True)
    transferido = models.BooleanField(default=False)

    def __str__(self):
        return f"Msg from {self.remote_jid} at {self.received_at}"
    
class Departamento(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    owner = models.ForeignKey('User', on_delete=models.CASCADE, related_name='departamentos', null=True)

    def __str__(self):
        return self.nombre

class Agente(models.Model):
    nombre = models.CharField(max_length=100)
    numero_whatsapp = models.CharField(max_length=20)
    departamentos = models.ManyToManyField(Departamento, related_name='agentes', blank=True)
    activo = models.BooleanField(default=True)
    owner = models.ForeignKey('User', on_delete=models.CASCADE, related_name='agentes', null=True)

    def __str__(self):
        return self.nombre
    
class ClienteConsulta(models.Model):
    bot = models.ForeignKey(ConfigBot, on_delete=models.CASCADE, related_name='consultas')
    remote_jid = models.CharField(max_length=200, blank=True)
    nombre = models.CharField(max_length=200, blank=True)
    correo = models.EmailField(blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    empresa = models.CharField(max_length=200, blank=True)
    plan_interes = models.CharField(max_length=200, blank=True)
    resumen = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre or self.remote_jid} — {self.created_at:%d/%m/%Y}"