from flask import Blueprint, request, jsonify, make_response, current_app
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

@alerts_bp.route('/alerts/details')
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
