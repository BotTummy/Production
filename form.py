from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, NumberRange

class SequenceForm(FlaskForm):
    sequence_number = StringField('Sequence Number', validators=[DataRequired()])
    number_in_sequence = IntegerField('Quantity In Work', validators=[DataRequired()],)
    submit = SubmitField('Submit')

class CutForm(FlaskForm):
    sequence_number = StringField('Sequence Number', validators=[DataRequired()])
    number_in_sequence = IntegerField('Work Number', validators=[DataRequired()])
    quantity_work = IntegerField('Quantity', validators=[NumberRange(min=0, max=10000)])
    submit = SubmitField('Submit')

class SlideForm(FlaskForm):
    sequence_number = StringField('Sequence Number', validators=[DataRequired()])
    number_in_sequence = IntegerField('Work Number', validators=[DataRequired()])
    quantity_work = IntegerField('Quantity', validators=[NumberRange(min=0, max=10000)])
    submit = SubmitField('Submit')

class AssemblyForm(FlaskForm):
    sequence_number = StringField('Sequence Number', validators=[DataRequired()])
    assembly_line = SelectField('Assembly Line', choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('UACJ', 'UACJ'), ('O', 'O')])
    quantity_work = IntegerField('Quantity', validators=[NumberRange(min=0, max=10000)])
    submit = SubmitField('Submit')
    
class OvenForm(FlaskForm):
    sequence_number = StringField('Sequence Number', validators=[DataRequired()])
    quantity_oven = IntegerField('Quantity', validators=[NumberRange(min=0, max=10000)])
    submit = SubmitField('Submit')

class QualityForm(FlaskForm):
    sequence_number = StringField('Sequence Number', validators=[DataRequired()])
    submit = SubmitField('Submit')