from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from db import db_connection, pd_connection
from utils import check_session

split_db_bp = Blueprint('split_db', __name__, template_folder='templates/split_dashboard')

@split_db_bp.route('/splitdashboard', methods=['GET'])
def splitdashboard():
    if not check_session(['AD','PD']):
        return redirect(url_for('home'))

    total_machines = 8
    final_machine_statuses = []
    for i in range(1, total_machines + 1):
        final_machine_statuses.append({
            'id': i,
            'status': 'Idle',
            'sequence': '-',
            'row_number':'-',
            'time_start': None,
            'time_start_iso': None
        })

    try:
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        query_daily_cut = """
            SELECT 
                cut_sequence, `date_cut`
            FROM
                masterpallet.daily_cut
            WHERE
                status != 'Cancel'
                Order by cut_sequence DESC
        """
        cursor.execute(query_daily_cut)
        query_daily_cut = cursor.fetchall() 

        # print(query_daily_cut)

    except Exception as e:
        print(f"Database Error: {e}")

    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            
    return render_template('split_dashboard/split_dashboard.html', machine_statuses=final_machine_statuses, query_daily_cut=query_daily_cut)

@split_db_bp.route('/get_daily_cut_detail/<int:cut_sequence>', methods=['GET'])
def get_daily_cut_detail(cut_sequence):
    if not check_session(['AD', 'PD']):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT
                sequence,
                delivery_date,
                customer,
                model_type,
                model,
                qty
            FROM 
                masterpallet.daily_cut_detail 
            WHERE cut_sequence = %s
        """
        cursor.execute(query, (cut_sequence,))
        details = cursor.fetchall()
        
        # Helper to ensure dates are serializable
        for row in details:
            for key, value in row.items():
                if hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()

        return jsonify(details)

    except Exception as e:
        print(f"Database Error: {e}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

@split_db_bp.route('/get_plan_details/<order_id>', methods=['GET'])
def get_plan_details(order_id):
    # order_id maps to sequence in the user's domain language
    if not check_session(['AD', 'PD']):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # 1. Fetch Plan Details (MasterPallet)
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT
                idplan_details,
                material_type,
                material_size,
                work_thickness - work_tolerance_thickness as thickness,
                work_width - work_tolerance_width as width,
                work_length as length,
                quantity
            FROM 
                masterpallet.plan_details 
            WHERE 
                order_id = %s
                AND plan_status != 'Cancel'
            ORDER BY idplan_details ASC
        """
        cursor.execute(query, (order_id,))
        plans = cursor.fetchall()
        
        cursor.close()
        conn.close()

        # 2. Fetch Start Split Status (Production)
        conn_pd = pd_connection()
        cursor_pd = conn_pd.cursor(dictionary=True)
        
        query_start = """
            SELECT 
                `row_number`, 
                `status`, 
                `matchine` 
            FROM 
                production.start_split 
            WHERE 
                sequence = %s
        """
        cursor_pd.execute(query_start, (order_id,))
        start_data = cursor_pd.fetchall()
        
        cursor_pd.close()
        conn_pd.close()
        
        # Map start data by row_number
        start_map = {row['row_number']: row for row in start_data}
        
        # 3. Merge Data
        for index, row in enumerate(plans):
            rn = index + 1 # Calculate row_number (1-based)
            row['row_number'] = rn
            
            if rn in start_map:
                row['production_status'] = start_map[rn]['status']
                row['machine'] = start_map[rn]['matchine']
            else:
                row['production_status'] = 'Not Started'
                row['machine'] = '-'

            # Ensure serializable
            for key, value in row.items():
                if hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        
        return jsonify(plans)

    except Exception as e:
        print(f"Database Error: {e}")
        return jsonify({'error': str(e)}), 500