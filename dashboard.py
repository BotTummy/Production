from flask import Blueprint, render_template, request, session
from db import db_connection, pd_connection

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates/dashboard')

@dashboard_bp.route('/dashboard', methods=['GET'])
def dashboard():
    if 'loggedin' in session and session['loggedin'] == False:
        return render_template('index.html', username=session['username'])

    total_machines = 8
    total_assy_lines = 6
    
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
    
    # Define assembly line names mapping
    assy_id_to_name = {
        1: 'PANTIMA',
        2: 'SI THU',
        3: 'DOR LONE',
        4: 'WAI LIN TUN',
        5: 'TIN KO WIN',
        6: 'THED KO KO'
    }
    
    final_assy_statuses = []
    for i in range(1, total_assy_lines + 1):
        final_assy_statuses.append({
            'id': i,
            'name': assy_id_to_name.get(i, f'Assembly Line {i}'),
            'status': 'Idle',
            'model': '-',
            'sequence': '-',
            'time_start': None,
            'time_limit': None,
            'time_start_iso': None,
            'assy_line_id': None  # Store the actual assy_id (string)
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
                status IN ("PlanC","PlanA","Cuted","Splited","Assembling")
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
                    # final_machine_statuses[machine_id - 1]['work_time'] = 120

                    if start_time_obj:
                        final_machine_statuses[machine_id - 1]['time_start'] = start_time_obj.strftime('%d/%m %H:%M')
                        final_machine_statuses[machine_id - 1]['time_start_iso'] = start_time_obj.isoformat()
        
        # ...................Assembly................................
        query_running_assembly = """
            SELECT 
                model, assy_line, sequence, start_time, man_price
            FROM
                production.assembly
            WHERE
                status = 'Assembling'
        """
        cursor2.execute(query_running_assembly)
        running_assy_line = cursor2.fetchall()

        # Mapping assy_id (string) to array index (1-based)
        assy_mapping = {
            'PANTIMA': 1, 
            'SI THU': 2,
            'DOR LONE': 3,
            'WAI LIN TUN': 4,
            'TIN KO WIN': 5,
            'THED KO KO': 6
        }
        
        # Mapping assy_id to number of workers (manpower)
        manpower_mapping = {
            'PANTIMA': 1,
            'SI THU': 6,
            'DOR LONE': 9,
            'WAI LIN TUN': 5,
            'TIN KO WIN': 5,
            'THED KO KO': 6
        }
        
        if running_assy_line:
            for assy in running_assy_line:
                assy_id = assy['assy_line']  # This is a string like "PANTIMA"
                start_time_obj = assy['start_time']
                
                # Skip if assy_id is not in mapping
                if assy_id not in assy_mapping:
                    continue
                
                # Get the array index from mapping (1-based)
                assy_index = assy_mapping[assy_id]
                
                # Calculate work_time in minutes (rounded to integer)
                work_time = 0
                if assy_id in manpower_mapping:
                    man_day_price = manpower_mapping[assy_id] * 400
                    man_price = assy.get('man_price', 0)
                    if man_day_price > 0:
                        work_time = round(man_price / man_day_price * 8 * 60)  # Round to integer minutes
                
                # Check if work period crosses lunch break (12:00-13:00)
                if start_time_obj and work_time > 0:
                    from datetime import timedelta
                    
                    # Calculate end time (without lunch break adjustment)
                    end_time = start_time_obj + timedelta(minutes=work_time)
                    
                    # Get hours
                    start_hour = start_time_obj.hour
                    end_hour = end_time.hour
                    
                    # Check if work crosses lunch time (12:00-13:00)
                    # If start is before 12:00 and end is after 12:00, add 60 minutes
                    if start_hour < 12 and end_hour >= 12:
                        work_time += 60  # Add 1 hour for lunch break
                
                # Update the status using the mapped index
                if 1 <= assy_index <= total_assy_lines:
                    current_status = final_assy_statuses[assy_index - 1]['status']
                    
                    # Check if this assy_id already has data (duplicate)
                    if current_status == 'Running':
                        # Append sequence with "+"
                        current_sequence = final_assy_statuses[assy_index - 1]['sequence']
                        new_sequence = assy['sequence']
                        final_assy_statuses[assy_index - 1]['sequence'] = f"{current_sequence} + {new_sequence}"
                        
                        # Add work_time together
                        current_work_time = final_assy_statuses[assy_index - 1]['work_time']
                        final_assy_statuses[assy_index - 1]['work_time'] = current_work_time + work_time
                    else:
                        # First time setting this assy_id
                        final_assy_statuses[assy_index - 1]['status'] = 'Running'
                        final_assy_statuses[assy_index - 1]['name'] = assy_id  # Use actual assy_id as name
                        final_assy_statuses[assy_index - 1]['model'] = assy['model']
                        final_assy_statuses[assy_index - 1]['sequence'] = assy['sequence']
                        final_assy_statuses[assy_index - 1]['work_time'] = work_time
                        final_assy_statuses[assy_index - 1]['assy_line_id'] = assy_id
                        
                        if start_time_obj:
                            final_assy_statuses[assy_index - 1]['time_start'] = start_time_obj.strftime('%d/%m %H:%M')
                            final_assy_statuses[assy_index - 1]['time_start_iso'] = start_time_obj.isoformat()

        final_assy_statuses = sorted(
            final_assy_statuses,
            key=lambda x: assy_mapping.get(x.get('assy_line_id'), 999)
)
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