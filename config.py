import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key_here'
    DATABASE = 'warranty.db'
    DEBUG = True
    ALERT_CRON = os.environ.get('ALERT_CRON', '0 8 * * *')  # Default: every day at 8am
