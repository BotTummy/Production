from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from db import db_connection, pd_connection
from utils import check_session

qualitycontrol_bp = Blueprint('qualitycontrol', __name__, template_folder='templates/qc')

@qualitycontrol_bp.route('/qc', methods=['GET'])
def qchome():
    if not check_session(['AD','QC']):
        return redirect(url_for('home'))
    return render_template('qc/qchome.html')

@qualitycontrol_bp.route('/confirm_check', methods=['GET','POST'])
def confirm_check():
    if not check_session(['AD','QC']):
        return redirect(url_for('home'))
    
    conn = db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        conn2 = pd_connection()
        cursor2 = conn2.cursor(dictionary=True)

        query = '''SELECT id, quantity FROM masterpallet.orders WHERE status NOT IN ("Cancle", "END", "Checked")'''
        cursor.execute(query)
        orders = {str(order['id']): order['quantity'] for order in cursor.fetchall()}

        data = request.get_json(silent=True)
        if not data or 'orders' not in data:
            return jsonify({'status': 'error', 'message': 'Invalid or missing data'}), 400
        checks = data.get('orders', [])
        
        for check in checks:
            order_id = str(check['order_id'])
            qty = int(check['quantity'])

            if order_id in orders:
                # แทรกรายการใหม่ลง quality_check
                sql_item = '''INSERT INTO production.quality_check (sequence, quantity) VALUES (%s, %s)'''
                cursor2.execute(sql_item, (order_id, qty))

                # ดึงจำนวนที่เคยเช็คจาก quality_check
                sql_sum = '''SELECT COALESCE(SUM(quantity), 0) AS total_checked 
                            FROM production.quality_check 
                            WHERE sequence = %s'''
                cursor2.execute(sql_sum, (order_id,))
                total_checked = cursor2.fetchone()['total_checked']

                total_quantity = orders[order_id]
                new_total = total_checked

                # อัปเดตสถานะ
                if new_total >= total_quantity:
                    sql_update = '''UPDATE masterpallet.orders SET status = "Checked" WHERE id = %s'''
                else:
                    sql_update = '''UPDATE masterpallet.orders SET status = "Checking" WHERE id = %s'''

                cursor.execute(sql_update, (order_id,))

        try:
            conn.commit()
            conn2.commit()
        except Exception as e:
            conn.rollback()
            conn2.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500
        finally:
            cursor.close()
            conn.close()
            cursor2.close()
            conn2.close()
        return jsonify({'status': 'success', 'message': 'Orders received'})
    
    else :
        query = '''SELECT 
                    orders.id,
                    orders.customer,
                    orders.model,
                    orders.quantity,
                    orders.delivery_date,
                    models.remark,
                    CONCAT(models.thickness,
                            ' x ',
                            models.width,
                            ' x ',
                            models.length) AS size
                FROM
                    masterpallet.orders
                        JOIN
                    masterpallet.models ON models.model = orders.model
                WHERE
                    status NOT IN ("Cancle", "END", "Checked")
                ORDER BY orders.delivery_date ASC'''
        
        cursor.execute(query)
        orders = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('qc/confirm_check.html', orders = orders )

@qualitycontrol_bp.route('/logcheck', methods=['GET'])
def logcheck():
    # return render_template('qc/logcheck.html')
    pass