from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from db import db_connection, pd_connection
from utils import check_session
from datetime import datetime, timedelta, timezone
import mysql.connector

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates/dashboard')

@dashboard_bp.route('/dashboard', methods=['GET'])
def dashboard():
    if 'loggedin' in session and session['loggedin'] == False:
        return render_template('index.html', username=session['username'])

    total_machines = 8
    total_assy_lines = 5
    
    # Initialize machine statuses
    final_machine_statuses = []
    for i in range(1, total_machines + 1):
        final_machine_statuses.append({
            'id': i,
            'name': f'Split Machine {i}',
            'status': 'Idle',
            'sequence': '-',
            'row_number': '-',
            'time_start': None,
            'time_start_iso': None
        })
    
    # Initialize assembly line statuses
    final_assy_statuses = []
    for i in range(1, total_assy_lines + 1):
        final_assy_statuses.append({
            'id': i,
            'name': f'Assembly Line {i}',
            'status': 'Idle',
            'model': '-',
            'sequence': '-',
            'time_start': None,
            'time_start_iso': None
        })

    try:
        conn2 = pd_connection()
        cursor2 = conn2.cursor(dictionary=True)

        # Query for running split machines
        query_running_machines = """
            SELECT 
                matchine, `row_number`, sequence, status, start_time
            FROM
                production.start_split
            WHERE
                status = 'Start'
        """
        cursor2.execute(query_running_machines)
        running_machines = cursor2.fetchall()

        if running_machines:
            for machine in running_machines:
                machine_id = machine['matchine']
                start_time_obj = machine['start_time']
                
                if 1 <= machine_id <= total_machines:
                    final_machine_statuses[machine_id - 1]['status'] = 'Running'
                    final_machine_statuses[machine_id - 1]['sequence'] = machine['sequence']
                    final_machine_statuses[machine_id - 1]['row_number'] = machine['row_number']

                    if start_time_obj:
                        final_machine_statuses[machine_id - 1]['time_start'] = start_time_obj.strftime('%d/%m %H:%M')
                        final_machine_statuses[machine_id - 1]['time_start_iso'] = start_time_obj.isoformat()
        
        # Query for running assembly lines
        query_running_assembly = """
            SELECT 
                model, assy_line, sequence, status, start_time
            FROM
                production.assembly
            WHERE
                status = 'Start'
        """
        cursor2.execute(query_running_assembly)  # แก้ไขจาก query_running_machines
        running_assy_line = cursor2.fetchall()
        
        if running_assy_line:
            for assy in running_assy_line:
                assy_id = assy['assy_line']
                start_time_obj = assy['start_time']
                
                if 1 <= assy_id <= total_assy_lines:
                    final_assy_statuses[assy_id - 1]['status'] = 'Running'
                    final_assy_statuses[assy_id - 1]['model'] = assy['model']
                    final_assy_statuses[assy_id - 1]['sequence'] = assy['sequence']
                    
                    if start_time_obj:
                        final_assy_statuses[assy_id - 1]['time_start'] = start_time_obj.strftime('%d/%m %H:%M')
                        final_assy_statuses[assy_id - 1]['time_start_iso'] = start_time_obj.isoformat()
    
    except Exception as e:
        print(f"Database Error: {e}")
        # Set error status
        for i in range(total_machines):
            final_machine_statuses[i]['status'] = 'Unknown'
        for i in range(total_assy_lines):
            final_assy_statuses[i]['status'] = 'Unknown'

    finally:
        if 'conn2' in locals() and conn2.is_connected():
            cursor2.close()
            conn2.close()
    
    return render_template(
        'dashboard/dashboard.html',
        machines=final_machine_statuses,
        assembly_lines=final_assy_statuses
    )