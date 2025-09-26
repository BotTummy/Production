import mysql.connector

def db_connection():
    conn = mysql.connector.connect(
        # host='localhost',
        host='119.59.101.135',
        user='root',
        password='Isylzjko0',
        database='masterpallet'
    )
    return conn

def pd_connection():
    conn = mysql.connector.connect(
        # host='localhost',
        host='69759854e4f4',
        user='root',
        password='Isylzjko0',
        database='production'
    )
    return conn
