from flask import render_template, redirect, url_for, flash, Blueprint, session, request
from db import db_connection
from form import QualityForm
from datetime import datetime

quality_bp = Blueprint('quality', __name__, template_folder='templates/')