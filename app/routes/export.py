from flask import Blueprint, request, jsonify, make_response, redirect, url_for, flash
from flask_login import login_required, current_user
from app.database import get_db
from datetime import datetime
import io
import csv
import logging

logger = logging.getLogger(__name__)

export_bp = Blueprint('export', __name__)

@export_bp.route('/alerts/export')
@login_required
def export_alert_details():
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required to export alert details.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        logger.info(f"Alert export requested by admin: {current_user.username}")
        alert_type = request.args.get('type', '')
        manufacturer = request.args.get('manufacturer', '')
        model = request.args.get('model', '')
        days = request.args.get('days', 30)
        
        logger.info(f"Exporting alert details - Type: {alert_type}, Manufacturer: {manufacturer}, Model: {model}, Days: {days}")
        
        db = get_db()
        cursor = db.cursor()
        
        base_query = """
            SELECT 
                asset_tag,
                service_tag,
                manufacturer,
                model,
                warranty_end_date,
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
            WHERE 1=1
        """
        
        params = []
        
        if alert_type == 'warning':
            base_query += " AND warranty_end_date BETWEEN date('now') AND date('now', ?)"
            params.append(f"+{days} days")
        elif alert_type == 'danger':
            base_query += " AND warranty_end_date BETWEEN date('now', ?) AND date('now')"
            params.append(f"-{days} days")
        elif alert_type == 'info':
            base_query += " AND DATE(created_at) > date('now', ?)"
            params.append(f"-{days} days")
        
        if manufacturer:
            base_query += " AND manufacturer = ?"
            params.append(manufacturer)
        
        if model:
            base_query += " AND model = ?"
            params.append(model)
        
        cursor.execute(base_query, tuple(params))
        assets = cursor.fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['Asset Tag', 'Serial', 'Manufacturer', 'Model', 
                        'Warranty End Date', 'Status', 'Days Remaining'])
        
        for asset in assets:
            writer.writerow([
                asset['asset_tag'],
                asset['service_tag'],
                asset['manufacturer'],
                asset['model'],
                asset['warranty_end_date'],
                asset['status'],
                asset['days_until_expiry']
            ])
        
        logger.info(f"Exported {len(assets)} assets to CSV by admin {current_user.username}")
        
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=alert_details_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response.headers['Content-type'] = 'text/csv'
        
        return response
    except Exception as e:
        logger.exception("Failed to export alert details")
        return jsonify({'error': 'Internal server error'}), 500