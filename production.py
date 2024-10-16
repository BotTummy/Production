from flask import render_template, redirect, url_for, flash, Blueprint, session, request
from db import db_connection
from form import SequenceForm, CutForm, SlideForm, AssemblyForm, OvenForm
from datetime import datetime

production_bp = Blueprint('production', __name__, template_folder='templates/')

@production_bp.route('/add_sequence', methods=['GET', 'POST'])
def add_sequence():
    session.pop('_flashes', None)
    form = SequenceForm()
    if form.validate_on_submit():
        sequence_number = form.sequence_number.data
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM plan WHERE sequence = %s', (sequence_number,))
        existing_sequence = cursor.fetchone()

        if existing_sequence:
            flash('Sequence number already exists.', 'danger')
        else:
            cursor.execute('INSERT INTO plan (sequence, number_in_sequeance) VALUES (%s, %s)', 
                           (sequence_number, form.number_in_sequence.data))
            conn.commit()
            flash('Sequence number added successfully!', 'success')

        cursor.close()
        conn.close()
        return redirect(url_for('home'))

    return render_template('add_sequence.html', form=form)

@production_bp.route('/start_cut', methods=['GET', 'POST'])
def start_cut():
    form = CutForm()
    session.pop('_flashes', None)
    if form.validate_on_submit():
        machine = request.form.get('machine')
        sequence = form.sequence_number.data
        number = form.number_in_sequence.data
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT sequence FROM plan WHERE sequence = %s',(sequence,))
        check_sequence = cursor.fetchone()
        cursor.execute('SELECT idcut FROM cut WHERE sequence = %s AND number_in_sequeance = %s',(sequence, number,))
        exiting_cut = cursor.fetchone()

        if check_sequence:
            if not exiting_cut:
                cursor.execute('INSERT INTO cut (machine, sequence, number_in_sequeance) VALUES (%s, %s, %s)', (machine, sequence, number,))
                conn.commit()
                cursor.close()
                conn.close()
                flash('start cut successfully!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Cut is Exits!', 'danger') 
        else:
            flash('Sequence not match!', 'danger') 
    return render_template('cut.html', form=form)

@production_bp.route('/end_cut', methods=['GET', 'POST'])
def end_cut():
    form = CutForm()
    session.pop('_flashes', None)
    sequence = form.sequence_number.data
    number = form.number_in_sequence.data
    quantity = form.quantity_work.data
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT cut FROM plan WHERE sequence = %s',(sequence,))
    cut_end = cursor.fetchone()
    cursor.execute('SELECT idcut FROM cut WHERE sequence = %s AND number_in_sequeance = %s AND cut_end IS NULL',(sequence, number,))
    exiting_cut = cursor.fetchone()
    
    if exiting_cut:
        cut_end_time = datetime.now()
        cursor.execute('UPDATE cut SET cut_end = %s, quantity_work = %s WHERE sequence = %s AND number_in_sequeance = %s', 
                (cut_end_time, quantity, sequence, number))
        conn.commit()

        num_cut_end = cut_end[0]
        num_cut_end += 1

        cursor.execute('''UPDATE plan SET cut = %s, status = CASE WHEN cut = number_in_sequeance THEN 'Cut OK' ELSE status END WHERE sequence = %s''', 
                (num_cut_end, sequence))
        conn.commit()

        cursor.close()
        conn.close()
        flash('cut End successfully!', 'success')
        return redirect(url_for('home'))
    else:
        flash('Sequence not match! or Sequence exits', 'danger') 
    return render_template('cut.html', form=form)

@production_bp.route('/slide', methods=['GET', 'POST'])
def slide():
    return render_template('slideindex.html')

@production_bp.route('/start_slide/<int:machine>', methods=['GET', 'POST'])
def start_slide(machine):
    session.pop('_flashes', None)
    form = SlideForm()
    if form.validate_on_submit():
        sequence = form.sequence_number.data
        number = form.number_in_sequence.data
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT sequence FROM plan WHERE sequence = %s',(sequence,))
        check_sequence = cursor.fetchone()
        cursor.execute('SELECT idslide FROM slide WHERE sequence = %s AND number_in_sequeance = %s',(sequence, number,))
        exiting_slide = cursor.fetchone()

        if check_sequence:
            if not exiting_slide:
                cursor.execute('INSERT INTO slide (machine, sequence, number_in_sequeance) VALUES (%s, %s, %s)', (machine, sequence, number,))
                conn.commit()
                cursor.close()
                conn.close()
                flash('Start Slide successfully!', 'success')
                return render_template('slideindex.html', form=form, machine=machine)
            else:
                flash('Slide is Exits!', 'danger') 
        else:
            flash('Sequence not match!', 'danger') 
    return render_template('slide.html', form=form, machine=machine)

@production_bp.route('/end_slide/<int:machine>', methods=['GET', 'POST'])
def end_slide(machine):
    form = SlideForm()
    session.pop('_flashes', None)
    sequence = form.sequence_number.data
    number = form.number_in_sequence.data
    quantity = form.quantity_work.data
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT slide FROM plan WHERE sequence = %s',(sequence,))
    slide_end = cursor.fetchone()
    cursor.execute('SELECT idslide FROM slide WHERE sequence = %s AND number_in_sequeance = %s AND machine = %s AND slide_end IS NULL',(sequence, number, machine,))
    exiting_slide = cursor.fetchone()
    
    if exiting_slide:
        slide_end_time = datetime.now()
        cursor.execute('UPDATE slide SET slide_end = %s, quantity_work = %s WHERE sequence = %s AND number_in_sequeance = %s', 
                (slide_end_time, quantity, sequence, number))
        conn.commit()

        num_slide_end = slide_end[0]
        num_slide_end += 1

        cursor.execute('''UPDATE plan SET slide = %s, status = CASE WHEN slide = number_in_sequeance THEN 'Slide OK' ELSE status END WHERE sequence = %s ''', 
                (num_slide_end, sequence))
        conn.commit()
        
        cursor.close()
        conn.close()
        flash('slide End successfully!', 'success')
        return render_template('slideindex.html', form=form, machine=machine)
    else:
        flash('Sequence not match! or Sequence exits', 'danger') 
    return render_template('slide.html', form=form,  machine=machine)
    
@production_bp.route('/start_assy', methods=['GET', 'POST'])
def start_assy():
    session.pop('_flashes', None)
    form = AssemblyForm()
    if form.validate_on_submit():
        sequence = form.sequence_number.data
        assembly_line = form.assembly_line.data
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT sequence FROM plan WHERE sequence = %s',(sequence,))
        check_sequence = cursor.fetchone()
        cursor.execute('SELECT idassembly FROM assembly WHERE sequence = %s',(sequence,))
        exiting_assy = cursor.fetchone()

        if check_sequence:
            if not exiting_assy:
                cursor.execute('INSERT INTO assembly (sequence, assembly_line) VALUES (%s, %s)', (sequence, assembly_line,))
                conn.commit()
                cursor.close()
                conn.close()
                flash('start Assembly successfully!', 'success')
                form.sequence_number.data = ""
                form.assembly_line.data = ""
                return render_template('assembly.html', form=form)
            else:
                flash('Assembly is Exits!', 'danger')
        else:
            flash('Sequence not match!', 'danger')
    return render_template('assembly.html', form=form)

@production_bp.route('/end_assy', methods=['GET', 'POST'])
def end_assy():
    session.pop('_flashes', None)
    form = AssemblyForm()
    form.assembly_line.data = "O"
    if form.validate_on_submit():
        sequence = form.sequence_number.data
        quantity = form.quantity_work.data
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT sequence FROM plan WHERE sequence = %s',(sequence,))
        check_sequence = cursor.fetchone()
        cursor.execute('SELECT idassembly FROM assembly WHERE sequence = %s AND assembly_end IS NOT NULL',(sequence,))
        exiting_assy = cursor.fetchone()

        if check_sequence:
            if not exiting_assy:
                assy_end_time = datetime.now()

                cursor.execute('UPDATE assembly SET assembly_end = %s, quantity_work = %s WHERE sequence = %s', 
                        (assy_end_time, quantity, sequence))
                conn.commit()

                cursor.execute('''UPDATE plan SET assembly = %s, status = 'Assy OK' WHERE sequence = %s ''', 
                (quantity, sequence))
                conn.commit()
                
                cursor.close()
                conn.close()
                flash('Assembly End successfully!', 'success')

                form.sequence_number.data = ""
                form.assembly_line.data = ""
                form.quantity_work.data = ""
                return render_template('assembly.html', form=form)
            else:
                flash('Assembly is Exits!', 'danger')
        else:
            flash('Sequence not match!', 'danger')
    return render_template('assembly.html', form=form)

@production_bp.route('/start_oven', methods=['GET', 'POST'])
def start_oven():
    session.pop('_flashes', None)
    form = OvenForm()
    if form.validate_on_submit():
        sequence = form.sequence_number.data
        quantity_oven = form.quantity_oven.data
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT sequence FROM plan WHERE sequence = %s',(sequence,))
        check_sequence = cursor.fetchone()
        cursor.execute('SELECT idoven FROM oven WHERE sequence = %s',(sequence,))
        exiting_oven = cursor.fetchone()

        if check_sequence:
            if not exiting_oven:
                cursor.execute('INSERT INTO oven (sequence, quantity_oven) VALUES (%s, %s)', (sequence, quantity_oven,))
                conn.commit()
                cursor.close()
                conn.close()
                flash('start Oven!', 'success')
                form.sequence_number.data = ""
                form.quantity_oven.data = ""
                return render_template('oven.html', form=form)
            else:
                flash('Sequence is Exits!', 'danger')
        else:
            flash('Sequence not match!', 'danger')
    return render_template('oven.html', form=form)

@production_bp.route('/end_oven', methods=['GET', 'POST'])
def end_oven():
    session.pop('_flashes', None)
    form = OvenForm()
    if form.validate_on_submit():
        sequence = form.sequence_number.data
        quantity = form.quantity_work.data
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT sequence FROM plan WHERE sequence = %s',(sequence,))
        check_sequence = cursor.fetchone()
        cursor.execute('SELECT idoven FROM oven WHERE sequence = %s AND oven_end IS NOT NULL',(sequence,))
        exiting_oven = cursor.fetchone()

        if check_sequence:
            if not exiting_oven:
                oven_end_time = datetime.now()

                cursor.execute('UPDATE oven SET oven_end = %s, quantity_work = %s WHERE sequence = %s', 
                        (oven_end_time, quantity, sequence))
                conn.commit()

                cursor.execute('''UPDATE plan SET oven = %s, status = 'Oven OK' WHERE sequence = %s ''', 
                (quantity, sequence))
                conn.commit()
                
                cursor.close()
                conn.close()
                flash('Oven End successfully!', 'success')

                form.sequence_number.data = ""
                form.assembly_line.data = ""
                form.quantity_work.data = ""
                return render_template('assembly.html', form=form)
            else:
                flash('Oven is Exits!', 'danger')
        else:
            flash('Sequence not match!', 'danger')
    return render_template('oven.html', form=form)