import sqlite3
from flask import g, current_app
from datetime import datetime
import re

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.execute('''
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_tag TEXT,
        service_tag TEXT,
        manufacturer TEXT,
        model TEXT,
        warranty_end_date TEXT,
        purchase_date TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    ''')
    # Add alert_settings table for storing webhook URLs and alert preferences
    db.execute('''
    CREATE TABLE IF NOT EXISTS alert_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        webhook_url TEXT,
        alert_type TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )
    ''')
    # Add app_settings table for global settings like alert cron
    db.execute('''
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')
    db.commit()

def calculate_warranty_stats():
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM assets")
    total_assets = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM assets WHERE warranty_end_date < date('now')")
    expired = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM assets WHERE warranty_end_date BETWEEN date('now') AND date('now', '+90 days')")
    expiring_soon = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM assets WHERE warranty_end_date > date('now', '+90 days')")
    active = cursor.fetchone()[0]
    
    return {
        'total_assets': total_assets,
        'expired': expired,
        'expiring_soon': expiring_soon,
        'active': active
    }

def get_expiring_assets(days=30):
    """Get assets expiring within the next X days"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT manufacturer, model, COUNT(*) as count
        FROM assets
        WHERE warranty_end_date BETWEEN date('now') AND date('now', ?)
        GROUP BY manufacturer, model
        ORDER BY count DESC
        LIMIT 5
    """, (f"+{days} days",))
    return cursor.fetchall()

def get_recently_expired_assets(days=30):
    """Get assets that expired in the last X days"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT manufacturer, model, COUNT(*) as count
        FROM assets
        WHERE warranty_end_date BETWEEN date('now', ?) AND date('now')
        GROUP BY manufacturer, model
        ORDER BY count DESC
        LIMIT 5
    """, (f"-{days} days",))
    return cursor.fetchall()

def get_recently_added_assets(days=7):
    """Get assets added in the last X days"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT manufacturer, model, COUNT(*) as count
        FROM assets
        WHERE DATE(created_at) > date('now', ?)
        GROUP BY manufacturer, model
        ORDER BY count DESC
        LIMIT 5
    """, (f"-{days} days",))
    return cursor.fetchall()

def normalize_date(date_str):
    if not date_str:
        return None
    
    # Clean up the date string
    date_str = date_str.strip().replace('"', '')
    
    # Handle empty strings after cleaning
    if not date_str:
        return None
    
    # Try to parse various date formats
    formats = [
        '%Y-%m-%d',          # 2023-12-31
        '%m/%d/%y',           # 12/31/23
        '%m/%d/%Y',           # 12/31/2023
        '%b %d, %Y',          # Dec 31, 2023
        '%B %d, %Y',          # December 31, 2023
        '%d-%b-%y',           # 31-Dec-23
        '%d-%b-%Y',           # 31-Dec-2023
        '%d/%m/%y',           # 31/12/23
        '%d/%m/%Y',           # 31/12/2023
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # Handle month-name-without-comma format (e.g., "May 01 2018")
    month_name_match = re.match(r'([a-zA-Z]{3,9})\s+(\d{1,2})\s+(\d{4})', date_str)
    if month_name_match:
        month, day, year = month_name_match.groups()
        try:
            return datetime.strptime(f"{month} {day}, {year}", '%b %d, %Y').strftime('%Y-%m-%d')
        except ValueError:
            try:
                return datetime.strptime(f"{month} {day}, {year}", '%B %d, %Y').strftime('%Y-%m-%d')
            except ValueError:
                pass
    
    # Handle two-digit year without separators (e.g., "022027" for February 2027)
    two_digit_year_match = re.match(r'(\d{2})(\d{2})(\d{2})', date_str)
    if two_digit_year_match:
        month, day, year = two_digit_year_match.groups()
        try:
            # Convert two-digit year to four-digit (00-68 = 2000-2068, 69-99 = 1969-1999)
            full_year = int(year) + 2000 if int(year) <= 68 else int(year) + 1900
            return datetime(full_year, int(month), int(day)).strftime('%Y-%m-%d')
        except ValueError:
            pass
    
    # Handle other edge cases
    if date_str.lower() in ['n/a', 'na', 'none', 'null']:
        return None
    
    # If all parsing fails, return None
    return None

# Alert settings helpers
def get_alert_settings():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM alert_settings WHERE is_active = 1")
    return cursor.fetchall()

def add_alert_setting(name, webhook_url, alert_type):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO alert_settings (name, webhook_url, alert_type, is_active) VALUES (?, ?, ?, 1)",
        (name, webhook_url, alert_type)
    )
    db.commit()
    return cursor.lastrowid

def remove_alert_setting(setting_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE alert_settings SET is_active = 0 WHERE id = ?", (setting_id,))
    db.commit()

# App settings helpers
def get_app_setting(key, default=None):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row['value'] if row else default

def set_app_setting(key, value):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """INSERT INTO app_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, value)
    )
    db.commit()