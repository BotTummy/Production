import mysql.connector

def db_connection():
    conn = mysql.connector.connect(
        # host='75f8c2ff60c3',
        host='localhost',
        user='root',
        password='Isylzjko0',
        database='production'
    )
    return conn