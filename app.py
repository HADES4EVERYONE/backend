from flask import Flask, request
import sqlite3
from utils import generate_session_id
import Recommender
from db import user_model_mg,wish_list_mg,ratings_collection


app = Flask(__name__)
# In production, all the secret keys should be read from environment variables
app.secret_key = 'hades'
session = {}

recommender = Recommender.OnlineRecommender()
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
    session_id = request.headers.get('Authorization')
    if session_id in session:
        session.pop(session_id)
        return {'message': 'Logged out successfully.'}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/get_model', methods=['GET'])
def get_model():
    session_id = request.headers.get('Authorization')
    if session_id in session:
        username = session[session_id]
        u = user_model_mg.find_one({'username': username})
        return {'message': 'Model retrieved successfully.', 'data': u['model'] if u else ""}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/update_model', methods=['POST'])
def update_model():
    session_id = request.headers.get('Authorization')
    if session_id in session:
        username = session[session_id]
        new_model = request.json['model']
        user_model_mg.update_one({'username': username}, {'$set': {'model': new_model}}, upsert=True)
        return {'message': 'Model updated successfully.'}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/get_wishlist', methods=['GET'])
def get_wishlist():
    session_id = request.headers.get('Authorization')
    if session_id in session:
        username = session[session_id]
        wish_list = wish_list_mg.find_one({'username': username})
        return {'message': 'wishlist retrieved successfully.', 'data': wish_list['wish_list'] if wish_list else ""}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/update_wish_list', methods=['POST'])
def add_to_wishlist():
    session_id = request.headers.get('Authorization')
    if session_id in session:
        username = session[session_id]
        wish_list = request.json['wish_list']
        wish_list_mg.update_one({'username': username}, {'$set': {'wish_list': wish_list}}, upsert=True)
        return {'message': 'wish_list updated successfully.'}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/rate', methods=['POST'])
def rate():
    session_id = request.headers.get('Authorization')
    if session_id in session:
        username = session[session_id]
        item_id = request.json['item_id']
        rating = request.json['rating']
        item_type = request.json['type']
        # print(f'Recorde rating for {username} on item {item_id} with rating {rating} and type {item_type}')
        if item_type not in ['m', 't', 'g']:
            return {'message': 'Invalid item type.'}

        # check if the user has already rated the item
        existing_rating = ratings_collection.find_one({
            'username': username,
            'item_id': item_id,
            'type': item_type
        })

        if existing_rating:
            # if exists, update the rating
            ratings_collection.update_one(
                {'_id': existing_rating['_id']},
                {'$set': {'rating': rating}}, upsert=True
            )
        else:
            # add new rating record
            ratings_collection.insert_one({
                'username': username,
                'item_id': item_id,
                'rating': rating,
                'type': item_type
            })

        recommender.train(username, item_id, rating, item_type)
        return {'message': 'Rating recorded successfully.'}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/recommend', methods=['GET'])
def recommend():
    session_id = request.headers.get('Authorization')
    item_type = request.args.get('type')
    if item_type not in ['m', 't', 'g']:
        return {'message': 'Invalid item type.'}
    if session_id in session:
        username = session[session_id]

        ratings = list(ratings_collection.find({'username': username, 'type': item_type}))
        rated_items = [x['item_id'] for x in ratings]

        recommendations = recommender.recommend(username, item_type, rated_items)
        return {'message': 'Recommendations generated successfully.', 'data': recommendations}
    else:
        return {'message': 'Invalid session ID.'}


@app.route('/ratings', methods=['GET'])
def get_ratings():
    session_id = request.headers.get('Authorization')
    item_type = request.args.get('type')
    if session_id in session:
        username = session[session_id]
        # print(f'Get ratings for {username} with type {item_type}')
        if item_type in ['m', 't', 'g']:
            # print(f'Get ratings for {username} with type {item_type} now is processing')
            ratings = list(ratings_collection.find({'username': username, 'type': item_type}, {'_id': 0}))
            return {'message': 'Ratings retrieved successfully.', 'data': ratings}
        else:
            return {'message': 'Invalid item type.'}
    else:
        return {'message': 'Invalid session ID.'}


if __name__ == '__main__':
    app.run(debug=True)
