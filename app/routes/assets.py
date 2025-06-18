from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from app.database import get_db, normalize_date
import csv
from io import TextIOWrapper
import logging
from datetime import datetime

assets_bp = Blueprint('assets', __name__, url_prefix='/assets')

@assets_bp.route('/upload', methods=['GET', 'POST'])
def upload_csv():
    if request.method == 'POST':
        file = request.files['csv_file']
        if file and (file.filename.endswith('.csv') or file.filename.endswith('.txt')):
            try:
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
                            logging.warning(f"Row {row_num}: Missing required fields - {row}")
                            continue
                            
                        # Insert into database
                        cursor.execute('''
                            INSERT INTO assets (
                                asset_tag, 
                                service_tag, 
                                manufacturer, 
                                model,
                                warranty_end_date
                            ) VALUES (?, ?, ?, ?, ?)
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
                        logging.error(f"Error processing row {row_num}: {str(e)} - Data: {row}")
                
                db.commit()
                
                # Prepare feedback message
                if count == 0:
                    flash('No valid assets were imported', 'danger')
                elif errors == 0:
                    flash(f'Successfully imported {count} assets', 'success')
                else:
                    flash(
                        f'Imported {count} assets with {errors} errors and {skipped} empty rows skipped', 
                        'warning' if count > 0 else 'danger'
                    )
                
                return redirect(url_for('main.dashboard'))
                
            except Exception as e:
                db.rollback()
                logging.error(f"CSV processing failed: {str(e)}")
                flash('Failed to process CSV file. Please check the format.', 'danger')
        else:
            flash('Please upload a valid CSV or TXT file', 'danger')
    
    return render_template('upload.html')

@assets_bp.route('/edit/<int:asset_id>', methods=['GET', 'POST'])
def edit_asset(asset_id):
    db = get_db()
    cursor = db.cursor()
    
    if request.method == 'POST':
        try:
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
                return redirect(url_for('assets.edit_asset', asset_id=asset_id))
            
            # Update asset in database
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
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error updating asset {asset_id}: {str(e)}")
            flash('Failed to update asset', 'danger')
            return redirect(url_for('assets.edit_asset', asset_id=asset_id))
    
    # GET request - show edit form
    try:
        cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
        asset = cursor.fetchone()
        
        if not asset:
            flash('Asset not found', 'danger')
            return redirect(url_for('main.dashboard'))
            
        return render_template('edit_asset.html', asset=asset)
        
    except Exception as e:
        logging.error(f"Error fetching asset {asset_id}: {str(e)}")
        flash('Failed to load asset', 'danger')
        return redirect(url_for('main.dashboard'))

@assets_bp.route('/delete/<int:asset_id>', methods=['GET', 'DELETE'])
def delete_asset(asset_id):
    try:
        db = get_db()
        cursor = db.cursor()
        
        # First check if asset exists
        cursor.execute("SELECT 1 FROM assets WHERE id = ?", (asset_id,))
        if not cursor.fetchone():
            if request.method == 'DELETE':
                return jsonify({'success': False, 'message': 'Asset not found'}), 404
            flash('Asset not found', 'danger')
            return redirect(url_for('main.dashboard'))
            
        # Delete the asset
        cursor.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        db.commit()
        
        if request.method == 'DELETE':
            # Return success with stats for AJAX requests
            from app.database import calculate_warranty_stats
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
        logging.error(f"Error deleting asset {asset_id}: {str(e)}")
        if request.method == 'DELETE':
            return jsonify({'success': False, 'message': 'Failed to delete asset'}), 500
        flash('Failed to delete asset', 'danger')
        return redirect(url_for('main.dashboard'))

def clean_field(value):
    """Clean and normalize a field value"""
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None