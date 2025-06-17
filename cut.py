from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from db import db_connection, pd_connection
from utils import check_session
from collections import defaultdict

cut_bp = Blueprint('cut', __name__, template_folder='templates/cut')

@cut_bp.route('/cuthome', methods=['GET'])
def cuthome():
    if not check_session(['AD','PD']):
        return redirect(url_for('home'))
    return render_template('cut/cuthome.html')

@cut_bp.route('/start_cut', methods=['GET', 'POST'])
def start_cut():
    if request.method == 'POST':
        sequence = request.form.get('sequence')
        row_number_raw = request.form.get('row_number')

        if not row_number_raw or not row_number_raw.isdigit():
            return "Invalid row number", 400
        row_number = int(row_number_raw)

        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        query = '''
            SELECT 
                plan_details.order_id,
                plan_details.material_type,
                plan_details.material_size,
                plan_details.work_length,
                plan_details.material_qty
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

        return render_template('cut/start_cut.html', plan_details = plan_details, sequence = sequence, row_number = row_number)

    else:
        order_sequence = request.args.get('order_sequence')
        return render_template('cut/selectcut.html', order_sequence = order_sequence)

    
@cut_bp.route('/submit_cut', methods=['POST'])
def submit_cut():
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

@cut_bp.route('/end_cut', methods=['GET', 'POST'])
def end_cut():

    conn2 = pd_connection()
    cursor2 = conn2.cursor(dictionary=True)

    if request.method == 'POST':

        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
        
        matchine = request.form.get('matchine')
        sequence = request.form.get('sequence')
        row_number = int(request.form.get('row_number') or 0)

        query_update_start = '''UPDATE `production`.`start_cut` 
                SET 
                    `status` = 'END'
                WHERE
                    (`sequence` = %s AND `row_number` = %s AND `status` = 'Start' AND `matchine` = %s)'''

        cursor2.execute(query_update_start, (sequence, row_number, matchine,))
        
        work_qty = int(request.form.get('work_qty') or 0)
        wip_length = int(request.form.get('wip_length') or 0)
        wip_qty = int(request.form.get('wip_qty') or 0)

        query_insert_end = '''INSERT INTO `production`.`end_cut` 
                (`sequence`, `row_number`, `matchine`, `work_qty`, `wip_length`, `wip_qty`) 
                VALUES (%s, %s, %s, %s, %s, %s)'''

        cursor2.execute(query_insert_end, (sequence, row_number, matchine, work_qty, wip_length, wip_qty,))

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
                            production.end_cut
                        WHERE
                            sequence = %s'''
        
        cursor2.execute(query_end_detail, (sequence,))
        end_details = cursor2.fetchall()
        
        # รวม work_qty โดยใช้ row_number เป็น key
        summary_by_row = defaultdict(int)
        for item in end_details:
            summary_by_row[item['row_number']] += item['work_qty']

        # เปรียบเทียบตามตำแหน่ง index ของ plan_details
        check_ok = True
        for i, plan in enumerate(plan_details):
            plan_qty = int(plan['quantity'] / plan['qty_per_piecs'])
            done_qty = summary_by_row.get(i + 1, 0)

            if plan_qty > done_qty:
                check_ok = False
                break

        if check_ok:
            query_update_status = '''UPDATE `masterpallet`.`orders` 
                SET 
                    `status` = 'Cuted'
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

        return render_template('cut/cuthome.html')
    else:
        matchine = request.args.get('matchine')

        query = '''SELECT 
                        *
                    FROM
                        production.start_cut
                    WHERE
                        start_cut.status = 'Start' AND start_cut.matchine = %s'''

        cursor2.execute(query, (matchine,))
        plan_details = cursor2.fetchone()

        cursor2.close()
        conn2.close()

        return render_template('cut/end_cut.html' , plan_details = plan_details, matchine = matchine)
