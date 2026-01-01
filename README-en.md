# 📦 HomeInventory

**Home Inventory with QR Codes** — a modern Django application for tracking items in your apartment, office, or warehouse. Scan boxes with your phone and instantly find their contents!

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

## ✨ Features

| Feature | How It Helps |
|---------|--------------|
| **📱 QR Codes** | Stick on a box → scan with your phone → instantly see contents |
| **🔍 Instant Search** | Find "passport" in 2 seconds without digging through 50 boxes |
| **📊 Statistics** | Know total value of items and number of categories |
| **📤 CSV Export** | For insurance or moving — download full list in 1 click |
| **🔒 Security** | Rate limiting, secret admin panel, 2FA (optional) |
| **🎨 Modern UI** | Django Unfold — admin panel like it's 2025 |

## 🚀 Quick Start

### Requirements
- Python 3.10+
- SQLite (default) or PostgreSQL

### Installation (5 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/Artem7898/homeinventory.git
cd homeinventory

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file (copy .env.example)
cp .env.example .env
# Edit .env, add SECRET_KEY

# 5. Run migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Start server
python manage.py runserver 0.0.0.0:8000