# HomeInventory

HomeInventory ayuda a familias, talleres y pequeños grupos a saber qué objetos tienen, dónde están y quién los tiene prestados. Utiliza Django 5.2 LTS y Python 3.14.

El catálogo se organiza en espacios privados con participantes, lugares, contenedores y objetos. Los roles de propietario, editor y observador limitan el acceso. Compartir públicamente un objeto es una acción explícita: su título y descripción públicos son independientes del catálogo privado.

Incluye formularios, fotografías, búsqueda, etiquetas QR, historial de movimientos, préstamos e importación y exportación de espacios. No es un sistema contable ni de tasación de seguros. La IA, la sincronización completa sin conexión y las notificaciones automáticas siguen como propuestas condicionadas a necesidades comprobadas.

## Desarrollo

```bash
git clone https://github.com/Artem7898/homeinventory.git
cd homeinventory
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.txt
cp .env.example .env
```

Activa `DEBUG=True` para desarrollo local. `PUBLIC_BASE_URL` debe ser una dirección accesible desde los dispositivos que escanean las etiquetas. En un teléfono, `localhost` significa el propio teléfono; la cámara normalmente necesita HTTPS.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver 127.0.0.1:8000
```

Inicia sesión y crea un espacio. No hay registro público: un administrador crea las cuentas y el propietario del espacio asigna los roles. SQLite permite una instalación personal; PostgreSQL necesita sus bibliotecas de desarrollo para instalar el controlador.

```bash
python manage.py test --settings=config.test_settings
python manage.py makemigrations --check --dry-run --settings=config.test_settings
```

Antes de actualizar, guarda y comprueba una copia de la base de datos y de los archivos. Los datos anteriores se trasladan a un espacio privado accesible inicialmente solo para superusuarios. En producción se necesitan una clave secreta segura, dominios exactos, HTTPS y almacenamiento persistente privado. No publiques `media/` evitando la autorización de la aplicación.

Consulta la [guía de despliegue](docs/DEPLOYMENT.md), la [respuesta a la auditoría](docs/AUDIT-RESPONSE.md), el [plan](docs/ROADMAP.md) y la [guía de contribución](CONTRIBUTING.md). La documentación operativa detallada está actualmente en ruso.

El propietario todavía no ha elegido una licencia para el proyecto. La antigua insignia MIT no otorgaba una licencia MIT. Los componentes de terceros conservan sus propias licencias.
