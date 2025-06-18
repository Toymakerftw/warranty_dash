from flask import Blueprint, render_template
from app.database import calculate_warranty_stats, get_db

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def dashboard():
    stats = calculate_warranty_stats()
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT *, 
        CASE 
            WHEN warranty_end_date < date('now') THEN 'Expired'
            WHEN warranty_end_date < date('now', '+90 days') THEN 'Expiring Soon'
            ELSE 'Active'
        END as status
        FROM assets 
        ORDER BY warranty_end_date DESC 
        LIMIT 50
    """)
    assets = cursor.fetchall()
    
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
