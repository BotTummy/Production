import mysql.connector

def db_connection():
    conn = mysql.connector.connect(
        host='e0e396e9438a',
        # host='localhost',
        user='root',
        password='Isylzjko0',
        database='production'
    )
    return conn