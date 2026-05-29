from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from db import db_connection, pd_connection
from utils import check_session
from collections import defaultdict
import base64
from escpos.printer import Dummy

cut_bp = Blueprint('cut', __name__, template_folder='templates/cut')

def parse_dimensions(size):
    thickness, width, length = map(int, size.split('x'))
    return thickness, width, length

@cut_bp.route('/cuthome', methods=['GET'])
def cuthome():
    if not check_session(['AD','PD']):
        return redirect(url_for('home'))
    return render_template('cut/cuthome.html')

@cut_bp.route('/select_cut', methods=['GET', 'POST'])
def select_cut():
    if request.method == 'POST':
        selected_ids = request.form.getlist('selected_cuts')
        print(f"ID ที่ถูกเลือกคือ: {selected_ids}")

        if selected_ids:
            conn = db_connection()
            cursor = conn.cursor(dictionary=True)
            conn2 = pd_connection()
            cursor2 = conn2.cursor(dictionary=True)

            try:
                query = '''INSERT INTO `production`.`cut` (`plan_id`) VALUES (%s)'''
                query2 = '''UPDATE `masterpallet`.`plan_details` 
                            SET `process_cut` = 'Cuted' 
                            WHERE (`idplan_details` = %s)
                            '''
                for an_id in selected_ids:

                    cursor2.execute(query, (an_id,))
                    cursor.execute(query2, (an_id,))

                conn.commit()
                conn2.commit()
                # print(f"เพิ่มข้อมูล {len(selected_ids)} รายการสำเร็จ")

                check_query = '''
                SELECT
                    COUNT(*) AS total_items_in_order,
                    SUM(CASE WHEN process_cut = 'Cuted' THEN 1 ELSE 0 END) AS cut_items_in_order
                FROM
                    `masterpallet`.`plan_details`
                WHERE
                    plan_status != 'Cancel' AND 
                    order_id = (SELECT order_id FROM `masterpallet`.`plan_details` WHERE idplan_details = %s);'''
                
                cursor.execute(check_query, (selected_ids[0],))
                check_item = cursor.fetchone()

                if check_item:
                    total_items = check_item['total_items_in_order']
                    cut_items = int(check_item['cut_items_in_order'])

                    if total_items == cut_items:
                        update_order_status = '''UPDATE `masterpallet`.`orders` 
                                   SET `status` = 'Cuted' 
                                   WHERE `id` = (SELECT order_id FROM `masterpallet`.`plan_details` WHERE idplan_details = %s) '''

                        cursor.execute(update_order_status, (int(selected_ids[0]),))
                        conn.commit()

            except Exception as e:
                conn.rollback()
                conn2.rollback()
                print(f"เกิดข้อผิดพลาด: {e}")
            finally:
                cursor.close()
                conn.close()
                cursor2.close()
                conn2.close()
        else:
            pass

        return render_template('cut/cuthome.html')
    
    else:
        order_sequence = request.args.get('order_sequence')
        if order_sequence:
            pass
        
        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT id,
                   customer,
                   model,
                   quantity
            FROM masterpallet.orders
            WHERE id = %s;
        """, (order_sequence,))
        order = cursor.fetchone()

        if not order:
            cursor.close()
            conn.close()
            flash(f'Sequence No. "{order_sequence}" not found. Please try again.', 'error')
            return redirect(url_for('cut.cuthome'))

        query_plan_details_detail = '''
            SELECT
                p.idplan_details,
                p.material_type,
                p.material_size,
                p.material_qty,
                CONCAT(p.work_thickness - p.work_tolerance_thickness,
                        'x',
                        p.work_width - p.work_tolerance_width,
                        'x',
                        p.work_length) AS size,
                p.quantity,
                p.qty_per_piecs,
                p.process_cut
            FROM
                masterpallet.plan_details AS p
            JOIN
                masterpallet.orders AS o ON o.id = p.order_id
            WHERE
                p.order_id = %s
                AND p.plan_status != "Cancel"
                AND o.status IN ("PlanC" , "PlanA", "Cuted", "Split");'''
        
        cursor.execute(query_plan_details_detail, (order_sequence,))
        cut_plan_items  = cursor.fetchall()
        # print(plan_details)
        plan_details = []

        for item in cut_plan_items:
            material_type = item['material_type']
            material_size = item['material_size']
            material_qty = item['material_qty']
            size = item['size']
            quantity = item['quantity']
            qty_per_piecs = item['qty_per_piecs']

            try:
                mat_thick, mat_width, mat_length = parse_dimensions(material_size)
                work_thick, work_width, work_length = parse_dimensions(size)
                cut_qty = (mat_length // work_length * material_qty) if work_length > 0 else 0
            except (ValueError, AttributeError, TypeError):
                cut_qty = 0

            plan_details.append({
                'idplan_details': item['idplan_details'],
                'material_type' : material_type,
                'material_size' : material_size,
                'material_qty' : material_qty,
                'size' : size,
                'quantity' : quantity,
                'qty_per_piecs' : qty_per_piecs,
                'cut_qty' : cut_qty,
                'process_cut' : item['process_cut'],
            })

        cursor.close()
        conn.close()

        return render_template('cut/selectcut.html', order = order, plan_details = plan_details)
   
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

PRINT_AGENT_KEY = "a3f8c2e1b7d94f6e0a2c5b8d3e7f1a4c9b6e2d5f8a1c4e7b0d3f6a9c2e5b8d1"

NORMAL   = b'\x1d\x21\x00'  # 1x1 normal
DOUBLE   = b'\x1d\x21\x11'  # 2x2
TRIPLE   = b'\x1d\x21\x22'  # 3x3
BOLD_ON  = b'\x1b\x45\x01'
BOLD_OFF = b'\x1b\x45\x00'
ALIGN_L  = b'\x1b\x61\x00'
ALIGN_C  = b'\x1b\x61\x01'

def build_wip_bytes():
    p = Dummy()
    p._raw(ALIGN_L + BOLD_OFF + DOUBLE)
    p._raw(f"Seq: {'WIP':<8} Qty: \n".encode('utf-8'))
    p._raw(ALIGN_L + BOLD_OFF + DOUBLE)
    p._raw(("- " * 12 + "\n").encode('utf-8'))
    p._raw(ALIGN_C + BOLD_OFF + DOUBLE)
    p._raw(f"WIP : 1 =  \n".encode('utf-8'))
    p._raw(DOUBLE)
    p._raw(f"\n{'x':^13} {'x':<9}\n".encode('utf-8'))
    p._raw(BOLD_OFF + DOUBLE)
    p._raw(f"\nTotal need :     \n".encode('utf-8'))
    p.cut()
    return bytes(p.output)


def build_slip_bytes(seq, no, model, qty, type, split, size, total, req):
    p = Dummy()
    p._raw(ALIGN_L + BOLD_OFF + DOUBLE)
    p._raw(f"Seq: {str(seq).zfill(5)}-{str(no).zfill(2):<2}  Qty: {qty}\n".encode('utf-8'))
    p._raw(ALIGN_C + BOLD_OFF + NORMAL)
    p._raw(f"\n{model}\n".encode('utf-8'))
    p._raw(ALIGN_L + BOLD_OFF + DOUBLE)
    p._raw(("- " * 12 + "\n").encode('utf-8'))
    p._raw(ALIGN_C + BOLD_OFF + DOUBLE)
    p._raw(f"{type} : 1 = {split}\n".encode('utf-8'))
    p._raw(DOUBLE)
    p._raw(f"\n{size} = {total}\n".encode('utf-8'))
    p._raw(BOLD_OFF + DOUBLE)
    p._raw(f"\nTotal need : {req}\n".encode('utf-8'))
    p.cut()
    return bytes(p.output)


def enqueue_print_job(job_type, payload_bytes):
    conn = None
    cursor = None
    try:
        conn = pd_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO print_queue (job_type, payload, status)
            VALUES (%s, %s, 'pending')
        """, (job_type, payload_bytes))
        conn.commit()
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

@cut_bp.route('/print-wip', methods=['POST'])
def print_wip():
    try:
        payload = build_wip_bytes()
        enqueue_print_job('wip', payload)
        return jsonify({"status": "success", "message": "ส่งคำสั่งปริ้นแล้ว กรุณารอสักครู่..."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@cut_bp.route('/print-slip', methods=['POST'])
def print_slip():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400
    try:
        payload = build_slip_bytes(
            seq   = data.get('seq', ''),
            no    = data.get('no', ''),
            model = data.get('model', ''),
            qty   = data.get('qty', ''),
            type  = data.get('type', ''),
            split = data.get('split', ''),
            size  = data.get('size', ''),
            total = data.get('total', ''),
            req   = data.get('req', ''),
        )
        enqueue_print_job('slip', payload)
        return jsonify({"status": "success", "message": "ส่งคำสั่งปริ้นแล้ว กรุณารอสักครู่..."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Print Agent API ───────────────────────────────────────────────────────────

def _agent_auth():
    if not PRINT_AGENT_KEY or request.headers.get('X-Agent-Key') != PRINT_AGENT_KEY:
        return jsonify({'error': 'Unauthorized'}), 401
    return None


@cut_bp.route('/api/print-jobs', methods=['GET'])
def api_get_print_jobs():
    blocked = _agent_auth()
    if blocked:
        return blocked

    conn = None
    cursor = None
    try:
        conn = pd_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, job_type, payload
            FROM print_queue
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        if rows:
            ids = [r['id'] for r in rows]
            ph = ','.join(['%s'] * len(ids))
            cursor.execute(f"UPDATE print_queue SET status = 'printing' WHERE id IN ({ph})", tuple(ids))
            conn.commit()
        jobs = [
            {
                'id': r['id'],
                'job_type': r['job_type'],
                'payload': base64.b64encode(r['payload']).decode('utf-8'),
            }
            for r in rows
        ]
        return jsonify(jobs), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


@cut_bp.route('/api/print-jobs/<int:job_id>/ack', methods=['POST'])
def api_ack_print_job(job_id):
    blocked = _agent_auth()
    if blocked:
        return blocked

    data = request.get_json() or {}
    success = data.get('success', True)
    error_msg = data.get('error', None)

    conn = None
    cursor = None
    try:
        conn = pd_connection()
        cursor = conn.cursor()
        if success:
            cursor.execute("UPDATE print_queue SET status = 'done' WHERE id = %s", (job_id,))
        else:
            cursor.execute(
                "UPDATE print_queue SET status = 'error', error_message = %s WHERE id = %s",
                (error_msg, job_id)
            )
        conn.commit()
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()