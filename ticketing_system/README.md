# Event Ticket Management System

A comprehensive Django-based ticket management system for events, featuring ticket validation, user management, and real-time announcements.

## Features

- 🎟️ Event creation and management
- 👥 User roles (Admin, Staff, Customer)
- 🔒 Secure authentication system
- 📱 Mobile-responsive design
- 📊 Dashboard with analytics
- 🎯 QR Code ticket validation
- 📢 Announcement system
- 💰 Token-based payment system

## Prerequisites

- Python 3.8+
- MySQL or PostgreSQL database
- pip (Python package manager)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Rango004/event_ticket_management.git
   cd event_ticket_management
   ```

2. **Set up a virtual environment** (recommended):
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate
   
   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   - Copy `.env.example` to `.env`
   - Update the database and secret key settings
   ```
   DEBUG=True
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=mysql://user:password@localhost/dbname
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the admin panel**
   - Visit `http://127.0.0.1:8000/admin/`
   - Log in with your superuser credentials

## Deployment

### PythonAnywhere

1. Create a PythonAnywhere account at [pythonanywhere.com](https://www.pythonanywhere.com/)
2. Upload your code using Git
3. Set up a virtual environment and install requirements
4. Configure your web app with the following WSGI configuration:
   ```python
   import os
   import sys
   
   path = '/home/yourusername/event_ticket_management'
   if path not in sys.path:
       sys.path.append(path)
   
   os.environ['DJANGO_SETTINGS_MODULE'] = 'ticketing_system.settings'
   
   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
5. Set up your static files and database
6. Reload your web app

## Project Structure

```
event_ticket_management/
├── manage.py
├── requirements.txt
├── ticketing_system/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── tickets/
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
└── README.md
```

## Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, email [your-email@example.com] or open an issue in the repository.

---

<div align="center">
  Made with ❤️ by Rango
</div>
