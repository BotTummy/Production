from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from db import db_connection, pd_connection
import mysql.connector
from datetime import datetime, timedelta
import calendar as cal

calendar_bp = Blueprint('calendar', __name__)

@calendar_bp.route('/calendar')
def calendar_view():
    """แสดงปฏิทินพร้อมรายการโมเดลตามวันที่ส่ง"""
    if 'loggedin' not in session:
        return redirect(url_for('login.login_page'))
    
    conn = db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get month and year from query parameters, default to current month
        year = request.args.get('year', datetime.now().year, type=int)
        month = request.args.get('month', datetime.now().month, type=int)
        
        # Get first and last day of the month
        first_day = datetime(year, month, 1)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # Fetch all orders with delivery dates in this month
        cursor.execute("""
            SELECT o.*, 
                   c.fullname as customer_name, 
                   c.callname as customer_short_name,
                   m.model,
                   m.model_type
            FROM orders o
            LEFT JOIN customers c ON o.customer = c.callname
            LEFT JOIN models m ON o.model = m.model
            WHERE o.delivery_date >= %s AND o.delivery_date <= %s
            AND o.status != 'Cancle'
            ORDER BY o.delivery_date ASC, m.model ASC
        """, (first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
        orders = cursor.fetchall()
        
        # Get all work in progress
        connpd = pd_connection()
        cursorpd = connpd.cursor(dictionary=True)
        cursorpd.execute("SELECT * FROM production.start_split")
        progress = cursorpd.fetchall()
        cursorpd.close()
        connpd.close()

        # Create a set of sequence IDs from progress for faster lookup
        progress_sequences = {
            int(p['sequence'])
            for p in progress
            if str(p.get('sequence')).isdigit()
        }

        # Update order status to "Spliting" if conditions are met
        for order in orders:
            if order['status'] in ['PlanA', 'PlanC'] and order['id'] in progress_sequences:
                order['status'] = 'Spliting'

        # Group orders by delivery date
        orders_by_date = {}
        for order in orders:
            if order['delivery_date']:
                date_key = order['delivery_date'].strftime('%Y-%m-%d')
                if date_key not in orders_by_date:
                    orders_by_date[date_key] = []
                orders_by_date[date_key].append(order)
        
        # Get calendar data
        month_calendar = cal.monthcalendar(year, month)
        month_name = cal.month_name[month]
        
        # Calculate previous and next month
        if month == 1:
            prev_month = 12
            prev_year = year - 1
        else:
            prev_month = month - 1
            prev_year = year
            
        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year
        
        # Get user info
        username = session.get('user_name')
        cursor.execute("SELECT userid, username, section FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        # Get today's date for highlighting
        today = datetime.now().strftime('%Y-%m-%d')
        
        return render_template('calendar_status.html', 
                             month_calendar=month_calendar,
                             orders_by_date=orders_by_date,
                             year=year,
                             month=month,
                             month_name=month_name,
                             prev_month=prev_month,
                             prev_year=prev_year,
                             next_month=next_month,
                             next_year=next_year,
                             today=today,
                             user=user)
        
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        flash("เกิดข้อผิดพลาดในการดึงข้อมูล", "error")
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()
