from app.database import get_db
import logging

logger = logging.getLogger(__name__)

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
    except Exception as e:
        logger.error(f"Error calculating warranty stats: {str(e)}")
        return {
            'total_assets': 0,
            'expired': 0,
            'expiring_soon': 0,
            'active': 0
        }

def get_expiring_assets(days=30):
    """Get assets expiring within the next X days"""
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
    except Exception as e:
        logger.error(f"Error fetching expiring assets: {str(e)}")
        return []

def get_recently_expired_assets(days=30):
    """Get assets that expired in the last X days"""
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
    except Exception as e:
        logger.error(f"Error fetching expired assets: {str(e)}")
        return []

def get_recently_added_assets(days=7):
    """Get assets added in the last X days"""
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
    except Exception as e:
        logger.error(f"Error fetching new assets: {str(e)}")
        return []