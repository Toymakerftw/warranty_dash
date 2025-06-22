from flask import Blueprint, request, jsonify, make_response, current_app
from flask_login import login_required, current_user
from app.database import get_db
from datetime import datetime
import logging
import io
import csv
import urllib.parse
import time
import requests
from app.routes.stats import get_expiring_assets, get_recently_expired_assets, get_recently_added_assets

logger = logging.getLogger(__name__)
alerts_bp = Blueprint('alerts', __name__)

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

@alerts_bp.route('/alerts/refresh')
@login_required
def refresh_alerts():
    """Refresh alerts data via AJAX"""
    try:
        logger.info(f"Alerts refresh requested by user: {current_user.username}")
        
        # Generate fresh alerts
        alerts = generate_alerts()
        
        # Return alerts as JSON
        return jsonify({
            'success': True,
            'alerts': alerts,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error refreshing alerts: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to refresh alerts',
            'alerts': []
        }), 500

@alerts_bp.route('/alerts/details')
@login_required
def alert_details():
    """Get detailed alert information"""
    try:
        logger.info(f"Alert details requested by user: {current_user.username}")
        alert_type = request.args.get('type', 'warning')
        manufacturer = request.args.get('manufacturer', '')
        model = request.args.get('model', '')
        days = int(request.args.get('days', 30))
        
        db = get_db()
        cursor = db.cursor()
        
        if alert_type == 'warning':
            # Assets expiring soon
            cursor.execute("""
                SELECT * FROM assets 
                WHERE manufacturer = ? AND warranty_end_date BETWEEN date('now') AND date('now', ?)
                ORDER BY warranty_end_date
            """, (manufacturer, f"+{days} days"))
        elif alert_type == 'danger':
            # Recently expired assets
            cursor.execute("""
                SELECT * FROM assets 
                WHERE manufacturer = ? AND warranty_end_date BETWEEN date('now', ?) AND date('now')
                ORDER BY warranty_end_date
            """, (manufacturer, f"-{days} days"))
        else:
            # New assets
            cursor.execute("""
                SELECT * FROM assets 
                WHERE manufacturer = ? AND DATE(created_at) > date('now', ?)
                ORDER BY created_at DESC
            """, (manufacturer, f"-{days} days"))
        
        assets = cursor.fetchall()
        
        return jsonify({
            'type': alert_type,
            'manufacturer': manufacturer,
            'model': model,
            'days': days,
            'count': len(assets),
            'assets': [dict(asset) for asset in assets]
        })
        
    except Exception as e:
        logger.error(f"Error getting alert details: {str(e)}")
        return jsonify({'error': 'Failed to get alert details'}), 500

@alerts_bp.route('/alerts/stats')
@login_required
def alert_stats():
    """Get alert statistics for dashboard"""
    try:
        logger.info(f"Alert stats requested by user: {current_user.username}")
        
        db = get_db()
        cursor = db.cursor()
        
        # Get various alert counts
        cursor.execute("""
            SELECT COUNT(*) FROM assets 
            WHERE warranty_end_date BETWEEN date('now') AND date('now', '+30 days')
        """)
        expiring_soon_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM assets 
            WHERE warranty_end_date < date('now')
        """)
        expired_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM assets 
            WHERE DATE(created_at) > date('now', '-7 days')
        """)
        new_assets_count = cursor.fetchone()[0]
        
        return jsonify({
            'success': True,
            'stats': {
                'expiring_soon': expiring_soon_count,
                'expired': expired_count,
                'new_assets': new_assets_count,
                'total_alerts': expiring_soon_count + expired_count + new_assets_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting alert stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get alert statistics'
        }), 500
