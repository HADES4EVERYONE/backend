from flask import Flask, request, session
import sqlite3

from utils import generate_session_id
from pymongo.mongo_client import MongoClient
from urllib.parse import quote_plus

app = Flask(__name__)
# In production, all the secret keys should be read from environment variables
app.secret_key = 'hades'
user = 'hades'
password = 'hades'
host = '16.171.7.170'
port = 27017
uri = "mongodb://%s:%s@%s:%s" % (
                quote_plus(user), quote_plus(password), host, port)
client = MongoClient(uri)
user_model_mg = client['hades']['user_model']
wish_list_mg = client['hades']['wishlist']
# set up the database
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        realname TEXT NOT NULL,
        username TEXT NOT NULL,
        password TEXT NOT NULL
    )
''')
conn.commit()


@app.route('/register', methods=['POST'])
def register():
    realname = request.json['realname']
    username = request.json['username']
    password = request.json['password']
    # Check if the username already exists
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if user:
        return {'message': 'User already exists.'}
    else:
        # Insert the new user
        cursor.execute("INSERT INTO users (realname, username, password) VALUES (?, ?, ?)", (realname, username, password))
        # login the user
        new_session_id = generate_session_id()
        session[new_session_id] = username
        return {'message': 'User created successfully.',
                'data': {'session_id': new_session_id, 'realname': realname, 'username': username}}


@app.route('/login', methods=['POST'])
def login():
    username = request.json['username']
    password = request.json['password']
    # Check if the username and password are correct
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    if user:
        new_session_id = generate_session_id()
        session[new_session_id] = username
        return {'message': 'Login successful.', 'data':
            {'session_id': new_session_id, 'username': username, 'realname': user[1]}}
    else:
        return {'message': 'Incorrect username or password.'}


@app.route('/logout', methods=['POST'])
def logout():
    session_id = request.json['session_id']
    if session_id in session:
        session.pop(session_id)
        return {'message': 'Logged out successfully.'}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/get_model', methods=['GET'])
def get_model():
    session_id = request.headers.get('session_id')
    if session_id in session:
        username = session[session_id]
        u = user_model_mg.find_one({'username': username})
        return {'message': 'Model retrieved successfully.', 'data': u['model']}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/update_model', methods=['POST'])
def update_model():
    session_id = request.headers.get('session_id')
    if session_id in session:
        username = session[session_id]
        new_model = request.json['model']
        user_model_mg.update_one({'username': username}, {'$set': {'model': new_model}})
        return {'message': 'Model updated successfully.'}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/get_wishlist', methods=['GET'])
def get_wishlist():
    session_id = request.headers.get('session_id')
    if session_id in session:
        username = session[session_id]
        wish_list = wish_list_mg.find_one({'username': username})
        return {'message': 'wishlist retrieved successfully.', 'data': wish_list['wish_list']}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/update_wish_list', methods=['POST'])
def add_to_wishlist():
    session_id = request.headers.get('session_id')
    if session_id in session:
        username = session[session_id]
        wish_list = request.json['wish_list']
        wish_list_mg.update_one({'username': username}, {'$set': {'wish_list': wish_list}})
        return {'message': 'wish_list updated successfully.'}
    else:
        return {'message': 'Invalid session ID.'}


if __name__ == '__main__':
    app.run(debug=True)
