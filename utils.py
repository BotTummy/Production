from flask import session, flash

def check_session(required_sections=None):
    if 'loggedin' not in session or session['loggedin'] != True:
        flash('You need to log in first.', 'warning')
        return False
    
    if required_sections and session.get('section') not in required_sections:
        flash('You are not authorized to access this page.', 'danger')
        return False

    return True
