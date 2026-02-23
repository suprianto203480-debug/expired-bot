# File main.py - penghubung untuk Gunicorn
from bot import app_flask

# Export app_flask sebagai 'app' untuk Gunicorn
app = app_flask

if __name__ == "__main__":
    app.run()