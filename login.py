from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_bcrypt import generate_password_hash, check_password_hash
from db import pd_connection
from forms import RegistrationForm, LoginForm

login_bp = Blueprint('login', __name__, template_folder='templates/login')

@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        conn = pd_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s', (form.username.data,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and check_password_hash(user['password'], form.password.data):
            session['loggedin'] = True
            session['username'] = user['username']
            session['user_name'] = user['username']
            session['section'] = user['section']
            session['user_section'] = user['section']
            flash('Logged in successfully!', 'success')
            return render_template('index.html')
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login/login.html', form=form)

@login_bp.route('/logout')
def logout():
    session['loggedin'] = False
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out!', 'success')
    return redirect(url_for('login.login'))

@login_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        if form.boss_confirm.data == "MasterConfirm":
            conn = pd_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM production.users WHERE username = %s', (form.username.data,))
            user = cursor.fetchone()
            if user:
                flash('Username already taken. Please choose a different one.', 'danger')
                return render_template('login/register.html', form=form)
            
            hashed_password = generate_password_hash(form.password.data).decode('utf-8')
            cursor.execute('INSERT INTO users (username, password, section) VALUES (%s, %s, %s)',
                        (form.username.data, hashed_password, form.section.data))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Account created successfully!', 'success')
            return redirect(url_for('login.login'))
        else:
            flash('Account can not created !', 'danger')
            return render_template('login/register.html', form=form)
    return render_template('login/register.html', form=form)
