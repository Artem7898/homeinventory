# 📦 HomeInventory

**Inventario Doméstico con Códigos QR** — una aplicación moderna en Django para gestionar objetos en tu apartamento, oficina o almacén. ¡Escanea cajas con tu teléfono e instántaneamente encuentra su contenido!

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

## ✨ Características

| Característica | Cómo Ayuda |
|----------------|------------|
| **📱 Códigos QR** | Pégalo en una caja → escanea con tu teléfono → ve el contenido al instante |
| **🔍 Búsqueda Instantánea** | Encuentra "pasaporte" en 2 segundos sin revisar 50 cajas |
| **📊 Estadísticas** | Conoce el valor total de los objetos y cuántas categorías tienes |
| **📤 Exportar a CSV** | Para seguros o mudanzas — descarga la lista completa con 1 clic |
| **🔒 Seguridad** | Rate limiting, panel de administración secreto, 2FA (opcional) |
| **🎨 UI Moderna** | Django Unfold — panel de administración como en 2025 |

## 🚀 Inicio Rápido

### Requisitos
- Python 3.10+
- SQLite (por defecto) o PostgreSQL

### Instalación (5 minutos)

```bash
# 1. Clona el repositorio
git clone https://github.com/Artem7898/homeinventory.git
cd homeinventory

# 2. Crea el entorno virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 3. Instala las dependencias
pip install -r requirements.txt

# 4. Crea el archivo .env (copia .env.example)
cp .env.example .env
# Edita .env, añade tu SECRET_KEY

# 5. Ejecuta las migraciones
python manage.py migrate

# 6. Crea el superusuario
python manage.py createsuperuser

# 7. Inicia el servidor
python manage.py runserver 0.0.0.0:8000