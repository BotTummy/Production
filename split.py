from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from db import db_connection, pd_connection
from utils import check_session
from collections import defaultdict

split_bp = Blueprint('split', __name__, template_folder='templates/split')

@split_bp.route('/splithome', methods=['GET'])
def splithome():
    if not check_session(['AD','PD']):
        return redirect(url_for('home'))

    total_machines = 8
    final_machine_statuses = []
    for i in range(1, total_machines + 1):
        final_machine_statuses.append({
            'id': i,
            'status': 'Idle',
            'sequence': '-',
            'row_number':'-'
        })

    try:
        conn2 = pd_connection()
        cursor2 = conn2.cursor(dictionary=True)

        query_running_machines = """
            SELECT 
                matchine, `row_number`, sequence, status 
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
                if 1 <= machine_id <= total_machines:
                    final_machine_statuses[machine_id - 1]['status'] = machine['status']
                    final_machine_statuses[machine_id - 1]['sequence'] = machine['sequence']
                    final_machine_statuses[machine_id - 1]['row_number'] = machine['row_number']

    except Exception as e:
        print(f"Database Error: {e}")

        for i in range(total_machines):
            final_machine_statuses[i]['status'] = 'Unknown'

    finally:
        if 'conn2' in locals() and conn2.is_connected():
            cursor2.close()
            conn2.close()
            
    return render_template('split/splithome.html', machine_statuses = final_machine_statuses)

@split_bp.route('/start_split', methods=['GET', 'POST'])
def start_split():
    if request.method == 'POST':
        sequence = request.form.get('sequence')
        row_number = request.form.get('row_number')
        matchine = request.form.get('matchine') or "0"
        material_type = request.form.get('material_type')
        size = request.form.get('size')

        conn = pd_connection()
        cursor = conn.cursor(dictionary=True)

        check_query = '''SELECT COUNT(*) as count 
                    FROM `production`.`start_split` 
                    WHERE status = 'Start' AND matchine = %s '''
        cursor.execute(check_query, (matchine,))
        result = cursor.fetchone()

        if result['count'] > 0:
            cursor.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Matchine is not end work' }), 400

        query = '''INSERT INTO `production`.`start_split` 
                    (`sequence`, `row_number`, `material_type`, `size`, `matchine`) 
                    VALUES (%s, %s, %s, %s, %s)'''

        cursor.execute(query, (sequence, row_number, material_type, size, matchine))

        try:
            conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500
        finally:
            cursor.close()
            conn.close()

        return splithome()
    else:
        sequence = request.args.get('sequence')
        row_number_raw = request.args.get('row_number')
        matchine = request.args.get('matchine')

        if not row_number_raw or not row_number_raw.isdigit():
            return "Invalid row number", 400
        row_number = int(row_number_raw)

        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        query = '''
            SELECT 
                plan_details.material_type,
                plan_details.work_thickness,
                plan_details.work_tolerance_thickness,
                plan_details.work_width,
                plan_details.work_tolerance_width,
                plan_details.qty_per_piecs,
                plan_details.quantity
            FROM
                masterpallet.plan_details
            WHERE
                plan_status != 'Cancel' AND order_id = %s 
            LIMIT 1 OFFSET %s;
        '''

        cursor.execute(query, (sequence, row_number - 1))
        plan_details = cursor.fetchone()

        cursor.close()
        conn.close()

        if not plan_details:
            return "No plan details found", 404

        return render_template('split/start_split.html', plan_details = plan_details, sequence = sequence, row_number = row_number , matchine = matchine)

@split_bp.route('/submit_split', methods=['POST'])
def submit_split():
    sequence = request.form.get('sequence')
    row_number = request.form.get('row_number')
    material_type = request.form.get('material_type_change')
    matchine = request.form.get('matchine')

    if not material_type:
        material_type = request.form.get('material_type')
        size = request.form.get('material_size')
        qty = int(request.form.get('material_qty') or 0)

    else:
        thick = request.form.get('thick_change') or "0"
        width = request.form.get('width_change') or "0"
        length = request.form.get('length_change') or "0"
        qty = int(request.form.get('qty_change') or 0)

        size = f"{thick}x{width}x{length}"

    conn = pd_connection()
    cursor = conn.cursor(dictionary=True)

    check_query = '''SELECT COUNT(*) as count 
                 FROM `production`.`start_cut` 
                 WHERE status = 'Start' AND matchine = %s '''
    cursor.execute(check_query, (matchine,))
    result = cursor.fetchone()

    if result['count'] > 0:
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'Matchine is not end work' }), 400

    query = '''INSERT INTO `production`.`start_cut` 
                (`sequence`, `row_number`, `material_type`, `size`, `qty`, `matchine`) 
                VALUES (%s, %s, %s, %s, %s, %s)'''

    cursor.execute(query, (sequence, row_number, material_type, size, qty, matchine))

    try:
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

    return render_template('cut/cuthome.html')

@split_bp.route('/end_split', methods=['GET', 'POST'])
def end_split():

    conn2 = pd_connection()
    cursor2 = conn2.cursor(dictionary=True)

    if request.method == 'POST':

        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
        
        matchine = request.form.get('matchine')
        sequence = request.form.get('sequence')
        row_number = int(request.form.get('row_number') or 0)

        query_update_start = '''UPDATE `production`.`start_split` 
                SET 
                    `status` = 'END'
                WHERE
                    (`sequence` = %s AND `row_number` = %s AND `status` = 'Start' AND `matchine` = %s)'''

        cursor2.execute(query_update_start, (sequence, row_number, matchine,))
        
        work_qty = int(request.form.get('work_qty') or 0)
        wip_thick = int(request.form.get('wip_thick') or 0)
        wip_width = int(request.form.get('wip_width') or 0)
        wip_qty = int(request.form.get('wip_qty') or 0)

        query_insert_end = '''INSERT INTO `production`.`end_split` 
                (`sequence`, `row_number`, `matchine`, `work_qty`, `wip_thick`, `wip_width`, `wip_qty`) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)'''

        cursor2.execute(query_insert_end, (sequence, row_number, matchine, work_qty, wip_thick, wip_width, wip_qty,))
        
        try:
            conn2.commit()
        except Exception as e:
            conn2.rollback()
            print("Error:", e)

        query_plan_details_detail = '''SELECT 
                            *
                        FROM
                            masterpallet.plan_details
                        WHERE
                            order_id = %s AND plan_status != "Cancel"'''
        
        cursor.execute(query_plan_details_detail, (sequence,))
        plan_details = cursor.fetchall()

        if not plan_details:
            return "No plan details found", 400

        query_end_detail = '''SELECT 
                            *
                        FROM
                            production.end_split
                        WHERE
                            sequence = %s'''
        
        cursor2.execute(query_end_detail, (sequence,))
        end_details = cursor2.fetchall()
        
        # # รวม work_qty โดยใช้ row_number เป็น key
        summary_by_row = defaultdict(int)
        for item in end_details:
            summary_by_row[item['row_number']] += item['work_qty']

        # # เปรียบเทียบตามตำแหน่ง index ของ plan_details
        check_ok = True
        for i, plan in enumerate(plan_details):
            plan_qty = int(plan['quantity'])
            done_qty = summary_by_row.get(i + 1, 0)

            if plan_qty > done_qty:
                check_ok = False
                break

        if check_ok:
            query_update_status = '''UPDATE `masterpallet`.`orders` 
                SET 
                    `status` = 'Splited'
                WHERE
                    `id` = %s'''

            cursor.execute(query_update_status, (sequence,))
            try:
                conn.commit()
            except Exception as e:
                conn.rollback()
                print("Error:", e)

        cursor.close()
        conn.close()
        cursor2.close()
        conn2.close()

        return render_template('split/splithome.html')
        
    else:
        matchine = request.args.get('matchine')

        query = '''SELECT 
                        *
                    FROM
                        production.start_split
                    WHERE
                        start_split.status = 'Start' AND start_split.matchine = %s'''

        cursor2.execute(query, (matchine,))
        plan_details = cursor2.fetchone()

        cursor2.close()
        conn2.close()

        return render_template('split/end_split.html' , plan_details = plan_details, matchine = matchine)
