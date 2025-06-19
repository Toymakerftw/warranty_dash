from flask import Blueprint, render_template, request, jsonify
from app.database import get_db
import math
from .stats import calculate_warranty_stats, get_expiring_assets, get_recently_expired_assets, get_recently_added_assets
from .alerts import generate_alerts

# Initialize logger
import logging
logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)
ITEMS_PER_PAGE = 10  # Number of items to show per page

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