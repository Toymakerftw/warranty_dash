from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from app.database import get_db, calculate_warranty_stats
from datetime import datetime, timedelta
import csv
import io
import json
import logging

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports')
@login_required
def reports_dashboard():
    """Main reports dashboard"""
    logger.info(f"Reports dashboard accessed by user: {current_user.username}")
    return render_template('reports_dashboard.html', now=datetime.now(), timedelta=timedelta)

@reports_bp.route('/reports/charts')
@login_required
def reports_dashboard_charts():
    """Reports dashboard with charts (use with caution)"""
    logger.info(f"Reports dashboard with charts accessed by user: {current_user.username}")
    return render_template('reports_dashboard.html', now=datetime.now(), timedelta=timedelta)

@reports_bp.route('/reports/monthly')
@login_required
def monthly_report():
    """Generate monthly report"""
    try:
        logger.info(f"Monthly report requested by user: {current_user.username}")
        month = request.args.get('month', datetime.now().strftime('%Y-%m'))
        year, month = month.split('-')
        
        db = get_db()
        cursor = db.cursor()
        
        # Get assets for the specified month
        cursor.execute("""
            SELECT * FROM assets 
            WHERE strftime('%Y-%m', warranty_end_date) = ?
            ORDER BY warranty_end_date
        """, (f"{year}-{month}",))
        
        assets = cursor.fetchall()
        
        # Calculate monthly statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN warranty_end_date < date('now') THEN 1 END) as expired,
                COUNT(CASE WHEN warranty_end_date BETWEEN date('now') AND date('now', '+30 days') THEN 1 END) as expiring_soon,
                COUNT(CASE WHEN warranty_end_date > date('now', '+30 days') THEN 1 END) as active
            FROM assets 
            WHERE strftime('%Y-%m', warranty_end_date) = ?
        """, (f"{year}-{month}",))
        
        stats = cursor.fetchone()
        
        # Get manufacturer breakdown
        cursor.execute("""
            SELECT manufacturer, COUNT(*) as count
            FROM assets 
            WHERE strftime('%Y-%m', warranty_end_date) = ?
            GROUP BY manufacturer
            ORDER BY count DESC
        """, (f"{year}-{month}",))
        
        manufacturer_stats = cursor.fetchall()
        
        return render_template('monthly_report.html', 
                             assets=assets, 
                             stats=stats, 
                             manufacturer_stats=manufacturer_stats,
                             month=month,
                             year=year,
                             now=datetime.now(),
                             timedelta=timedelta)
    except Exception as e:
        logger.error(f"Error generating monthly report: {str(e)}")
        return render_template('error.html', error="Failed to generate monthly report"), 500

@reports_bp.route('/reports/custom')
@login_required
def custom_report():
    """Generate custom date range report"""
    try:
        logger.info(f"Custom report requested by user: {current_user.username}")
        start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        report_type = request.args.get('type', 'warranty_expiry')
        
        db = get_db()
        cursor = db.cursor()
        
        if report_type == 'warranty_expiry':
            cursor.execute("""
                SELECT * FROM assets 
                WHERE warranty_end_date BETWEEN ? AND ?
                ORDER BY warranty_end_date
            """, (start_date, end_date))
        elif report_type == 'purchase_date':
            cursor.execute("""
                SELECT * FROM assets 
                WHERE purchase_date BETWEEN ? AND ?
                ORDER BY purchase_date
            """, (start_date, end_date))
        elif report_type == 'created_date':
            cursor.execute("""
                SELECT * FROM assets 
                WHERE DATE(created_at) BETWEEN ? AND ?
                ORDER BY created_at
            """, (start_date, end_date))
        
        assets = cursor.fetchall()
        
        # Calculate statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN warranty_end_date < date('now') THEN 1 END) as expired,
                COUNT(CASE WHEN warranty_end_date BETWEEN date('now') AND date('now', '+30 days') THEN 1 END) as expiring_soon,
                COUNT(CASE WHEN warranty_end_date > date('now', '+30 days') THEN 1 END) as active
            FROM assets 
            WHERE warranty_end_date BETWEEN ? AND ?
        """, (start_date, end_date))
        
        stats = cursor.fetchone()
        
        return render_template('custom_report.html', 
                             assets=assets, 
                             stats=stats,
                             start_date=start_date,
                             end_date=end_date,
                             report_type=report_type,
                             now=datetime.now(),
                             timedelta=timedelta)
    except Exception as e:
        logger.error(f"Error generating custom report: {str(e)}")
        return render_template('error.html', error="Failed to generate custom report"), 500

@reports_bp.route('/reports/expiring')
@login_required
def expiring_report():
    """Generate report for assets expiring soon"""
    try:
        logger.info(f"Expiring report requested by user: {current_user.username}")
        days = int(request.args.get('days', 30))
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT * FROM assets 
            WHERE warranty_end_date BETWEEN date('now') AND date('now', ?)
            ORDER BY warranty_end_date
        """, (f"+{days} days",))
        
        assets = cursor.fetchall()
        
        # Calculate days left for each asset
        current_date = datetime.now().date()
        
        # Convert sqlite3.Row objects to dictionaries and add days_left
        processed_assets = []
        for asset in assets:
            # Convert Row to dict
            asset_dict = dict(asset)
            
            if asset_dict['warranty_end_date']:
                try:
                    end_date = datetime.strptime(asset_dict['warranty_end_date'], '%Y-%m-%d').date()
                    days_left = (end_date - current_date).days
                    asset_dict['days_left'] = days_left
                except ValueError:
                    asset_dict['days_left'] = None
            else:
                asset_dict['days_left'] = None
            
            processed_assets.append(asset_dict)
        
        # Group by manufacturer
        cursor.execute("""
            SELECT manufacturer, COUNT(*) as count
            FROM assets 
            WHERE warranty_end_date BETWEEN date('now') AND date('now', ?)
            GROUP BY manufacturer
            ORDER BY count DESC
        """, (f"+{days} days",))
        
        manufacturer_stats = cursor.fetchall()
        
        return render_template('expiring_report.html', 
                             assets=processed_assets, 
                             manufacturer_stats=manufacturer_stats,
                             days=days,
                             now=datetime.now(),
                             timedelta=timedelta)
    except Exception as e:
        logger.error(f"Error generating expiring report: {str(e)}")
        return render_template('error.html', error="Failed to generate expiring report"), 500

@reports_bp.route('/reports/manufacturer')
@login_required
def manufacturer_report():
    """Generate manufacturer-specific report"""
    try:
        logger.info(f"Manufacturer report requested by user: {current_user.username}")
        manufacturer = request.args.get('manufacturer', '')
        
        db = get_db()
        cursor = db.cursor()
        
        if manufacturer:
            cursor.execute("""
                SELECT * FROM assets 
                WHERE manufacturer LIKE ?
                ORDER BY warranty_end_date
            """, (f"%{manufacturer}%",))
        else:
            cursor.execute("""
                SELECT manufacturer, COUNT(*) as count,
                       COUNT(CASE WHEN warranty_end_date < date('now') THEN 1 END) as expired,
                       COUNT(CASE WHEN warranty_end_date BETWEEN date('now') AND date('now', '+30 days') THEN 1 END) as expiring_soon
                FROM assets 
                GROUP BY manufacturer
                ORDER BY count DESC
            """)
        
        assets = cursor.fetchall()
        
        # Calculate days left for each asset if we have individual assets
        if manufacturer:
            current_date = datetime.now().date()
            
            # Convert sqlite3.Row objects to dictionaries and add days_left
            processed_assets = []
            for asset in assets:
                # Convert Row to dict
                asset_dict = dict(asset)
                
                if asset_dict['warranty_end_date']:
                    try:
                        end_date = datetime.strptime(asset_dict['warranty_end_date'], '%Y-%m-%d').date()
                        days_left = (end_date - current_date).days
                        asset_dict['days_left'] = days_left
                    except ValueError:
                        asset_dict['days_left'] = None
                else:
                    asset_dict['days_left'] = None
                
                processed_assets.append(asset_dict)
            
            assets = processed_assets
        
        return render_template('manufacturer_report.html', 
                             assets=assets, 
                             manufacturer=manufacturer,
                             now=datetime.now(),
                             timedelta=timedelta)
    except Exception as e:
        logger.error(f"Error generating manufacturer report: {str(e)}")
        return render_template('error.html', error="Failed to generate manufacturer report"), 500

@reports_bp.route('/reports/export/<report_type>')
@login_required
def export_report(report_type):
    """Export report as CSV"""
    try:
        logger.info(f"Report export requested by user {current_user.username}: {report_type}")
        db = get_db()
        cursor = db.cursor()
        
        if report_type == 'monthly':
            month = request.args.get('month', datetime.now().strftime('%Y-%m'))
            year, month = month.split('-')
            
            cursor.execute("""
                SELECT asset_tag, service_tag, manufacturer, model, 
                       warranty_end_date, purchase_date, notes
                FROM assets 
                WHERE strftime('%Y-%m', warranty_end_date) = ?
                ORDER BY warranty_end_date
            """, (f"{year}-{month}",))
            
            filename = f"monthly_report_{year}_{month}.csv"
            
        elif report_type == 'custom':
            start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
            report_type_filter = request.args.get('type', 'warranty_expiry')
            
            if report_type_filter == 'warranty_expiry':
                cursor.execute("""
                    SELECT asset_tag, service_tag, manufacturer, model, 
                           warranty_end_date, purchase_date, notes
                    FROM assets 
                    WHERE warranty_end_date BETWEEN ? AND ?
                    ORDER BY warranty_end_date
                """, (start_date, end_date))
            elif report_type_filter == 'purchase_date':
                cursor.execute("""
                    SELECT asset_tag, service_tag, manufacturer, model, 
                           warranty_end_date, purchase_date, notes
                    FROM assets 
                    WHERE purchase_date BETWEEN ? AND ?
                    ORDER BY purchase_date
                """, (start_date, end_date))
            
            filename = f"custom_report_{start_date}_to_{end_date}.csv"
            
        elif report_type == 'expiring':
            days = int(request.args.get('days', 30))
            
            cursor.execute("""
                SELECT asset_tag, service_tag, manufacturer, model, 
                       warranty_end_date, purchase_date, notes
                FROM assets 
                WHERE warranty_end_date BETWEEN date('now') AND date('now', ?)
                ORDER BY warranty_end_date
            """, (f"+{days} days",))
            
            filename = f"expiring_report_{days}_days.csv"
            
        else:
            return jsonify({'error': 'Invalid report type'}), 400
        
        assets = cursor.fetchall()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Asset Tag', 'Service Tag', 'Manufacturer', 'Model', 
                        'Warranty End Date', 'Purchase Date', 'Notes'])
        
        # Write data
        for asset in assets:
            writer.writerow([
                asset['asset_tag'] or '',
                asset['service_tag'] or '',
                asset['manufacturer'] or '',
                asset['model'] or '',
                asset['warranty_end_date'] or '',
                asset['purchase_date'] or '',
                asset['notes'] or ''
            ])
        
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error exporting report: {str(e)}")
        return jsonify({'error': 'Failed to export report'}), 500

@reports_bp.route('/api/reports/stats')
@login_required
def get_report_stats():
    """Get statistics for reports dashboard"""
    try:
        logger.info(f"Report stats requested by user: {current_user.username}")
        db = get_db()
        cursor = db.cursor()
        
        # Overall stats
        overall_stats = calculate_warranty_stats()
        
        # Monthly breakdown for current year (limit to 12 months)
        current_year = datetime.now().year
        cursor.execute("""
            SELECT strftime('%m', warranty_end_date) as month,
                   COUNT(*) as count
            FROM assets 
            WHERE strftime('%Y', warranty_end_date) = ?
            GROUP BY month
            ORDER BY month
            LIMIT 12
        """, (str(current_year),))
        
        monthly_data = cursor.fetchall()
        
        # Manufacturer breakdown (limit to top 10)
        cursor.execute("""
            SELECT manufacturer, COUNT(*) as count
            FROM assets 
            GROUP BY manufacturer
            ORDER BY count DESC
            LIMIT 10
        """)
        
        manufacturer_data = cursor.fetchall()
        
        # Assets expiring in next 30, 60, 90 days
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN warranty_end_date BETWEEN date('now') AND date('now', '+30 days') THEN 1 END) as next_30,
                COUNT(CASE WHEN warranty_end_date BETWEEN date('now', '+31 days') AND date('now', '+60 days') THEN 1 END) as next_60,
                COUNT(CASE WHEN warranty_end_date BETWEEN date('now', '+61 days') AND date('now', '+90 days') THEN 1 END) as next_90
            FROM assets
        """)
        
        expiring_data = cursor.fetchone()
        
        return jsonify({
            'overall_stats': overall_stats,
            'monthly_data': [{'month': row['month'], 'count': row['count']} for row in monthly_data],
            'manufacturer_data': [{'manufacturer': row['manufacturer'], 'count': row['count']} for row in manufacturer_data],
            'expiring_data': {
                'next_30': expiring_data['next_30'],
                'next_60': expiring_data['next_60'],
                'next_90': expiring_data['next_90']
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting report stats: {str(e)}")
        return jsonify({'error': 'Failed to get report statistics'}), 500 