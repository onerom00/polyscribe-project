# Staging temporal de PolyScribe One

La propuesta está en `render.staging.yaml`, separada de `render.yaml`.
No se ha autorizado su aplicación. Crear un plan de Blueprint no despliega.

## Recursos propuestos

- Web `polyscribe-one-staging`, Docker/Python 3.12 con FFmpeg, plan `free`.
- PostgreSQL `polyscribe-one-staging-db`, versión 18, plan `free` y base lógica
  `polyscribe_staging`. Conexión interna; acceso externo bloqueado.
- Oregon, rama `polyscribe-one-core`, despliegues automáticos desactivados.
- Datos nuevos de prueba; no se copian usuarios, pagos, claves ni grabaciones
  de producción. No se enlaza un grupo de variables de producción.

La separación usa recursos y credenciales distintos; no se afirma aislamiento
de red entre entornos, que depende del plan del workspace y su configuración.

## Costos y límites verificados

Según la documentación de Render consultada el 2026-11-08, los dos planes
`free` no tienen cargo de cómputo. El workspace permite una base gratuita
activa; la consulta de inventario no mostraba ninguna.

La base gratuita tiene 1 GB, caduca a los 30 días y no incluye backups. La web
duerme tras 15 minutos sin tráfico, comparte las 750 horas gratuitas mensuales
del workspace y no permite shell ni SMTP. Build y transferencia cuentan contra
cuotas compartidas y pueden generar cargos por exceso. OpenAI cobra las
llamadas reales según la cuenta utilizada. Revisar uso y límites de gasto del
workspace antes de aplicar; no se promete costo total cero.

Fuentes: https://render.com/docs/free y https://render.com/docs/compute-plans.

## Inicialización y acceso

El contenedor ejecuta `scripts.prepare_staging` antes de Gunicorn. El script
exige `POLYSCRIBE_STAGING=1`, PostgreSQL y el nombre exacto `polyscribe_staging`.
Solo inicializa bases vacías; rechaza una base no vacía sin versión Alembic.
No es una herramienta de recuperación para bases inicializadas parcialmente.

Las migraciones históricas asumen tablas anteriores. Por ello, en esta base
vacía se crean las tablas actuales anteriores a One, se marca `0e9c61264114`
y se ejecuta la migración aditiva. Esto no prueba la reproducción completa
de la cadena histórica desde cero.

Render genera SECRET_KEY y STAGING_TEST_PASSWORD. El script crea la cuenta
verificada `polyscribe-staging@example.invalid`; el login está en `/auth/login`.
Consultar su contraseña exclusivamente en el Dashboard, sin copiarla a Git ni
a chat. La clave OPENAI_API_KEY se solicita al aprobar el plan y debe ingresarse
directamente en Render. Si se aprueba desde Dashboard sin configurarla y el
despliegue falla, añadirla en Environment y repetir el despliegue.

No se configuran credenciales PayPal ni SMTP. La cuenta pre-verificada permite
probar el acceso sin enviar correos. Se configuran cookies para el host de
staging, cinco minutos de cuota y archivos de hasta 10 MB.

## Verificación previa a aplicación

- Blueprint validado con el JSON Schema actual de Render; CLI no disponible.
- Bootstrap y repetición probados contra PostgreSQL 18 local, incluido login,
  cookie sin atributo Domain, sesión y rechazo de un nombre de base distinto.
- Veintiséis pruebas de aplicación aprobadas en SQLite.
- La imagen Docker aún debe construirse durante la validación de despliegue;
  no se ha probado una llamada real a OpenAI.

Tras aprobación, comprobar build, `/healthz`, login y una grabación corta,
con los criterios de `POLYSCRIBE_ONE_RELEASE.md`.
