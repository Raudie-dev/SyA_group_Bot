from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('app1', '0010_remove_agente_departamento_agente_departamentos'),
    ]

    operations = [
        migrations.AddField(
            model_name='configbot',
            name='api_provider',
            field=models.CharField(
                max_length=20,
                choices=[('deepseek', 'DeepSeek'), ('openai', 'OpenAI'), ('gemini', 'Gemini')],
                default='deepseek',
                help_text='Proveedor de IA',
            ),
        ),
        migrations.AlterField(
            model_name='configbot',
            name='api_key',
            field=models.CharField(
                max_length=100,
                blank=True,
                null=True,
                help_text='API Key del proveedor seleccionado',
            ),
        ),
    ]
