from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from db import db_connection, pd_connection
from utils import check_session
from collections import defaultdict

assy_bp = Blueprint('assy', __name__, template_folder='templates/assy')

@assy_bp.route('/assyhome', methods=['GET','POST'])
def assyhome():
    if not check_session(['AD','PD']):
        return redirect(url_for('home'))
    
    return render_template('assy/assyhome.html')
    
@assy_bp.route('/assy_start', methods=['GET','POST'])
def assy_start():
    if not check_session(['AD','PD']):
        return redirect(url_for('home'))

    if request.method == 'POST':
        conn = conn2 = None
        cursor = cursor2 = None
        try:
            leader_assy = request.form.get('leader_assy')
            selected_ids = request.form.getlist('selected_ids')
            man_prices   = request.form.getlist('man_price')

            if not selected_ids:
                flash("กรุณาเลือกรายการอย่างน้อย 1 รายการ", "warning")
                return redirect(url_for('assy.assy_start'))

            selected_ids = [int(x) for x in selected_ids if str(x).strip() != ""]

            if len(man_prices) != len(selected_ids):
                flash("จำนวนค่าแรง (man_price) ไม่ตรงกับจำนวนรายการที่เลือก", "danger")
                return redirect(url_for('assy.assy_start'))

            conn  = db_connection()
            cursor = conn.cursor(dictionary=True)
            conn2 = pd_connection()
            cursor2 = conn2.cursor(dictionary=True)

            query_check = """
                SELECT 
                    sequence
                FROM 
                    production.assembly
                WHERE 
                    status = 'Assembling'
                    AND assy_line = %s
                LIMIT 1
            """
            cursor2.execute(query_check, (leader_assy,))
            assy_check = cursor2.fetchall()
            if assy_check:
                flash("มีการประกอบกำลังทำงานอยู่ ไม่สามารถเพิ่มงานใหม่ได้ในขณะนี้", "danger")
                return redirect(url_for('assy.assy_start'))

            placeholders = ",".join(["%s"] * len(selected_ids))
            query_order = f"""
                SELECT 
                    id,
                    model,
                    quantity
                FROM masterpallet.orders
                WHERE id IN ({placeholders})
            """
            cursor.execute(query_order, tuple(selected_ids))
            assy_order = cursor.fetchall()
            order_lookup = { str(row['id']): row for row in assy_order }

            insert_query = """
                INSERT INTO 
                    production.assembly (sequence, assy_line, man_price, model, quantity, status)
                VALUES 
                    (%s, %s, %s, %s, %s, 'Assembling')
            """

            for seq, mp in zip(selected_ids, man_prices):
                data = order_lookup[str(seq)]
                mp_val = float(mp) if mp.strip() else 0.0
                cursor2.execute(insert_query, (seq, leader_assy, mp_val, data['model'], data['quantity']))
            conn2.commit()

            placeholders = ",".join(["%s"] * len(selected_ids))

            update_daily = f"""
                UPDATE masterpallet.daily_assy_detail
                SET status = 'Assembling'
                WHERE sequence IN ({placeholders})
            """
            cursor.execute(update_daily, tuple(selected_ids))

            update_orders = f"""
                UPDATE masterpallet.orders
                SET status = 'Assembling'
                WHERE id IN ({placeholders})
            """
            cursor.execute(update_orders, tuple(selected_ids))

            conn.commit()

            flash(f"เพิ่มงาน {len(selected_ids)} รายการแล้ว (สถานะ Assembling)", "success")
            return redirect(url_for('assy.assyhome'))

        except Exception as e:
            if conn2 and conn2.is_connected():
                try:
                    conn2.rollback()
                except:
                    pass
            print(f"Error in assy_start POST: {e}")
            flash("เกิดข้อผิดพลาดระหว่างบันทึกข้อมูล", "danger")
            return redirect(url_for('assy.assy_start'))

        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
            if cursor2:
                cursor2.close()
            if conn2 and conn2.is_connected():
                conn2.close()

    # --------- GET ---------
    else:
        try:
            conn = db_connection()
            cursor = conn.cursor(dictionary=True)
            query = """
                SELECT 
                    sequence,
                    model_type,
                    customer,
                    model,
                    qty,
                    man_price,
                    status,
                    qty_done
                FROM 
                    masterpallet.daily_assy_detail
                WHERE 
                    status NOT IN ('Assembled','Cancel')
            """
            cursor.execute(query)
            assy_data = cursor.fetchall()

            assy_leader = ['PANTIMA','SI THU','DOR LONE','WAI LIN TUN','TIN KO WIN','THED KO KO']

        except Exception as e:
            print(f"Database Error: {e}")
            assy_data = []
            assy_leader = []

        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

        return render_template('assy/assystart.html', assy_data=assy_data, assy_leader=assy_leader)

@assy_bp.route('/assy_end', methods=['GET','POST'])
def assy_end():
    if not check_session(['AD','PD']):
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'No JSON data received'}), 400
                      
            conn  = db_connection()
            cursor = conn.cursor(dictionary=True)
            conn2 = pd_connection()
            cursor2 = conn2.cursor(dictionary=True)

            for task in data['tasks']:
                task_id = task['id']
                seq = task['sequence']
                qty = task['completed_qty']

                if task_id is None or seq is None or qty is None:
                    raise ValueError(f"Missing fields in task: {task}")

                try:
                    qty = int(qty)
                except ValueError:
                    raise ValueError(f"Invalid qty for task {task_id}: {qty}")

                query = """
                    SELECT 
                        sequence,
                        qty - qty_done as unfinish
                    FROM 
                        masterpallet.daily_assy_detail
                    WHERE 
                        status NOT IN ('Assembled','Cancel')
                            AND
                        sequence = %s
                """
                cursor.execute(query, (seq,))
                assy_data = cursor.fetchone()

                if not assy_data:
                    raise LookupError(f"No daily_assy_detail row found for sequence {seq}")

                query_assy = """
                    UPDATE 
                        production.assembly
                    SET
                        quantity_done = %s,
                        status = %s,
                        end_time = CURRENT_TIME(),
                        work_time = TIMEDIFF(CURRENT_TIMESTAMP(), start_time)
                    WHERE 
                        idassembly = %s
                """
                cursor2.execute(query_assy, (qty, 'Assembled', task_id))
                conn2.commit()

                if qty >= assy_data['unfinish']:
                    query_assy_detail = """
                        UPDATE masterpallet.daily_assy_detail
                        SET qty_done = qty_done + %s,
                            status = %s
                        WHERE sequence = %s
                    """
                    new_status_detail = 'Assembled'
                    update_order_flag = True
                else:
                    query_assy_detail = """
                        UPDATE masterpallet.daily_assy_detail
                        SET qty_done = qty_done + %s,
                            status = %s
                        WHERE sequence = %s
                    """
                    new_status_detail = 'Incomplete'
                    update_order_flag = False

                cursor.execute(query_assy_detail, (qty, new_status_detail, seq, ))
                conn.commit()

                if update_order_flag:
                    query_order = """
                        UPDATE 
                            masterpallet.orders
                        SET
                            status = %s
                        WHERE
                            id = %s
                    """
                    cursor.execute(query_order, ('Assembled', seq,))
                    conn.commit()
                    
            conn2.commit()
            conn.commit()

            return jsonify({'status': 'success'}), 200

        except Exception as e:
            try:
                conn2.rollback()
            except:
                pass
            try:
                conn.rollback()
            except:
                pass

            print("❌ Error in /assy_end:", e)
            return jsonify({'error': str(e)}), 500

        finally:
            try:
                cursor2.close()
                conn2.close()
            except:
                pass
            try:
                cursor.close()
                conn.close()
            except:
                pass
    else:
        return render_template('assy/assyend.html')
@assy_bp.route('/get_assy', methods=['GET'])
def get_assy():
    try:
        line_id = request.args.get('line')
        if not line_id:
            return jsonify({'error': 'Missing line parameter'}), 400

        conn = db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                idassembly,
                sequence,
                model,
                quantity AS qty_planned
            FROM
                production.assembly
            WHERE
                assy_line = %s
                AND status = 'Assembling'
            ORDER BY
                idassembly ASC
        """
        cursor.execute(query, (line_id,))
        rows = cursor.fetchall()

        # ✅ ถ้าไม่มีข้อมูล
        if not rows:
            return jsonify([])

        # ✅ จัดรูปแบบข้อมูลส่งกลับ (optionally ปรับฟิลด์เพิ่มเติมได้)
        tasks = []
        for r in rows:
            tasks.append({
                'id': r['idassembly'],
                'sequence': r['sequence'],
                'model': r['model'],
                'qty_planned': r['qty_planned']
            })

        return jsonify(tasks), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({'error': str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass