import mysql.connector

def db_connection():
    conn = mysql.connector.connect(
        host='f5da8fc4b539',
        # host='localhost',
        user='root',
        password='Isylzjko0',
        database='production'
    )
    return conn