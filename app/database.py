import sqlite3
from flask import g, current_app
from datetime import datetime
import re
import logging
import math

# Initialize logger
logger = logging.getLogger(__name__)

def get_db():
    if 'db' not in g:
        try:
            g.db = sqlite3.connect(current_app.config['DATABASE'])
            g.db.row_factory = sqlite3.Row
            logger.debug("Database connection established")
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {str(e)}")
            raise
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
            logger.debug("Database connection closed")
        except sqlite3.Error as e:
            logger.error(f"Error closing database connection: {str(e)}")

def init_db():
    try:
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
        db.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')
        db.commit()
        logger.info("Database tables initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise

def calculate_warranty_stats():
    try:
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
        
        logger.debug(f"Calculated warranty stats: total={total_assets}, expired={expired}, expiring_soon={expiring_soon}, active={active}")
        
        return {
            'total_assets': total_assets,
            'expired': expired,
            'expiring_soon': expiring_soon,
            'active': active
        }
    except sqlite3.Error as e:
        logger.error(f"Error calculating warranty stats: {str(e)}")
        return {
            'total_assets': 0,
            'expired': 0,
            'expiring_soon': 0,
            'active': 0
        }

def get_expiring_assets(days=30):
    try:
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
        results = cursor.fetchall()
        logger.debug(f"Fetched expiring assets: {len(results)} results for {days} days")
        return results
    except sqlite3.Error as e:
        logger.error(f"Error fetching expiring assets: {str(e)}")
        return []

def get_recently_expired_assets(days=30):
    try:
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
        results = cursor.fetchall()
        logger.debug(f"Fetched recently expired assets: {len(results)} results for {days} days")
        return results
    except sqlite3.Error as e:
        logger.error(f"Error fetching expired assets: {str(e)}")
        return []

def get_recently_added_assets(days=7):
    try:
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
        results = cursor.fetchall()
        logger.debug(f"Fetched recently added assets: {len(results)} results for {days} days")
        return results
    except sqlite3.Error as e:
        logger.error(f"Error fetching new assets: {str(e)}")
        return []

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
            normalized = datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            logger.debug(f"Normalized date: '{date_str}' -> '{normalized}'")
            return normalized
        except ValueError:
            continue
    
    # Handle month-name-without-comma format (e.g., "May 01 2018")
    month_name_match = re.match(r'([a-zA-Z]{3,9})\s+(\d{1,2})\s+(\d{4})', date_str)
    if month_name_match:
        month, day, year = month_name_match.groups()
        try:
            normalized = datetime.strptime(f"{month} {day}, {year}", '%b %d, %Y').strftime('%Y-%m-%d')
            logger.debug(f"Normalized date with month name: '{date_str}' -> '{normalized}'")
            return normalized
        except ValueError:
            try:
                normalized = datetime.strptime(f"{month} {day}, {year}", '%B %d, %Y').strftime('%Y-%m-%d')
                logger.debug(f"Normalized date with full month name: '{date_str}' -> '{normalized}'")
                return normalized
            except ValueError:
                pass
    
    # Handle two-digit year without separators (e.g., "022027" for February 2027)
    two_digit_year_match = re.match(r'(\d{2})(\d{2})(\d{2})', date_str)
    if two_digit_year_match:
        month, day, year = two_digit_year_match.groups()
        try:
            # Convert two-digit year to four-digit (00-68 = 2000-2068, 69-99 = 1969-1999)
            full_year = int(year) + 2000 if int(year) <= 68 else int(year) + 1900
            normalized = datetime(full_year, int(month), int(day)).strftime('%Y-%m-%d')
            logger.debug(f"Normalized two-digit year date: '{date_str}' -> '{normalized}'")
            return normalized
        except ValueError:
            pass
    
    # Handle other edge cases
    if date_str.lower() in ['n/a', 'na', 'none', 'null']:
        logger.debug(f"Date normalization: '{date_str}' recognized as null value")
        return None
    
    logger.warning(f"Failed to normalize date: '{date_str}'")
    return None

# Alert settings helpers
def get_alert_settings():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM alert_settings WHERE is_active = 1")
        settings = cursor.fetchall()
        logger.debug(f"Fetched {len(settings)} active alert settings")
        return settings
    except sqlite3.Error as e:
        logger.error(f"Error fetching alert settings: {str(e)}")
        return []

def add_alert_setting(name, webhook_url, alert_type):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO alert_settings (name, webhook_url, alert_type, is_active) VALUES (?, ?, ?, 1)",
            (name, webhook_url, alert_type)
        )
        db.commit()
        setting_id = cursor.lastrowid
        logger.info(f"Added new alert setting: ID={setting_id}, Name={name}, Type={alert_type}")
        return setting_id
    except sqlite3.Error as e:
        logger.error(f"Error adding alert setting: {str(e)}")
        raise

def remove_alert_setting(setting_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE alert_settings SET is_active = 0 WHERE id = ?", (setting_id,))
        db.commit()
        logger.info(f"Removed alert setting: ID={setting_id}")
    except sqlite3.Error as e:
        logger.error(f"Error removing alert setting {setting_id}: {str(e)}")
        raise

# App settings helpers
def get_app_setting(key, default=None):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        value = row['value'] if row else default
        logger.debug(f"Retrieved app setting: {key}={value}")
        return value
    except sqlite3.Error as e:
        logger.error(f"Error getting app setting {key}: {str(e)}")
        return default

def set_app_setting(key, value):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, value)
        )
        db.commit()
        logger.info(f"Updated app setting: {key}={value}")
    except sqlite3.Error as e:
        logger.error(f"Error setting app setting {key}: {str(e)}")
        raise

def search_assets(query, page=1, per_page=10):
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Sanitize query - remove wildcards that could cause performance issues
        # We'll only allow wildcards at the end of words
        safe_query = query.replace('%', '').replace('_', '')
        
        # Split into words and add wildcards only at the end
        words = [word.strip() + '%' for word in safe_query.split() if word.strip()]
        
        # If no valid words remain, return empty results
        if not words:
            return [], 0
        
        # Create parameter placeholders for each word in each field
        placeholders = []
        params = []
        for word in words:
            placeholders.append(" OR ".join([
                "asset_tag LIKE ?", 
                "service_tag LIKE ?", 
                "manufacturer LIKE ?", 
                "model LIKE ?", 
                "notes LIKE ?"
            ]))
            params.extend([word] * 5)  # Add the same word for each field
        
        where_clause = "(" + ") OR (".join(placeholders) + ")"
        
        # Count total matches
        count_query = f"""
            SELECT COUNT(*) 
            FROM assets
            WHERE {where_clause}
        """
        cursor.execute(count_query, tuple(params))
        total_items = cursor.fetchone()[0]
        
        # Get paginated results
        offset = (page - 1) * per_page
        search_query = f"""
            SELECT 
                *,
                CASE 
                    WHEN warranty_end_date < date('now') THEN 'Expired'
                    WHEN warranty_end_date BETWEEN date('now') AND date('now', '+90 days') THEN 'Expiring Soon'
                    ELSE 'Active'
                END as status,
                CASE
                    WHEN warranty_end_date < date('now') THEN 0
                    ELSE CAST(julianday(warranty_end_date) - julianday('now') AS INTEGER)
                END as days_until_expiry
            FROM assets
            WHERE {where_clause}
            ORDER BY warranty_end_date DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(search_query, tuple(params + [per_page, offset]))
        assets = cursor.fetchall()
        
        logger.debug(f"Search found {len(assets)} assets for query '{query}'")
        return assets, total_items
        
    except sqlite3.Error as e:
        logger.error(f"Search error: {str(e)}")
        return [], 0