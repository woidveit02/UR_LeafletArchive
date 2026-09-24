import os
import datetime
import logging
import jwt

from flask import Flask, render_template

from .database.session import session
from .database.models import Leaflet

# Room list page
@app.route('/rooms', methods=['GET'])
    
def room_list():

    leaflets = session.query(Leaflet).all()

    return render_template('room_list.html', leaflets=leaflets)

