from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.database import get_alert_settings, get_app_setting, add_alert_setting, remove_alert_setting, set_app_setting
from app.routes.alerts import build_alert_card, send_google_chat_card
from flask import current_app
import logging

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/alert-settings', methods=['GET'])
@login_required
def alert_settings():
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required to access alert settings.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        logger.info(f"Alert settings page accessed by admin: {current_user.username}")
        settings = get_alert_settings()
        alert_cron = get_app_setting('alert_cron', current_app.config.get('ALERT_CRON', '0 8 * * *'))
        return render_template('alert_settings.html', settings=settings, alert_cron=alert_cron)
    except Exception as e:
        logger.exception("Error loading alert settings")
        return render_template('error.html', message="Failed to load alert settings"), 500

@settings_bp.route('/alert-settings/add', methods=['POST'])
@login_required
def add_alert_setting_route():
    # Check if user is admin
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
    
    try:
        name = request.form.get('name')
        webhook_url = request.form.get('webhook_url')
        alert_type = request.form.get('alert_type')
        
        if not (name and webhook_url and alert_type):
            logger.warning(f"Add alert setting failed by user {current_user.username}: Missing required fields")
            return jsonify({'success': False, 'message': 'All fields are required.'}), 400
        
        add_alert_setting(name, webhook_url, alert_type, current_user.id)
        logger.info(f"Added new alert setting by admin {current_user.username}: {name} ({alert_type})")
        return jsonify({'success': True, 'message': 'Alert setting added.'})
    except Exception as e:
        logger.exception("Failed to add alert setting")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@settings_bp.route('/alert-settings/remove/<int:setting_id>', methods=['POST'])
@login_required
def remove_alert_setting_route(setting_id):
    # Check if user is admin
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
    
    try:
        remove_alert_setting(setting_id)
        logger.info(f"Removed alert setting by admin {current_user.username}: ID={setting_id}")
        return jsonify({'success': True, 'message': 'Alert setting removed.'})
    except Exception as e:
        logger.exception(f"Failed to remove alert setting {setting_id}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@settings_bp.route('/alert-settings/test', methods=['POST'])
@login_required
def test_alert_settings():
    # Check if user is admin
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied. Admin privileges required.'}), 403
    
    try:
        message = request.form.get('message', 'This is a test alert from WarrantyTrack.')
        settings = get_alert_settings()
        results = []
        
        if not settings:
            logger.warning(f"Test alert failed by admin {current_user.username}: No active alert settings")
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
        
        logger.info(f"Test card alerts sent by admin {current_user.username} to {len(settings)} webhooks")
        return jsonify({'results': results})
    except Exception as e:
        logger.exception("Failed to send test alerts")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500

@settings_bp.route('/alert-settings/schedule', methods=['POST'])
@login_required
def update_alert_cron():
    # Check if user is admin
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
    
    try:
        cron = request.form.get('cron', '').strip()
        if not cron or len(cron.split()) != 5:
            logger.warning(f"Invalid cron format by admin {current_user.username}: '{cron}'")
            return jsonify({'success': False, 'message': 'Invalid cron format. Use 5 fields: min hour day month day_of_week.'})
        
        set_app_setting('alert_cron', cron)
        current_app.config['ALERT_CRON'] = cron
        logger.info(f"Updated alert cron schedule by admin {current_user.username}: {cron}")
        
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