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
                    status NOT IN ("Cancle", "END", "Checked") AND
                    stock != "Stock"
                ORDER BY orders.delivery_date ASC'''
        
        cursor.execute(query)
        orders = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('qc/confirm_check.html', orders = orders )

@qualitycontrol_bp.route('/check_logs', methods=['GET'])
def check_logs():
    if not check_session(['AD','QC']):
        return redirect(url_for('home'))
    
    conn = db_connection()
    cursor = conn.cursor(dictionary=True)
    
    conn2 = pd_connection()
    cursor2 = conn2.cursor(dictionary=True)

    query = '''SELECT 
                    orders.id,
                    orders.customer,
                    orders.model,
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
                    status NOT IN ("Cancle", "Order")
                ORDER BY orders.delivery_date ASC'''
    
    cursor.execute(query)
    orders = cursor.fetchall()

    query = '''SELECT * FROM production.quality_check'''
    cursor2.execute(query)
    check_item = cursor2.fetchall()

    # สร้างรายการผลลัพธ์
    matched_items = []

    # วนลูปผ่าน check_item เพื่อหา orders ที่มี id ตรงกับ sequence
    for check in check_item:
        for order in orders:
            if order['id'] == int(check['sequence']):
                # สร้าง dictionary ใหม่ที่รวมข้อมูลจากทั้งสองแหล่ง
                matched_item = {
                    'id': check['sequence'],
                    'check_date': check['check_date'],
                    'quantity': check['quantity'],
                    'customer': order['customer'],
                    'model': order['model'],
                    'delivery_date': order['delivery_date'],
                    'remark': order['remark'],
                    'size': order['size']
                }

                matched_items.append(matched_item)
                break  # หยุดเมื่อพบรายการที่ตรงกัน

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

    return render_template('qc/check_logs.html', orders = matched_items )

@qualitycontrol_bp.route('/check_stock', methods=['GET','POST'])
def check_stock():
    if not check_session(['AD','QC']):
        return redirect(url_for('home'))
    
    conn = db_connection()
    cursor = conn.cursor(dictionary=True)
    conn2 = pd_connection()
    cursor2 = conn2.cursor(dictionary=True)

    if request.method == 'POST':
        
        query = '''SELECT id, quantity FROM masterpallet.orders WHERE status NOT IN ("Cancle", "END", "Checked") AND stock = "Stock"'''
        cursor.execute(query)
        orders = {str(order['id']): order['quantity'] for order in cursor.fetchall()}

        data = request.get_json(silent=True)
        if not data or 'orders' not in data:
            return jsonify({'status': 'error', 'message': 'Invalid or missing data'}), 400
        checks = data.get('orders', [])
        
        for check in checks:
            order_id = str(check['order_id'])
            qty = int(check['quantity'])
            model = str(check['model'])

            if order_id in orders:
                sql_item = '''INSERT INTO production.stock_movements (`stock_id`, `type`, `sequence`, `quantity`) VALUES ((SELECT stock.id FROM production.stock WHERE stock.model = %s), %s, %s, %s)'''
                cursor2.execute(sql_item, (model, "IN", order_id, qty))

                # ดึงจำนวนที่เคยเช็คจาก stock_movements
                sql_sum = '''SELECT COALESCE(SUM(quantity), 0) AS total_checked 
                            FROM production.stock_movements 
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

                sql_update_stock = '''UPDATE production.stock 
                     SET quantity = quantity + %s 
                     WHERE model = %s'''
                cursor2.execute(sql_update_stock, (qty, model))

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
                        AND stock = "Stock"
                ORDER BY orders.id ASC'''
        
        cursor.execute(query)
        orders = cursor.fetchall()
        order_ids = [order['id'] for order in orders]
        
        if order_ids:
            placeholders = ', '.join(['%s'] * len(order_ids))

            stock_query = f"""SELECT 
                                sequence, 
                                SUM(quantity) AS total_quantity 
                            FROM 
                                production.stock_movements 
                            WHERE 
                                sequence IN ({placeholders}) 
                            GROUP BY 
                                sequence"""
            
            cursor2.execute(stock_query, order_ids)
            stock_movements = cursor2.fetchall()

            sums_map = {int(item['sequence']): item['total_quantity'] for item in stock_movements}

            for order in orders:
                used_quantity = sums_map.get(order['id'], 0)
                order['quantity'] -= used_quantity

        cursor.close()
        conn.close()
        cursor2.close()
        conn2.close()
        return render_template('qc/check_stock.html', orders = orders )