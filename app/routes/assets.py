from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify, send_file
from app.database import get_db, normalize_date
import csv
from io import TextIOWrapper, StringIO, BytesIO
import logging
from datetime import datetime

# Initialize logger
logger = logging.getLogger(__name__)

assets_bp = Blueprint('assets', __name__, url_prefix='/assets')

@assets_bp.route('/upload', methods=['GET', 'POST'])
def upload_csv():
    if request.method == 'POST':
        file = request.files['csv_file']
        if file and (file.filename.endswith('.csv') or file.filename.endswith('.txt')):
            try:
                logger.info(f"CSV upload started: {file.filename}")
                # Parse CSV data with error handling
                csv_file = TextIOWrapper(file.stream, encoding='utf-8', errors='replace')
                reader = csv.DictReader(csv_file)
                
                db = get_db()
                cursor = db.cursor()
                
                count = 0
                errors = 0
                skipped = 0
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Skip empty rows
                        if not any(row.values()):
                            skipped += 1
                            continue
                            
                        # Get and clean fields
                        asset_tag = clean_field(row.get('asset_tag'))
                        service_tag = clean_field(row.get('service_tag'))
                        manufacturer = clean_field(row.get('manufacturer'))
                        model = clean_field(row.get('model', ''))
                        
                        # Handle warranty date
                        warranty_date = normalize_date(row.get('warranty_end_date', ''))
                        
                        # Validate required fields
                        if not asset_tag or not service_tag or not manufacturer:
                            errors += 1
                            logger.warning(f"Row {row_num}: Missing required fields - {row}")
                            continue
                            
                        # Insert into database with created_at timestamp
                        cursor.execute('''
                            INSERT INTO assets (
                                asset_tag, 
                                service_tag, 
                                manufacturer, 
                                model,
                                warranty_end_date,
                                created_at
                            ) VALUES (?, ?, ?, ?, ?, datetime('now'))
                        ''', (
                            asset_tag,
                            service_tag,
                            manufacturer,
                            model,
                            warranty_date
                        ))
                        count += 1
                        
                    except Exception as e:
                        errors += 1
                        logger.error(f"Error processing row {row_num}: {str(e)} - Data: {row}")
                
                db.commit()
                
                # Prepare feedback message
                if count == 0:
                    flash('No valid assets were imported', 'danger')
                    logger.warning("CSV upload completed with no valid assets")
                elif errors == 0:
                    flash(f'Successfully imported {count} assets', 'success')
                    logger.info(f"CSV upload completed: {count} assets imported")
                else:
                    message = f'Imported {count} assets with {errors} errors and {skipped} empty rows skipped'
                    flash(message, 'warning' if count > 0 else 'danger')
                    logger.warning(message)
                
                return redirect(url_for('main.dashboard'))
                
            except Exception as e:
                db.rollback()
                logger.exception(f"CSV processing failed: {str(e)}")
                flash('Failed to process CSV file. Please check the format.', 'danger')
        else:
            logger.warning("Invalid file type uploaded")
            flash('Please upload a valid CSV or TXT file', 'danger')
    
    logger.debug("CSV upload page accessed")
    return render_template('upload.html')

@assets_bp.route('/edit/<int:asset_id>', methods=['GET', 'POST'])
def edit_asset(asset_id):
    db = get_db()
    cursor = db.cursor()
    
    if request.method == 'POST':
        try:
            logger.info(f"Editing asset: ID={asset_id}")
            # Get form data
            form_data = {
                'asset_tag': request.form['asset_tag'].strip(),
                'service_tag': request.form['service_tag'].strip(),
                'manufacturer': request.form['manufacturer'].strip(),
                'model': request.form.get('model', '').strip(),
                'warranty_end_date': normalize_date(request.form['warranty_end_date']),
                'purchase_date': normalize_date(request.form.get('purchase_date', '')),
                'notes': request.form.get('notes', '').strip()
            }
            
            # Validate required fields
            if not all([form_data['asset_tag'], form_data['service_tag'], form_data['manufacturer']]):
                flash('Asset Tag, Service Tag, and Manufacturer are required', 'danger')
                logger.warning(f"Edit asset failed: Missing required fields for asset {asset_id}")
                return redirect(url_for('assets.edit_asset', asset_id=asset_id))
            
            # Update asset in database (preserve created_at)
            cursor.execute('''
                UPDATE assets SET
                    asset_tag = ?,
                    service_tag = ?,
                    manufacturer = ?,
                    model = ?,
                    warranty_end_date = ?,
                    purchase_date = ?,
                    notes = ?
                WHERE id = ?
            ''', (
                form_data['asset_tag'],
                form_data['service_tag'],
                form_data['manufacturer'],
                form_data['model'],
                form_data['warranty_end_date'],
                form_data['purchase_date'],
                form_data['notes'],
                asset_id
            ))
            db.commit()
            
            flash('Asset updated successfully!', 'success')
            logger.info(f"Asset updated: ID={asset_id}")
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            db.rollback()
            logger.exception(f"Error updating asset {asset_id}: {str(e)}")
            flash('Failed to update asset', 'danger')
            return redirect(url_for('assets.edit_asset', asset_id=asset_id))
    
    # GET request - show edit form
    try:
        logger.debug(f"Edit asset page accessed: ID={asset_id}")
        cursor.execute("""
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
            WHERE id = ?
        """, (asset_id,))
        asset = cursor.fetchone()
        
        if not asset:
            flash('Asset not found', 'danger')
            logger.warning(f"Asset not found: ID={asset_id}")
            return redirect(url_for('main.dashboard'))
            
        return render_template('edit_asset.html', asset=asset)
        
    except Exception as e:
        logger.exception(f"Error fetching asset {asset_id}: {str(e)}")
        flash('Failed to load asset', 'danger')
        return redirect(url_for('main.dashboard'))

@assets_bp.route('/delete/<int:asset_id>', methods=['GET', 'DELETE'])
def delete_asset(asset_id):
    try:
        logger.info(f"Deleting asset: ID={asset_id}")
        db = get_db()
        cursor = db.cursor()
        
        # First check if asset exists
        cursor.execute("SELECT 1 FROM assets WHERE id = ?", (asset_id,))
        if not cursor.fetchone():
            if request.method == 'DELETE':
                logger.warning(f"Delete failed: Asset not found - ID={asset_id}")
                return jsonify({'success': False, 'message': 'Asset not found'}), 404
            flash('Asset not found', 'danger')
            return redirect(url_for('main.dashboard'))
            
        # Delete the asset
        cursor.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        db.commit()
        
        if request.method == 'DELETE':
            # Return success with stats for AJAX requests
            from app.database import calculate_warranty_stats
            logger.info(f"Asset deleted: ID={asset_id}")
            return jsonify({
                'success': True,
                'message': 'Asset deleted successfully!',
                'stats': calculate_warranty_stats()
            })
        
        # For GET requests (normal browser navigation)
        flash('Asset deleted successfully!', 'success')
        return redirect(url_for('main.dashboard'))
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Error deleting asset {asset_id}: {str(e)}")
        if request.method == 'DELETE':
            return jsonify({'success': False, 'message': 'Failed to delete asset'}), 500
        flash('Failed to delete asset', 'danger')
        return redirect(url_for('main.dashboard'))

@assets_bp.route('/download-template')
def download_template():
    """Download a CSV template for asset uploads"""
    try:
        logger.info("CSV template download requested")
        
        # Create a StringIO object to write CSV data
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header row with column names
        writer.writerow([
            'asset_tag',
            'manufacturer', 
            'service_tag',
            'model',
            'warranty_end_date',
            'purchase_date',
            'notes'
        ])
        
        # Write example rows
        writer.writerow([
            'LAPTOP001',
            'Dell',
            'ABC123XYZ',
            'Latitude 5520',
            '2025-12-31',
            '2023-01-15',
            'IT Department laptop'
        ])
        writer.writerow([
            'DESKTOP002',
            'HP',
            'HP789DEF',
            'EliteDesk 800',
            '2024-06-30',
            '2022-03-20',
            'Finance department'
        ])
        writer.writerow([
            'TABLET003',
            'Apple',
            'AP456GHI',
            'iPad Pro 12.9',
            '2025-03-15',
            '2023-09-10',
            'Sales team tablet'
        ])
        
        # Get the CSV content and convert to bytes
        csv_content = output.getvalue()
        output.close()
        
        # Create a BytesIO object for binary data
        csv_file = BytesIO(csv_content.encode('utf-8'))
        
        logger.info("CSV template generated successfully")
        
        # Return the file as a download
        return send_file(
            csv_file,
            mimetype='text/csv',
            as_attachment=True,
            download_name='warranty_assets_template.csv'
        )
        
    except Exception as e:
        logger.exception(f"Error generating CSV template: {str(e)}")
        flash('Failed to generate template file', 'danger')
        return redirect(url_for('assets.upload_csv'))

def clean_field(value):
    """Clean and normalize a field value"""
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None