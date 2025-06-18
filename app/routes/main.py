from flask import Blueprint, request, render_template, jsonify
from app.database import get_db, calculate_warranty_stats
from datetime import datetime
import math

main_bp = Blueprint('main', __name__)

ITEMS_PER_PAGE = 10  # Number of items to show per page

@main_bp.route('/')
def dashboard():
    db = get_db()
    cursor = db.cursor()
    
    # Calculate warranty stats
    stats = calculate_warranty_stats()
    
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
            'stats': stats
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
                         })