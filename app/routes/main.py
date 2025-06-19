from flask import Blueprint, request, render_template, jsonify, make_response, current_app, url_for
from app.database import get_db, calculate_warranty_stats, get_alert_settings, add_alert_setting, remove_alert_setting, get_app_setting, set_app_setting
from datetime import datetime
import math
import io
import csv
import requests
import logging
import time
import urllib.parse

# Initialize logger
logger = logging.getLogger(__name__)

# First define the Blueprint
main_bp = Blueprint('main', __name__)

ITEMS_PER_PAGE = 10  # Number of items to show per page

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

def generate_alerts():
    """Generate recent alerts based on asset status"""
    try:
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
                'count': item['count']
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
                'count': item['count']
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
                'count': item['count']
            })
        
        logger.info(f"Generated {len(alerts)} alerts")
        return alerts[:3]
    except Exception as e:
        logger.error(f"Error generating alerts: {str(e)}")
        return []

def build_alert_card(alert_type, item, days):
    """Build a Google Chat card for an alert"""
    # Default values
    title = "Warranty Alert"
    subtitle = "Asset warranty notification"
    color = "#4285F4"  # Blue
    icon = "https://cdn-icons-png.flaticon.com/512/3524/3524388.png"  # Info icon
    
    # Customize based on alert type
    if alert_type == 'warning':
        title = "Warranty Expiring Soon"
        subtitle = f"{item['count']} {item['manufacturer']} {item['model'] or 'devices'} expiring in {days} days"
        color = "#F4B400"  # Yellow
        icon = "https://cdn-icons-png.flaticon.com/512/2088/2088617.png"  # Warning icon
    elif alert_type == 'danger':
        title = "Warranty Expired"
        subtitle = f"{item['count']} {item['manufacturer']} {item['model'] or 'devices'} expired"
        color = "#EA4335"  # Red
        icon = "https://cdn-icons-png.flaticon.com/512/564/564619.png"  # Error icon
    elif alert_type == 'info':
        title = "New Assets Added"
        subtitle = f"{item['count']} new {item['manufacturer']} {item['model'] or 'devices'} added"
        color = "#4285F4"  # Blue
        icon = "https://cdn-icons-png.flaticon.com/512/3524/3524388.png"  # Info icon
    
    # Encode parameters for export URL
    export_params = urllib.parse.urlencode({
        'type': alert_type,
        'manufacturer': item['manufacturer'],
        'model': item['model'] or '',
        'days': days
    })
    
    # Build URLs without url_for
    dashboard_url = f"{current_app.config['APP_BASE_URL']}/"
    export_url = f"{current_app.config['APP_BASE_URL']}/alerts/export?{export_params}"
    
    # Build card structure
    return {
        "cardsV2": [{
            "cardId": f"alert-{int(time.time())}",
            "card": {
                "header": {
                    "title": title,
                    "subtitle": subtitle,
                    "imageUrl": icon,
                    "imageType": "CIRCLE",
                    "imageAltText": "Alert Icon"
                },
                "sections": [{
                    "collapsible": False,
                    "widgets": [
                        {
                            "decoratedText": {
                                "text": f"<b>Manufacturer:</b> {item['manufacturer']}",
                                "wrapText": True
                            }
                        },
                        {
                            "decoratedText": {
                                "text": f"<b>Model:</b> {item['model'] or 'N/A'}",
                                "wrapText": True
                            }
                        },
                        {
                            "decoratedText": {
                                "text": f"<b>Count:</b> {item['count']} assets",
                                "wrapText": True
                            }
                        },
                        {
                            "decoratedText": {
                                "text": f"<b>Status:</b> {'Expiring Soon' if alert_type == 'warning' else 'Expired' if alert_type == 'danger' else 'New'}",
                                "wrapText": True
                            }
                        },
                        {
                            "buttonList": {
                                "buttons": [
                                    {
                                        "text": "VIEW IN DASHBOARD",
                                        "onClick": {
                                            "openLink": {
                                                "url": dashboard_url
                                            }
                                        }
                                    },
                                    {
                                        "text": "EXPORT DETAILS",
                                        "onClick": {
                                            "openLink": {
                                                "url": export_url
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }],
                "sectionDividerStyle": "SOLID_DIVIDER"
            }
        }]
    }

def send_google_chat_card(webhook_url, card_data):
    headers = {'Content-Type': 'application/json; charset=UTF-8'}
    try:
        response = requests.post(
            webhook_url, 
            json=card_data, 
            headers=headers, 
            timeout=10
        )
        if response.status_code == 200:
            logger.info(f"Sent Google Chat card to {webhook_url}")
            return True
        else:
            logger.warning(
                f"Failed to send Google Chat card to {webhook_url}: "
                f"Status {response.status_code}, Response: {response.text}"
            )
            return False
    except Exception as e:
        logger.error(f"Error sending Google Chat card to {webhook_url}: {str(e)}")
        return False

def send_scheduled_alerts(app):
    with app.app_context():
        try:
            from app.database import get_alert_settings, get_expiring_assets, get_recently_expired_assets
            settings = get_alert_settings()
            
            # Expiring soon alerts
            expiring = get_expiring_assets(30)
            if expiring:
                for s in settings:
                    if s['alert_type'] in ('all', 'warning'):
                        for item in expiring:
                            card = build_alert_card('warning', item, 30)
                            send_google_chat_card(s['webhook_url'], card)
            
            # Expired alerts
            expired = get_recently_expired_assets(30)
            if expired:
                for s in settings:
                    if s['alert_type'] in ('all', 'danger'):
                        for item in expired:
                            card = build_alert_card('danger', item, 30)
                            send_google_chat_card(s['webhook_url'], card)
            
            logger.info("Scheduled card alerts sent successfully")
        except Exception as e:
            logger.error(f"Error sending scheduled card alerts: {str(e)}")

@main_bp.route('/')
def dashboard():
    try:
        logger.info("Dashboard accessed")
        db = get_db()
        cursor = db.cursor()
        
        stats = calculate_warranty_stats()
        alerts = generate_alerts()
        
        status_filter = request.args.get('status', 'all')
        manufacturer_filter = request.args.get('manufacturer', 'all')
        page = int(request.args.get('page', 1))
        
        logger.debug(f"Dashboard filters - Status: {status_filter}, Manufacturer: {manufacturer_filter}, Page: {page}")
        
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
        
        if status_filter != 'all':
            if status_filter == 'Active':
                where_clauses.append("warranty_end_date > date('now', '+90 days')")
            elif status_filter == 'Expiring Soon':
                where_clauses.append("warranty_end_date BETWEEN date('now') AND date('now', '+90 days')")
            elif status_filter == 'Expired':
                where_clauses.append("warranty_end_date < date('now')")
        
        if manufacturer_filter != 'all':
            where_clauses.append("manufacturer = ?")
            params.append(manufacturer_filter)
        
        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)
        
        count_query = "SELECT COUNT(*) FROM (" + base_query + ")"
        cursor.execute(count_query, tuple(params))
        total_items = cursor.fetchone()[0]
        
        total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
        offset = (page - 1) * ITEMS_PER_PAGE
        
        base_query += " ORDER BY warranty_end_date DESC LIMIT ? OFFSET ?"
        params.extend([ITEMS_PER_PAGE, offset])
        
        cursor.execute(base_query, tuple(params))
        assets = cursor.fetchall()
        
        cursor.execute("""
            SELECT manufacturer, COUNT(*) as count 
            FROM assets 
            GROUP BY manufacturer 
            ORDER BY count DESC
            LIMIT 10
        """)
        manufacturers = cursor.fetchall()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            logger.debug("Dashboard AJAX request handled")
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
        
        logger.info("Dashboard rendered successfully")
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
    except Exception as e:
        logger.exception("Error loading dashboard")
        return render_template('error.html', message="Failed to load dashboard"), 500

@main_bp.route('/alerts/details')
def alert_details():
    try:
        alert_type = request.args.get('type', '')
        manufacturer = request.args.get('manufacturer', '')
        model = request.args.get('model', '')
        days = request.args.get('days', 30)
        
        logger.info(f"Alert details requested - Type: {alert_type}, Manufacturer: {manufacturer}, Model: {model}, Days: {days}")
        
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
        
        count_query = "SELECT COUNT(*) FROM (" + base_query + ")"
        cursor.execute(count_query, tuple(params))
        total_count = cursor.fetchone()[0]
        
        logger.info(f"Alert details fetched: {len(assets)} assets found")
        
        return jsonify({
            'assets': [dict(asset) for asset in assets],
            'total_count': total_count
        })
    except Exception as e:
        logger.exception("Failed to get alert details")
        return jsonify({'error': 'Internal server error'}), 500

@main_bp.route('/alerts/export')
def export_alert_details():
    try:
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
        
        logger.info(f"Exported {len(assets)} assets to CSV")
        
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=alert_details_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response.headers['Content-type'] = 'text/csv'
        
        return response
    except Exception as e:
        logger.exception("Failed to export alert details")
        return jsonify({'error': 'Internal server error'}), 500

@main_bp.route('/alert-settings', methods=['GET'])
def alert_settings():
    try:
        settings = get_alert_settings()
        alert_cron = get_app_setting('alert_cron', current_app.config.get('ALERT_CRON', '0 8 * * *'))
        logger.info("Alert settings page accessed")
        return render_template('alert_settings.html', settings=settings, alert_cron=alert_cron)
    except Exception as e:
        logger.exception("Error loading alert settings")
        return render_template('error.html', message="Failed to load alert settings"), 500

@main_bp.route('/alert-settings/add', methods=['POST'])
def add_alert_setting_route():
    try:
        name = request.form.get('name')
        webhook_url = request.form.get('webhook_url')
        alert_type = request.form.get('alert_type')
        
        if not (name and webhook_url and alert_type):
            logger.warning("Add alert setting failed: Missing required fields")
            return jsonify({'success': False, 'message': 'All fields are required.'}), 400
        
        add_alert_setting(name, webhook_url, alert_type)
        logger.info(f"Added new alert setting: {name} ({alert_type})")
        return jsonify({'success': True, 'message': 'Alert setting added.'})
    except Exception as e:
        logger.exception("Failed to add alert setting")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@main_bp.route('/alert-settings/remove/<int:setting_id>', methods=['POST'])
def remove_alert_setting_route(setting_id):
    try:
        remove_alert_setting(setting_id)
        logger.info(f"Removed alert setting: ID={setting_id}")
        return jsonify({'success': True, 'message': 'Alert setting removed.'})
    except Exception as e:
        logger.exception(f"Failed to remove alert setting {setting_id}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@main_bp.route('/alert-settings/test', methods=['POST'])
def test_alert_settings():
    try:
        message = request.form.get('message', 'This is a test alert from WarrantyTrack.')
        settings = get_alert_settings()
        results = []
        
        if not settings:
            logger.warning("Test alert failed: No active alert settings")
            return jsonify({'results': []})
        
        # Create a test card
        test_item = {
            'manufacturer': 'Test Manufacturer',
            'model': 'Test Model',
            'count': 5
        }
        test_card = build_alert_card('info', test_item, 7)
        test_card['cardsV2'][0]['card']['header']['title'] = "Test Alert"
        test_card['cardsV2'][0]['card']['header']['subtitle'] = "This is a test notification"
        
        # Add custom message to card
        test_card['cardsV2'][0]['card']['sections'][0]['widgets'].insert(0, {
            "decoratedText": {
                "text": f"<b>Test Message:</b> {message}",
                "wrapText": True
            }
        })
        
        for s in settings:
            try:
                ok = send_google_chat_card(s['webhook_url'], test_card)
                results.append({
                    'name': s['name'], 
                    'webhook_url': s['webhook_url'], 
                    'success': ok
                })
            except Exception as e:
                logger.error(f"Error sending test to {s['webhook_url']}: {str(e)}")
                results.append({
                    'name': s['name'], 
                    'webhook_url': s['webhook_url'], 
                    'success': False
                })
        
        logger.info(f"Test card alerts sent to {len(settings)} webhooks")
        return jsonify({'results': results})
    except Exception as e:
        logger.exception("Failed to send test alerts")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500

@main_bp.route('/alert-settings/schedule', methods=['POST'])
def update_alert_cron():
    try:
        cron = request.form.get('cron', '').strip()
        if not cron or len(cron.split()) != 5:
            logger.warning(f"Invalid cron format: '{cron}'")
            return jsonify({'success': False, 'message': 'Invalid cron format. Use 5 fields: min hour day month day_of_week.'})
        
        set_app_setting('alert_cron', cron)
        current_app.config['ALERT_CRON'] = cron
        logger.info(f"Updated alert cron schedule: {cron}")
        
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
                logger.info("Rescheduled alert job successfully")
                return jsonify({'success': True, 'message': f'Schedule updated to: {cron}'})
            except Exception as e:
                logger.exception("Failed to reschedule alert job")
                return jsonify({'success': False, 'message': f'Failed to update schedule: {e}'})
        
        logger.warning("Scheduler not running while updating cron")
        return jsonify({'success': False, 'message': 'Scheduler not running.'})
    except Exception as e:
        logger.exception("Failed to update alert schedule")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500