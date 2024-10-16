from flask import Flask, render_template, request
from production import production_bp
from db import db_connection

app = Flask(__name__)
app.register_blueprint(production_bp)

app.config['SECRET_KEY'] = 'MasterPallet'

@app.route('/', methods=['GET'])
def home():
    return render_template('home.html')

@app.route('/search_plan', methods=['GET'])
def search_plan():
    search_term = request.args.get('search', '')
    
    conn = db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if search_term:
        cursor.execute('SELECT * FROM plan WHERE sequence LIKE %s OR status LIKE %s', (f'%{search_term}%', f'%{search_term}%'))
    else:
        cursor.execute('SELECT * FROM plan')
    
    plans = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('home.html', plans=plans)

if __name__ == "__main__":
    app.run(debug=True)