from flask import Blueprint, render_template, request, session
from db import db_connection, pd_connection

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates/dashboard')

@dashboard_bp.route('/dashboard', methods=['GET'])
def dashboard():
    if 'loggedin' in session and session['loggedin'] == False:
        return render_template('index.html', username=session['username'])

    total_machines = 8
    total_assy_lines = 5
    
    final_machine_statuses = []
    for i in range(1, total_machines + 1):
        final_machine_statuses.append({
            'id': i,
            'name': f'Split Machine {i}',
            'status': 'Idle',
            'model': '-',
            'sequence': '-',
            'row_number': '-',
            'time_start': None,
            'time_start_iso': None
        })
    
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
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        query_order = """
            SELECT 
                id, customer, model, quantity
            FROM
                masterpallet.orders
            WHERE
                status IN ("PlanC","PlanA","Cuted","Splited")
        """
        cursor.execute(query_order)
        order_detail = cursor.fetchall()

        conn2 = pd_connection()
        cursor2 = conn2.cursor(dictionary=True)

        query_running_machines = """
            SELECT 
                matchine, size, sequence, status, start_time
            FROM
                production.start_split
            WHERE
                status = 'Start'
        """
        cursor2.execute(query_running_machines)
        running_machines = cursor2.fetchall()

        order_map = {str(o['id']): o for o in order_detail}

        for machine in running_machines:
            seq = machine['sequence']
            if seq == "WIP":
                machine.update({
                    'customer': "WIP",
                    'model': "WIP",
                    'quantity': "-"
                })
                continue
            if seq in order_map:
                order = order_map[seq]
                machine.update({
                    'customer': order['customer'],
                    'model': order['model'],
                    'quantity': order['quantity']
                })

        if running_machines:
            for machine in running_machines:
                machine_id = machine['matchine']
                start_time_obj = machine['start_time']
                
                if 1 <= machine_id <= total_machines:
                    final_machine_statuses[machine_id - 1]['status'] = 'Running'
                    final_machine_statuses[machine_id - 1]['sequence'] = machine['sequence']
                    final_machine_statuses[machine_id - 1]['size'] = machine['size']
                    final_machine_statuses[machine_id - 1]['model'] = machine['model']
                    final_machine_statuses[machine_id - 1]['work_time'] = 120

                    if start_time_obj:
                        final_machine_statuses[machine_id - 1]['time_start'] = start_time_obj.strftime('%d/%m %H:%M')
                        final_machine_statuses[machine_id - 1]['time_start_iso'] = start_time_obj.isoformat()
        
        # ...................Assembly................................
        query_running_assembly = """
            SELECT 
                model, assy_line, sequence, status, start_time, man_price
            FROM
                production.assembly
            WHERE
                status = 'Assembling'
        """
        cursor2.execute(query_running_assembly)
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