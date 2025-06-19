import os
import logging

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key_here'
    DATABASE = 'warranty.db'
    DEBUG = True
    ALERT_CRON = os.environ.get('ALERT_CRON', '0 8 * * *')  # Default: every day at 8am
    
    # Add base URL for card links
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')

    # Logging configuration
    LOG_LEVEL = logging.INFO
    LOG_FILE = 'warranty_track.log'
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT = 5