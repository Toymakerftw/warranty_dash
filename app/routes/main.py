from flask import Blueprint, request, render_template, jsonify, make_response
from app.database import get_db, calculate_warranty_stats
from datetime import datetime
import math
import io
import csv

# First define the Blueprint
main_bp = Blueprint('main', __name__)

ITEMS_PER_PAGE = 10  # Number of items to show per page

# Then define your helper functions
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

def generate_alerts():
    """Generate recent alerts based on asset status"""
    alerts = []
    
    # Expiring soon alerts
    expiring = get_expiring_assets(30)
    for item in expiring:
        alerts.append({
            'type': 'warning',
            'icon': 'fa-clock',
            'title': f"{item['manufacturer']} {item['model'] or 'devices'} expiring soon",
            'message': 'Action required to renew warranties',
            'manufacturer': item['manufacturer'],
            'model': item['model'],
            'days': 30,
            'count': item['count']  # Add count for badge
        })
    
    # Recently expired alerts
    expired = get_recently_expired_assets(30)
    for item in expired:
        alerts.append({
            'type': 'danger',
            'icon': 'fa-exclamation-circle',
            'title': f"{item['manufacturer']} {item['model'] or 'devices'} warranties expired",
            'message': 'Need immediate attention',
            'manufacturer': item['manufacturer'],
            'model': item['model'],
            'days': 30,
            'count': item['count']  # Add count for badge
        })
    
    # Newly added assets
    new_assets = get_recently_added_assets(7)
    for item in new_assets:
        alerts.append({
            'type': 'info',
            'icon': 'fa-plus-circle',
            'title': f"New {item['manufacturer']} {item['model'] or 'devices'} added",
            'message': 'Recently added to inventory',
            'manufacturer': item['manufacturer'],
            'model': item['model'],
            'days': 7,
            'count': item['count']  # Add count for badge
        })
    
    return alerts[:3]  # Return top 3 most important alerts

# Then define your routes
@main_bp.route('/')
def dashboard():
    db = get_db()
    cursor = db.cursor()
    
    # Calculate warranty stats
    stats = calculate_warranty_stats()
    
    # Generate recent alerts
    alerts = generate_alerts()
    
    # Get filter parameters from request
    status_filter = request.args.get('status', 'all')
    manufacturer_filter = request.args.get('manufacturer', 'all')
    page = int(request.args.get('page', 1))
    
    # Build the base query for assets
    base_query = """
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
    """
    
    where_clauses = []
    params = []
    
    # Add status filter if specified
    if status_filter != 'all':
        if status_filter == 'Active':
            where_clauses.append("warranty_end_date > date('now', '+90 days')")
        elif status_filter == 'Expiring Soon':
            where_clauses.append("warranty_end_date BETWEEN date('now') AND date('now', '+90 days')")
        elif status_filter == 'Expired':
            where_clauses.append("warranty_end_date < date('now')")
    
    # Add manufacturer filter if specified
    if manufacturer_filter != 'all':
        where_clauses.append("manufacturer = ?")
        params.append(manufacturer_filter)
    
    # Combine filters
    if where_clauses:
        base_query += " WHERE " + " AND ".join(where_clauses)
    
    # Get total count for pagination
    count_query = "SELECT COUNT(*) FROM (" + base_query + ")"
    cursor.execute(count_query, tuple(params))
    total_items = cursor.fetchone()[0]
    
    # Calculate pagination values
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    offset = (page - 1) * ITEMS_PER_PAGE
    
    # Add sorting, limiting and pagination
    base_query += " ORDER BY warranty_end_date DESC LIMIT ? OFFSET ?"
    params.extend([ITEMS_PER_PAGE, offset])
    
    # Execute the query
    cursor.execute(base_query, tuple(params))
    assets = cursor.fetchall()
    
    # Get manufacturer distribution for filter dropdown
    cursor.execute("""
        SELECT manufacturer, COUNT(*) as count 
        FROM assets 
        GROUP BY manufacturer 
        ORDER BY count DESC
        LIMIT 10
    """)
    manufacturers = cursor.fetchall()
    
    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'html': render_template('_asset_table.html',
                                  assets=assets,
                                  current_status=status_filter,
                                  current_manufacturer=manufacturer_filter,
                                  pagination={
                                      'page': page,
                                      'total_pages': total_pages,
                                      'total_items': total_items,
                                      'items_per_page': ITEMS_PER_PAGE
                                  }),
            'stats': stats,
            'alerts': alerts
        })
    
    return render_template('dashboard.html', 
                         stats=stats,
                         assets=assets,
                         manufacturers=manufacturers,
                         current_status=status_filter,
                         current_manufacturer=manufacturer_filter,
                         pagination={
                             'page': page,
                             'total_pages': total_pages,
                             'total_items': total_items,
                             'items_per_page': ITEMS_PER_PAGE
                         },
                         alerts=alerts)

@main_bp.route('/alerts/details')
def alert_details():
    alert_type = request.args.get('type', '')
    manufacturer = request.args.get('manufacturer', '')
    model = request.args.get('model', '')
    days = request.args.get('days', 30)
    
    db = get_db()
    cursor = db.cursor()
    
    base_query = """
        SELECT 
            asset_tag,
            service_tag,
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
    
    # Add filters based on alert type
    if alert_type == 'warning':  # Expiring soon
        base_query += " AND warranty_end_date BETWEEN date('now') AND date('now', ?)"
        params.append(f"+{days} days")
    elif alert_type == 'danger':  # Expired
        base_query += " AND warranty_end_date BETWEEN date('now', ?) AND date('now')"
        params.append(f"-{days} days")
    elif alert_type == 'info':  # Newly added
        base_query += " AND DATE(created_at) > date('now', ?)"
        params.append(f"-{days} days")
    
    # Add manufacturer filter
    if manufacturer:
        base_query += " AND manufacturer = ?"
        params.append(manufacturer)
    
    # Add model filter
    if model:
        base_query += " AND model = ?"
        params.append(model)
    
    # Execute the query
    cursor.execute(base_query, tuple(params))
    assets = cursor.fetchall()
    
    # Get total count without LIMIT
    count_query = "SELECT COUNT(*) FROM (" + base_query + ")"
    cursor.execute(count_query, tuple(params))
    total_count = cursor.fetchone()[0]
    
    return jsonify({
        'assets': [dict(asset) for asset in assets],
        'total_count': total_count
    })

@main_bp.route('/alerts/export')
def export_alert_details():
    alert_type = request.args.get('type', '')
    manufacturer = request.args.get('manufacturer', '')
    model = request.args.get('model', '')
    days = request.args.get('days', 30)
    
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
    
    # Add filters based on alert type
    if alert_type == 'warning':  # Expiring soon
        base_query += " AND warranty_end_date BETWEEN date('now') AND date('now', ?)"
        params.append(f"+{days} days")
    elif alert_type == 'danger':  # Expired
        base_query += " AND warranty_end_date BETWEEN date('now', ?) AND date('now')"
        params.append(f"-{days} days")
    elif alert_type == 'info':  # Newly added
        base_query += " AND DATE(created_at) > date('now', ?)"
        params.append(f"-{days} days")
    
    # Add manufacturer filter
    if manufacturer:
        base_query += " AND manufacturer = ?"
        params.append(manufacturer)
    
    # Add model filter
    if model:
        base_query += " AND model = ?"
        params.append(model)
    
    # Execute the query
    cursor.execute(base_query, tuple(params))
    assets = cursor.fetchall()
    
    # Create CSV output
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Asset Tag', 'Serial', 'Manufacturer', 'Model', 
                    'Warranty End Date', 'Status', 'Days Remaining'])
    
    # Write data
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
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=alert_details_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response.headers['Content-type'] = 'text/csv'
    
    return response