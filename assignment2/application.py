from flask import Flask, redirect, request, url_for

import requests

from flask import request
from flask import Flask, render_template

from jinja2 import Template
import secrets

import base64
import json
import os


from flask import session


app = Flask(__name__)

app.secret_key = secrets.token_hex() 


from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    },
     'file.handler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'weatherportal.log',
            'maxBytes': 10000000,
            'backupCount': 5,
            'level': 'DEBUG',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file.handler']
    }
})

# [CityDetails(name:Austin, year:2023, month:08, params:[TMAX,TMIN], CityDetails(name:Dallas])
# Filled by the Admin workflow
in_mem_cities = []

# {username: [CityDetails(name:Austin, year:2023, month:08, params:[TMAX,TMIN], CityDetails(name:Dallas)]}
# Filled by user workflow
in_mem_user_cities = {}


class CityDetails:
    def __init__(self, name='', month='', year='', params=None):
        self.name = name
        self.month = month
        self.year = year
        self.params = params if params is not None else []
    

weather_parameters_to_track = ['TMAX','TMIN','PRCP','SNOW']


@app.route("/status", methods=['GET'])
def city_status():
    op = {}
    app.logger.info("Inside city_status")
    city_name = request.args.get('city').strip()
    app.logger.info("City status:" + city_name)
    
    username = ''
    if 'username' in session:
        username = session['username']

    app.logger.info("Username:" + username + " City:" + city_name)
    cities_to_check = []
    if username in in_mem_user_cities:
        cities_to_check = in_mem_user_cities[username]
    else:
        cities_to_check = in_mem_cities

    city_details = None
    for c in cities_to_check:
        if c.name == city_name:
            city_details = c
            break

    if city_details is None:
        return json.dumps({
            "name": city_name,
            "month": "",
            "year": "",
            "params": ""
        })

    # Assignment2 TODO: Add month, year, params to op
    op["name"] = city_details.name
    op["month"] = city_details.month or ""
    op["year"] = city_details.year or ""
    params = city_details.params or []
    op["params"] = ", ".join(params) if len(params) > 0 else ""

    app.logger.info(op)
    return json.dumps(op)


@app.route("/addcity", methods=['POST','GET'])
def addcity():
    app.logger.info("Inside addcity")
    city_name = request.args.get('city_name').strip()
    city = CityDetails(name=city_name)
    in_mem_cities.append(city)

    username = ''
    if 'username' in session:
        username = session['username']

    user_cities = in_mem_cities
    return render_template('welcome.html',
            welcome_message = "Personal Weather Portal - Admin Panel",
            status_string=f"Registered city {city_name}.",
            cities=user_cities,
            name=username,
            addButton_style="display:inline;",
            addCityForm_style="display:none;",
            regButton_style="display:none;",
            regForm_style="display:none;",
            status_style="display:block;")


@app.route("/registercity", methods=['POST','GET'])
def registercity():
    app.logger.info("Inside registercity")

    username = ''
    if 'username' in session:
        username = session['username']

    city_name = request.args.get('city_name').strip()

    # Assignment2 TODO:
    # Parse year and month
    year = request.args.get("year", "").strip()
    month = request.args.get("month", "").strip()
    app.logger.info(f"City:{city_name} Year:{year} Month:{month}")
 
    user_weather_params = [] 
    if 'max_temp' in request.args:
        user_weather_params.append('TMAX')

    # Assignment2 TODO:
    # Parse and save min_temp, precipitation, snow
    if "min_temp" in request.args:
        user_weather_params.append("TMIN")
    if "precipitation" in request.args:
        user_weather_params.append("PRCP")
    if "snow" in request.args:
        user_weather_params.append("SNOW")

    app.logger.info(user_weather_params)

    present = any(c.name == city_name for c in in_mem_cities)
    my_cities = in_mem_user_cities.get(username, [])

    if present:
        city_details = CityDetails(
            name=city_name,
            year=year,
            month=month,
            params=user_weather_params,
        )

        # Prevent duplicate cities
        my_cities = [c for c in my_cities if c.name != city_name]
        my_cities.append(city_details)
        in_mem_user_cities[username] = my_cities

        status_msg = f"Registered city {city_name}."
    else:
        status_msg = f"Weather data for city {city_name} not available."

    return render_template(
        "welcome.html",
        welcome_message="Personal Weather Portal",
        cities=my_cities,
        name=username,
        status_string=status_msg,
        addButton_style="display:none;",
        addCityForm_style="display:none;",
        regButton_style="display:inline;",   
        regForm_style="display:none;",
        status_style="display:block;",
    )

@app.route("/logout",methods=['GET'])
def logout():
    app.logger.info("Logout called.")
    session.pop('username', None)
    app.logger.info("Before returning...")
    return render_template('index.html')


@app.route("/login", methods=['POST'])
def login():
    username = request.form['username'].strip()
    password = request.form['password'].strip()
    app.logger.info("Username:%s", username)
    app.logger.info("Password:%s", password)

    session['username'] = username

    my_cities = []
    if username in in_mem_user_cities:
        my_cities = in_mem_user_cities[username]
    return render_template('welcome.html',
            welcome_message = "Personal Weather Portal",
            cities=my_cities,
            name=username,
            addButton_style="display:none;",
            addCityForm_style="display:none;",
            regButton_style="display:inline;",
            regForm_style="display:inline;",
            status_style="display:none;")


@app.route("/")
def index():
    return render_template('index.html')


# Assignment2 TODO: Add route for "/adminlogin"
# This should be the action of the admin form submission
# Use the login() method for reference
@app.route("/adminlogin", methods=["POST"])
def adminlogin():
    username = request.form["username"].strip()
    password = request.form["password"].strip()


    session["username"] = username
    session["is_admin"] = True

    user_cities = in_mem_cities

    return render_template(
        "welcome.html",
        welcome_message="Personal Weather Portal - Admin Panel",
        cities=user_cities,
        name=username,
        addButton_style="display:inline;",
        addCityForm_style="display:inline;",
        regButton_style="display:none;",
        regForm_style="display:none;",
        status_style="display:block;",
    )


# Assignment2 TODO: Add route and method for "/admin" path
# This should respond with adminindex.html
# Use the index() method for reference.
@app.route("/admin", methods=["GET"])
def admin():
    return render_template("adminindex.html")


if __name__ == "__main__":

    app.debug = False
    app.logger.info('Portal started...')
    app.run(host='0.0.0.0', port=5009) 
