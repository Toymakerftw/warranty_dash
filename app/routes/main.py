from flask import Blueprint, request, render_template, jsonify, make_response, current_app
from app.database import get_db, calculate_warranty_stats, get_alert_settings, add_alert_setting, remove_alert_setting, get_app_setting, set_app_setting
from datetime import datetime
import math
import io
import csv
import requests

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

# Utility to send a message to a Google Chat webhook
def send_google_chat_message(webhook_url, message):
    headers = {'Content-Type': 'application/json; charset=UTF-8'}
    data = {"text": message}
    try:
        response = requests.post(webhook_url, json=data, headers=headers, timeout=5)
        return response.status_code == 200
    except Exception as e:
        return False

def send_scheduled_alerts(app):
    with app.app_context():
        from app.database import get_alert_settings, get_expiring_assets, get_recently_expired_assets
        settings = get_alert_settings()
        # Expiring soon
        expiring = get_expiring_assets(30)
        if expiring:
            for s in settings:
                if s['alert_type'] in ('all', 'warning'):
                    for item in expiring:
                        msg = f"[Expiring Soon] {item['manufacturer']} {item['model'] or ''} ({item['count']}) warranties expiring soon. Action required."
                        send_google_chat_message(s['webhook_url'], msg)
        # Expired
        expired = get_recently_expired_assets(30)
        if expired:
            for s in settings:
                if s['alert_type'] in ('all', 'danger'):
                    for item in expired:
                        msg = f"[Expired] {item['manufacturer']} {item['model'] or ''} ({item['count']}) warranties expired. Immediate attention needed."
                        send_google_chat_message(s['webhook_url'], msg)

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

# Route to list all alert settings
@main_bp.route('/alert-settings', methods=['GET'])
def alert_settings():
    settings = get_alert_settings()
    alert_cron = get_app_setting('alert_cron', current_app.config.get('ALERT_CRON', '0 8 * * *'))
    return render_template('alert_settings.html', settings=settings, alert_cron=alert_cron)

# Route to add a new alert setting
@main_bp.route('/alert-settings/add', methods=['POST'])
def add_alert_setting_route():
    name = request.form.get('name')
    webhook_url = request.form.get('webhook_url')
    alert_type = request.form.get('alert_type')
    if not (name and webhook_url and alert_type):
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400
    add_alert_setting(name, webhook_url, alert_type)
    return jsonify({'success': True, 'message': 'Alert setting added.'})

# Route to remove an alert setting
@main_bp.route('/alert-settings/remove/<int:setting_id>', methods=['POST'])
def remove_alert_setting_route(setting_id):
    remove_alert_setting(setting_id)
    return jsonify({'success': True, 'message': 'Alert setting removed.'})

# Route to send a test alert to all webhooks
@main_bp.route('/alert-settings/test', methods=['POST'])
def test_alert_settings():
    message = request.form.get('message', 'This is a test alert from WarrantyTrack.')
    settings = get_alert_settings()
    results = []
    for s in settings:
        ok = send_google_chat_message(s['webhook_url'], message)
        results.append({'name': s['name'], 'webhook_url': s['webhook_url'], 'success': ok})
    return jsonify({'results': results})

# Route to update alert cron schedule
@main_bp.route('/alert-settings/schedule', methods=['POST'])
def update_alert_cron():
    cron = request.form.get('cron', '').strip()
    if not cron or len(cron.split()) != 5:
        return jsonify({'success': False, 'message': 'Invalid cron format. Use 5 fields: min hour day month day_of_week.'})
    set_app_setting('alert_cron', cron)
    current_app.config['ALERT_CRON'] = cron
    if hasattr(current_app, 'apscheduler'):
        try:
            current_app.apscheduler.reschedule_job('send_scheduled_alerts',
                trigger='cron',
                minute=cron.split()[0],
                hour=cron.split()[1],
                day=cron.split()[2],
                month=cron.split()[3],
                day_of_week=cron.split()[4],
            )
            return jsonify({'success': True, 'message': f'Schedule updated to: {cron}'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Failed to update schedule: {e}'})
    return jsonify({'success': False, 'message': 'Scheduler not running.'})