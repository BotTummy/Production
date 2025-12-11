from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from db import db_connection, pd_connection
from utils import check_session
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import mysql.connector

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
            'row_number':'-',
            'time_start': None,
            'time_start_iso': None
        })

    try:
        conn2 = pd_connection()
        cursor2 = conn2.cursor(dictionary=True)

        query_running_machines = """
            SELECT 
                matchine, `row_number`, sequence, status , start_time
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
                    final_machine_statuses[machine_id - 1]['status'] = machine['status']
                    final_machine_statuses[machine_id - 1]['sequence'] = machine['sequence']
                    final_machine_statuses[machine_id - 1]['row_number'] = machine['row_number']

                if start_time_obj:
                        final_machine_statuses[machine_id - 1]['start_time'] = start_time_obj.strftime('%d/%m %H:%M')

                        final_machine_statuses[machine_id - 1]['time_start_iso'] = start_time_obj.isoformat()

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

        # cursor.execute("SET time_zone = '+07:00'")
        thailand_tz = timezone(timedelta(hours=7))
        current_datetime = datetime.now(thailand_tz).replace(tzinfo=None)

        check_query = '''SELECT COUNT(*) as count 
                    FROM `production`.`start_split` 
                    WHERE status = 'Start' AND matchine = %s '''
        cursor.execute(check_query, (matchine,))
        result = cursor.fetchone()

        if result['count'] > 0:
            cursor.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Matchine is not end work' }), 400

        # แก้ไขเวลา
        query = '''INSERT INTO `production`.`start_split` 
                    (`sequence`, `row_number`, `material_type`, `size`, `matchine`, `start_time`) 
                    VALUES (%s, %s, %s, %s, %s, %s)'''

        cursor.execute(query, (sequence, row_number, material_type, size, matchine, current_datetime))

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
                plan_details.work_length,
                plan_details.qty_per_piecs,
                plan_details.quantity
            FROM
                masterpallet.plan_details
                    JOIN
                masterpallet.orders ON orders.id = plan_details.order_id
            WHERE
                plan_status != 'Cancel' AND 
                order_id = %s AND
                orders.status IN ("PlanC","PlanA","Cuted","Splited")
            LIMIT 1 OFFSET %s;
        '''

        cursor.execute(query, (sequence, row_number - 1))
        plan_details = cursor.fetchone()

        cursor.close()
        conn.close()

        if not plan_details:
            return "No plan details found", 404

        return render_template('split/start_split.html', plan_details = plan_details, sequence = sequence, row_number = row_number , matchine = matchine)

@split_bp.route('/end_split', methods=['GET', 'POST'])
def end_split():

    conn2 = pd_connection()
    cursor2 = conn2.cursor(dictionary=True)

    if request.method == 'POST':

        conn = db_connection()
        cursor = conn.cursor(dictionary=True)
        
        matchine = int(request.form.get('matchine'))
        sequence = request.form.get('sequence')
        row_number = int(request.form.get('row_number') or 0)

        work_time_str = '00:00:00' 

        try:
            query_get_start_time = '''SELECT start_time FROM `production`.`start_split`
                                      WHERE `sequence` = %s AND `row_number` = %s AND `status` = 'Start' AND `matchine` = %s'''
            cursor2.execute(query_get_start_time, (sequence, row_number, matchine,))
            start_time_result = cursor2.fetchone()

            if start_time_result and start_time_result['start_time']:
                start_time = start_time_result['start_time']
                end_time = datetime.now()
                
                duration = end_time - start_time
                
                total_seconds = int(duration.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60

                work_time_str = f"{hours}:{minutes:02}:{seconds:02}"

        except Exception as e:
            print(f"Error getting start time: {e}")
            work_time_str = '00:00:00'

        query_update_start = '''UPDATE `production`.`start_split` 
                SET 
                    `status` = 'END'
                WHERE
                    (`sequence` = %s AND `row_number` = %s AND `status` = 'Start' AND `matchine` = %s)'''

        cursor2.execute(query_update_start, (sequence, row_number, matchine,))
        try:
            conn2.commit()
        except Exception as e:
            conn2.rollback()
            print("Error:", e)

        work_qty = int(request.form.get('work_qty') or 0)
        wip_thick = int(request.form.get('wip_thick') or 0)
        wip_width = int(request.form.get('wip_width') or 0)
        wip_qty = int(request.form.get('wip_qty') or 0)

        query_insert_end = '''INSERT INTO `production`.`end_split` 
                      (`sequence`, `row_number`, `matchine`, `work_qty`, `wip_thick`, `wip_width`, `wip_qty`, `work_time`) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'''

        cursor2.execute(query_insert_end, (sequence, row_number, matchine, work_qty, wip_thick, wip_width, wip_qty, work_time_str, ))
        
        try:
            conn2.commit()
        except Exception as e:
            conn2.rollback()
            print("Error:", e)

        if sequence == "WIP":
            return splithome()

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
        
        summary_by_row = defaultdict(int)
        for item in end_details:
            summary_by_row[item['row_number']] += item['work_qty']

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

        return splithome()
        
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

@split_bp.route('/wip_split', methods=['GET', 'POST'])
def wip_split():
    vals = request.values
    try:
        thick = vals.get('thick', None)
        width = vals.get('width', None)
        length = vals.get('length', None)
        matchine = vals.get('matchine', "0")
        
        if thick is None or width is None or length is None:
            return jsonify({'status': 'error', 'message': 'Missing size parameters (thick/width/length)'}), 400
        
        try:
            thick_i = int(thick)
            width_i = int(width)
            length_i = int(length)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Size values must be integers'}), 400

        size = f"{thick_i}x{width_i}x{length_i}"
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

    conn = pd_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SET time_zone = '+07:00'")
        thailand_tz = timezone(timedelta(hours=7))
        current_datetime = datetime.now(thailand_tz).replace(tzinfo=None)

        check_query = '''SELECT COUNT(*) as count 
                         FROM `production`.`start_split` 
                         WHERE status = 'Start' AND matchine = %s'''
        cursor.execute(check_query, (matchine,))
        result = cursor.fetchone()

        if result and result.get('count', 0) > 0:
            return jsonify({'status': 'error', 'message': 'Matchine is not end work'}), 400

        insert_query = '''INSERT INTO `production`.`start_split` 
                          (`sequence`, `row_number`, `material_type`, `size`, `matchine`, `start_time`) 
                          VALUES (%s, %s, %s, %s, %s, %s)'''
        cursor.execute(insert_query, ("WIP", 1, "WIP", size, matchine, current_datetime))

        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

    return splithome()

@split_bp.route('/split_log', methods=['GET', 'POST'])
def split_log():

    final_results = []

    try:
        conn_p = pd_connection()
        cursor_p = conn_p.cursor(dictionary=True)
        
        query_end_split = '''
                        SELECT 
                            idend_split,
                            matchine,
                            work_qty,
                            work_time,
                            sequence,
                            `row_number`
                        FROM
                            end_split
                        ORDER BY end_time DESC
                        LIMIT 10'''
        cursor_p.execute(query_end_split)
        end_split_data = cursor_p.fetchall()
        
        if not end_split_data:
            return []

        search_conditions = []
        for row in end_split_data:
            search_conditions.append(f"({int(row['sequence'])}, {row['row_number']})")
        
        conditions_str = ", ".join(search_conditions)
        # print(conditions_str)

        conn_master = db_connection()
        cursor_master = conn_master.cursor(dictionary=True)

        query_plan_details = f"""
            WITH plan_with_rownum AS (
              SELECT
                order_id,
                material_type,
                CONCAT(work_thickness - work_tolerance_thickness) AS thick,
				CONCAT(work_width - work_tolerance_width) AS width,
                ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY idplan_details ASC) AS rn
              FROM
                plan_details
            )
            SELECT * FROM plan_with_rownum
            WHERE (order_id, rn) IN ({conditions_str});
        """
        
        cursor_master.execute(query_plan_details)
        plan_details_data = cursor_master.fetchall()

        plan_details_map = {
            (str(row['order_id']), row['rn']): row for row in plan_details_data
        }

        for end_row in end_split_data:
            key = (end_row['sequence'], end_row['row_number'])
            plan_row = plan_details_map.get(key)
            
            if plan_row:
                combined_row = {**end_row, **plan_row}
                final_results.append(combined_row)
            else:
                final_results.append({**end_row, 'plan_details': None})
        
    except mysql.connector.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn_p and conn_p.is_connected():
            cursor_p.close()
            conn_p.close()

        if conn_master and conn_master.is_connected():
            cursor_master.close()
            conn_master.close()
    
    # print(final_results)
    return render_template('split/split_log.html' , latest_combined_data = final_results)
    
@split_bp.route('/edit_split/<int:record_id>', methods=['GET', 'POST'])
def edit_split(record_id):
    
    if request.method == 'POST':
        work_qty = request.form.get('work_qty')

        conn = pd_connection()
        cursor = conn.cursor(dictionary=True)

        query = '''UPDATE 
                    `production`.`end_split`
                SET 
                    `work_qty` = %s
                WHERE
                    (`idend_split` = %s )
                '''

        cursor.execute(query, (work_qty, record_id,))
        try:
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("Error:", e)
        
        cursor.close()
        conn.close()

        return split_log()
    else:
        try:
            conn = pd_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = "SELECT * FROM end_split WHERE idend_split = %s"
            
            cursor.execute(query, (record_id,))
            
            split_data = cursor.fetchone()
            
            if split_data is None:
                return "No record_id found", 404
            
            return render_template('edit_split.html', split_data=split_data)

        except mysql.connector.Error as e:
            print(f"Database error: {e}")
            return "Error connecting to database", 500
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()