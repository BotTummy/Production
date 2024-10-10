import mysql.connector

def db_connection():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='Isylzjko0',
        database='production'
    )
    return conn