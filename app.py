from flask import Flask, request, session
import sqlite3

from utils import generate_session_id


app = Flask(__name__)
app.secret_key = 'hades'

# set up the database
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL
    )
''')
conn.commit()


@app.route('/register', methods=['POST'])
def register():
    username = request.json['username']
    password = request.json['password']
    # Check if the username already exists
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if user:
        return {'message': 'User already exists.'}
    else:
        # Insert the new user
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        return {'message': 'User created successfully.'}


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
        return {'message': 'Login successful.', 'data': {'session_id': new_session_id}}
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


if __name__ == '__main__':
    app.run(debug=True)
