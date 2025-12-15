from flask import Flask, render_template, request, session, redirect, url_for
from flask_bcrypt import Bcrypt
from login import login_bp
from qualitycontrol import qualitycontrol_bp
from cut import cut_bp
from split import split_bp
from dashboard import dashboard_bp
from assembly import assy_bp
from split_dashboard import split_db_bp 
from calendar_status import calendar_bp

app = Flask(__name__)
app.register_blueprint(login_bp)
app.register_blueprint(qualitycontrol_bp)
app.register_blueprint(cut_bp)
app.register_blueprint(assy_bp)
app.register_blueprint(split_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(split_db_bp)
app.register_blueprint(calendar_bp)

app.config['SECRET_KEY'] = 'MasterPallet'
app.config['MAX_CONTENT_PATH'] = 16 * 1024 * 1024

bcrypt = Bcrypt(app)

@app.route('/', methods=['GET'])
def home():
    if 'loggedin' in session and session['loggedin'] == True:
        return render_template('index.html', username = session['username'])
    return redirect(url_for('login.login'))

if __name__ == "__main__":
      app.run(debug=True)