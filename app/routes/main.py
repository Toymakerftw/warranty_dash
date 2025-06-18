from flask import Blueprint, render_template
from app.database import get_db
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def dashboard():
    db = get_db()
    cursor = db.cursor()
    
    # Calculate warranty stats
    cursor.execute("SELECT COUNT(*) FROM assets")
    total_assets = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM assets WHERE warranty_end_date < date('now')")
    expired = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM assets WHERE warranty_end_date BETWEEN date('now') AND date('now', '+90 days')")
    expiring_soon = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM assets WHERE warranty_end_date > date('now', '+90 days')")
    active = cursor.fetchone()[0]
    
    stats = {
        'total_assets': total_assets,
        'expired': expired,
        'expiring_soon': expiring_soon,
        'active': active
    }
    
    # Get recent assets with warranty calculations
    cursor.execute("""
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
        ORDER BY warranty_end_date DESC 
        LIMIT 50
    """)
    assets = cursor.fetchall()
    
    # Get manufacturer distribution
    cursor.execute("""
        SELECT manufacturer, COUNT(*) as count 
        FROM assets 
        GROUP BY manufacturer 
        ORDER BY count DESC
        LIMIT 5
    """)
    manufacturers = cursor.fetchall()
    
    return render_template('dashboard.html', 
                         stats=stats,
                         assets=assets,
                         manufacturers=manufacturers)