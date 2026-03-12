from flask import Flask, redirect, request, url_for
from flask import Response

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


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, ForeignKey, String, UniqueConstraint

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

# SQLite Database creation
Base = declarative_base()
engine = create_engine("sqlite:///weatherportal.db", echo=True, future=True)
DBSession = sessionmaker(bind=engine)


@app.before_first_request
def create_tables():
    Base.metadata.create_all(engine)


class Admin(Base):
    __tablename__ = 'admin'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    password = Column(String)

    def __repr__(self):
        return "<Admin(name='%s')>" % (self.name)

    # Ref: https://stackoverflow.com/questions/5022066/how-to-serialize-sqlalchemy-result-to-json
    def as_dict(self):
        fields = {}
        for c in self.__table__.columns:
            fields[c.name] = getattr(self, c.name)
        return fields


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True)
    password = Column(String)

    user_cities = relationship("UserCity", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return "<User(name='%s')>" % (self.name)

    def as_dict(self):
        fields = {}
        for c in self.__table__.columns:
            fields[c.name] = getattr(self, c.name)
        return fields


class City(Base):
    __tablename__ = 'cities'
    id = Column(Integer, primary_key=True, autoincrement=True)
    adminid = Column(Integer, ForeignKey("admin.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    url = Column(String, nullable=False)

    admin = relationship("Admin")
    user_cities = relationship("UserCity", back_populates="city", cascade="all, delete-orphan")

    def __repr__(self):
        return "<City(name='%s', adminid='%s')>" % (self.name, self.adminid)

    def as_dict(self):
        fields = {}
        for c in self.__table__.columns:
            fields[c.name] = getattr(self, c.name)
        return fields


class UserCity(Base):
    __tablename__ = 'user_cities'
    id = Column(Integer, primary_key=True, autoincrement=True)
    cityId = Column(Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True)
    userId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month = Column(String, nullable=False)
    year = Column(String, nullable=False)
    weather_params = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("cityId", "userId", name="uq_user_city"),
    )

    user = relationship("User", back_populates="user_cities")
    city = relationship("City", back_populates="user_cities")

    def __repr__(self):
        return "<UserCity(userId='%s', cityId='%s')>" % (self.userId, self.cityId)

    def as_dict(self):
        fields = {}
        for c in self.__table__.columns:
            fields[c.name] = getattr(self, c.name)
        return fields


def _is_valid_year(year):
    year_str = str(year)
    return len(year_str) == 4 and year_str.isdigit()



## Admin REST API
@app.route("/admin", methods=['POST'])
def add_admin():
    app.logger.info("Inside add_admin")
    data = request.json
    app.logger.info("Received request:%s", str(data))

    name = data['name']
    password = data['password']

    admin = Admin(name=name, password=password)

    session = DBSession()
    session.add(admin)
    session.commit()

    return admin.as_dict()


@app.route("/admin")
def get_admins():
    app.logger.info("Inside get_admins")
    ret_obj = {}

    session = DBSession()
    admins = session.query(Admin)
    admin_list = []
    for admin in admins:
        admin_list.append(admin.as_dict())

    ret_obj['admins'] = admin_list
    return ret_obj


@app.route("/admin/<id>")
def get_admin_by_id(id):
    app.logger.info("Inside get_admin_by_id %s\n", id)

    session = DBSession()
    admin = session.get(Admin, id)

    app.logger.info("Found admin:%s\n", str(admin))
    if admin == None:
        status = ("Admin with id {id} not found\n").format(id=id)
        return Response(status, status=404)
    else:
        return admin.as_dict()


@app.route("/admin/<id>", methods=['DELETE'])
def delete_admin_by_id(id):
    app.logger.info("Inside delete_admin_by_id %s\n", id)

    session = DBSession()
    admin = session.query(Admin).filter_by(id=id).first()

    app.logger.info("Found admin:%s\n", str(admin))
    if admin == None:
        status = ("Admin with id {id} not found.\n").format(id=id)
        return Response(status, status=404)
    else:
        session.delete(admin)
        session.commit()
        status = ("Admin with id {id} deleted.\n").format(id=id)
        return Response(status, status=200)


## Users REST API
@app.route("/users", methods=['POST'])
def add_user():
    app.logger.info("Inside add_user")
    data = request.json
    app.logger.info("Received request:%s", str(data))

    name = data['name']
    password = data['password']

    db = DBSession()
    existing = db.query(User).filter_by(name=name).first()
    if existing is not None:
        status = ("User with {name} already exists.\n").format(name=name)
        return Response(status, status=400)

    user = User(name=name, password=password)
    db.add(user)
    db.commit()
    return user.as_dict()


@app.route("/users")
def get_users():
    app.logger.info("Inside get_users")
    ret_obj = {}

    db = DBSession()
    users = db.query(User)
    user_list = []
    for user in users:
        user_list.append(user.as_dict())

    ret_obj['users'] = user_list
    return ret_obj


@app.route("/users/<id>")
def get_user_by_id(id):
    app.logger.info("Inside get_user_by_id %s\n", id)

    db = DBSession()
    user = db.get(User, id)

    app.logger.info("Found user:%s\n", str(user))
    if user is None:
        status = ("User with id {id} not found.\n").format(id=id)
        return Response(status, status=404)
    return user.as_dict()


@app.route("/users/<id>", methods=['DELETE'])
def delete_user_by_id(id):
    app.logger.info("Inside delete_user_by_id %s\n", id)

    db = DBSession()
    user = db.query(User).filter_by(id=id).first()

    app.logger.info("Found user:%s\n", str(user))
    if user is None:
        status = ("User with id {id} not found.\n").format(id=id)
        return Response(status, status=404)

    db.delete(user)
    db.commit()
    status = ("User with {id} deleted.\n").format(id=id)
    return Response(status, status=200)


## Cities (admin) REST API
@app.route("/admin/<admin_id>/cities", methods=['POST'])
def add_city(admin_id):
    app.logger.info("Inside add_city admin_id=%s", admin_id)
    data = request.json
    app.logger.info("Received request:%s", str(data))

    name = data['name']
    url = data['url']

    db = DBSession()
    admin = db.get(Admin, admin_id)
    if admin is None:
        status = ("Admin with id {id} not found.\n").format(id=admin_id)
        return Response(status, status=404)

    city = City(adminid=int(admin_id), name=name, url=url)
    db.add(city)
    db.commit()
    return city.as_dict()


@app.route("/admin/<admin_id>/cities")
def get_cities(admin_id):
    app.logger.info("Inside get_cities admin_id=%s", admin_id)
    ret_obj = {}

    db = DBSession()
    admin = db.get(Admin, admin_id)
    if admin is None:
        status = ("Admin with id {id} not found.\n").format(id=admin_id)
        return Response(status, status=404)

    cities = db.query(City).filter_by(adminid=int(admin_id))
    city_list = []
    for city in cities:
        city_list.append(city.as_dict())

    ret_obj['cities'] = city_list
    return ret_obj


@app.route("/admin/<admin_id>/cities/<city_id>")
def get_city_by_id(admin_id, city_id):
    app.logger.info("Inside get_city_by_id admin_id=%s city_id=%s", admin_id, city_id)

    db = DBSession()
    admin = db.get(Admin, admin_id)
    if admin is None:
        status = ("Admin with id {id} not found.\n").format(id=admin_id)
        return Response(status, status=404)

    city = db.query(City).filter_by(id=city_id, adminid=int(admin_id)).first()
    if city is None:
        status = ("City with id {id} not found.\n").format(id=city_id)
        return Response(status, status=404)
    return city.as_dict()


@app.route("/admin/<admin_id>/cities/<city_id>", methods=['DELETE'])
def delete_city_by_id(admin_id, city_id):
    app.logger.info("Inside delete_city_by_id admin_id=%s city_id=%s", admin_id, city_id)

    db = DBSession()
    admin = db.get(Admin, admin_id)
    if admin is None:
        status = ("Admin with id {id} not found.\n").format(id=admin_id)
        return Response(status, status=404)

    city = db.query(City).filter_by(id=city_id, adminid=int(admin_id)).first()
    if city is None:
        status = ("City with id {id} not found.\n").format(id=city_id)
        return Response(status, status=404)

    db.delete(city)
    db.commit()
    status = ("City with {id} deleted.\n").format(id=city_id)
    return Response(status, status=200)


## User Cities REST API
@app.route("/users/<user_id>/cities", methods=['POST'])
def add_user_city(user_id):
    app.logger.info("Inside add_user_city user_id=%s", user_id)
    data = request.json
    app.logger.info("Received request:%s", str(data))

    city_name = data['name']
    month = data['month']
    year = str(data['year'])
    params = data['params']

    db = DBSession()
    user = db.get(User, user_id)
    if user is None:
        status = ("User with id {id} not found.\n").format(id=user_id)
        return Response(status, status=404)

    city = db.query(City).filter_by(name=city_name).first()
    if city is None:
        status = ("City with name {name} not found.\n").format(name=city_name)
        return Response(status, status=404)

    if not _is_valid_year(year):
        status = "Year needs to be exactly four digits.\n"
        return Response(status, status=400)

    user_city = UserCity(
        cityId=city.id,
        userId=int(user_id),
        month=month,
        year=year,
        weather_params=params
    )
    db.add(user_city)
    db.commit()
    return user_city.as_dict()


@app.route("/users/<user_id>/cities")
def get_user_cities(user_id):
    app.logger.info("Inside get_user_cities user_id=%s", user_id)

    name = request.args.get('name')

    db = DBSession()
    user = db.get(User, user_id)
    if user is None:
        status = ("User with id {id} not found.\n").format(id=user_id)
        return Response(status, status=404)

    if name is None:
        user_cities = db.query(UserCity).filter_by(userId=int(user_id))
        user_city_list = []
        for uc in user_cities:
            user_city_list.append(uc.as_dict())
        return {"usercities": user_city_list}

    city = db.query(City).filter_by(name=name).first()
    if city is None:
        status = ("City with name {name} not found.\n").format(name=name)
        return Response(status, status=404)

    tracked = db.query(UserCity).filter_by(userId=int(user_id), cityId=city.id).first()
    if tracked is None:
        status = ("City with name {name} not being tracked by the user {uname}.\n").format(
            name=name, uname=user.name
        )
        return Response(status, status=404)

    return {
        "name": city.name,
        "month": tracked.month,
        "year": str(tracked.year),
        "weather_params": tracked.weather_params
    }


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


@app.route("/adminlogin", methods=['POST'])
def adminlogin():
    username = request.form['username'].strip()
    password = request.form['password'].strip()
    app.logger.info("Username:%s", username)
    app.logger.info("Password:%s", password)

    session['username'] = username

    user_cities = []
    return render_template('welcome.html',
            welcome_message = "Personal Weather Portal - Admin Panel",
            cities=user_cities,
            name=username,
            addButton_style="display:inline;",
            addCityForm_style="display:inline;",
            regButton_style="display:none;",
            regForm_style="display:none;",
            status_style="display:none;")


@app.route("/adminui")
def adminindex():
    return render_template('adminindex.html')


if __name__ == "__main__":

    app.debug = False
    app.logger.info('Portal started...')
    app.run(host='0.0.0.0', port=5009) 
