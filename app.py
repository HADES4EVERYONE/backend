import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from utils import generate_session_id
import Recommender
from db import (
    user_model_mg,
    wish_list_mg,
    ratings_collection,
    genres_collection,
    session_collection,
    users_collection,
)
from config import TMDB_API_KEY, RAWG_API_KEY, TMDB_ACCESS_TOKEN
import requests
import random

app = Flask(__name__)
CORS(app)
# In production, all the secret keys should be read from environment variables
app.secret_key = "hades"
session = {}

recommender = Recommender.OnlineRecommender()
# set up the database
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        realname TEXT NOT NULL,
        username TEXT NOT NULL,
        password TEXT NOT NULL
    )
"""
)
conn.commit()


# @app.route('/register', methods=['POST'])
# def register():
#     realname = request.json['realname']
#     username = request.json['username']
#     password = request.json['password']
#     # Check if the username already exists
#     cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
#     user = cursor.fetchone()
#     if user:
#         return {'message': 'User already exists.'}
#     else:
#         # Insert the new user
#         cursor.execute("INSERT INTO users (realname, username, password) VALUES (?, ?, ?)",
#                        (realname, username, password))
#         # login the user
#         new_session_id = generate_session_id()
#         session[new_session_id] = username
#         return {'message': 'User created successfully.',
#                 'data': {'session_id': new_session_id, 'realname': realname, 'username': username}}


@app.route("/register", methods=["POST"])
def register():
    realname = request.json["realname"]
    username = request.json["username"]
    password = request.json["password"]

    # Check if the username already exists
    if users_collection.find_one({"username": username}):
        return (
            jsonify({"message": "User already exists."}),
            409,
        )  # HTTP 409 Conflict for existing resource

    # Insert the new user
    users_collection.insert_one(
        {
            "realname": realname,
            "username": username,
            "password": password,  # Note: In production, ensure password is hashed
        }
    )

    # Login the user by creating a session
    new_session_id = generate_session_id()
    session_collection.insert_one({"_id": new_session_id, "username": username})

    return jsonify(
        {
            "message": "User created successfully.",
            "data": {
                "session_id": new_session_id,
                "realname": realname,
                "username": username,
            },
        }
    )


# @app.route('/login', methods=['POST'])
# def login():
#     username = request.json['username']
#     password = request.json['password']
#     # Check if the username and password are correct
#     cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
#     user = cursor.fetchone()
#     if user:
#         new_session_id = generate_session_id()
#         session[new_session_id] = username
#         return {'message': 'Login successful.', 'data':
#             {'session_id': new_session_id, 'username': username, 'realname': user[1]}}
#     else:
#         return {'message': 'Incorrect username or password.'}


@app.route("/login", methods=["POST"])
def login():
    username = request.json["username"]
    password = request.json["password"]

    # Check if the username and password are correct
    user = users_collection.find_one({"username": username, "password": password})

    if user:
        new_session_id = generate_session_id()
        session_collection.insert_one({"_id": new_session_id, "username": username})

        return jsonify(
            {
                "message": "Login successful.",
                "data": {
                    "session_id": new_session_id,
                    "username": username,
                    "realname": user[
                        "realname"
                    ],  # Retrieve realname from the MongoDB document
                },
            }
        )
    else:
        return jsonify({"message": "Incorrect username or password."}), 401


# @app.route('/logout', methods=['POST'])
# def logout():
#     session_id = request.headers.get('Authorization')
#     if session_id in session:
#         session.pop(session_id)
#         return {'message': 'Logged out successfully.'}
#     else:
#         return jsonify({'message': 'Invalid session ID.'}), 401


@app.route("/logout", methods=["POST"])
def logout():
    session_id = request.headers.get("Authorization")
    if session_id:
        session_collection.delete_one({"_id": session_id})
        return {"message": "Logged out successfully."}
    else:
        return jsonify({"message": "Invalid session ID."}), 401


@app.route("/get_model", methods=["GET"])
def get_model():
    session_id = request.headers.get("Authorization")
    session_doc = session_collection.find_one({"_id": session_id})
    if session_doc:
        username = session_doc["username"]
        u = user_model_mg.find_one({"username": username})
        return {
            "message": "Model retrieved successfully.",
            "data": u["model"] if u else "",
        }
    else:
        return jsonify({"message": "Invalid session ID."}), 401


@app.route("/update_model", methods=["POST"])
def update_model():
    session_id = request.headers.get("Authorization")
    session_doc = session_collection.find_one({"_id": session_id})
    if session_doc:
        username = session_doc["username"]
        new_model = request.json["model"]
        user_model_mg.update_one(
            {"username": username}, {"$set": {"model": new_model}}, upsert=True
        )
        return {"message": "Model updated successfully."}
    else:
        return jsonify({"message": "Invalid session ID."}), 401


# @app.route('/get_wishlist', methods=['GET'])
# def get_wishlist():
#     session_id = request.headers.get('Authorization')
#     if session_id in session:
#         username = session[session_id]
#         wish_list = wish_list_mg.find_one({'username': username})
#         return {'message': 'wishlist retrieved successfully.', 'data': wish_list['wish_list'] if wish_list else ""}
#     else:
#         return jsonify({'message': 'Invalid session ID.'}), 401


# @app.route('/update_wish_list', methods=['POST'])
# def add_to_wishlist():
#     session_id = request.headers.get('Authorization')
#     if session_id in session:
#         username = session[session_id]
#         wish_list = request.json['wish_list']
#         wish_list_mg.update_one({'username': username}, {'$set': {'wish_list': wish_list}}, upsert=True)
#         return {'message': 'wish_list updated successfully.'}
#     else:
#         return jsonify({'message': 'Invalid session ID.'}), 401


@app.route("/add_to_wishlist", methods=["POST"])
def add_to_wishlist():
    session_id = request.headers.get("Authorization")
    session_doc = session_collection.find_one({"_id": session_id})
    if session_doc:
        username = session_doc["username"]
        item_id = request.json["item_id"]
        item_type = request.json.get("type")  # Default type can be set as 'general'

        if item_type not in ["m", "t", "g"]:
            return jsonify({"message": "Invalid item type."}), 400

        # Check if the item already exists in the wishlist to prevent duplicates
        existing_item = wish_list_mg.find_one(
            {"username": username, "item_id": item_id, "type": item_type}
        )

        if existing_item:
            return jsonify({"message": "Item already exists in the wishlist."}), 409

        # Add new wishlist item if it doesn't exist
        wish_list_mg.insert_one(
            {"username": username, "item_id": item_id, "type": item_type}
        )

        return jsonify({"message": "wishlist updated successfully."})
    else:
        return jsonify({"message": "Invalid session ID."}), 401


@app.route("/remove_from_wishlist", methods=["DELETE"])
def remove_from_wishlist():
    session_id = request.headers.get("Authorization")
    session_doc = session_collection.find_one({"_id": session_id})
    if session_doc:
        username = session_doc["username"]
        item_id = request.args.get("item_id")
        item_type = request.args.get("type")

        if item_type not in ["m", "t", "g"]:
            return jsonify({"message": "Invalid item type."}), 400

        result = wish_list_mg.delete_one(
            {"username": username, "item_id": item_id, "type": item_type}
        )
        if result.deleted_count > 0:
            return jsonify({"message": "Item removed successfully."})
        else:
            return jsonify({"message": "Item not found in wishlist."}), 404
    else:
        return jsonify({"message": "Invalid session ID."}), 401


@app.route("/check_wishlist", methods=["POST"])
def check_wishlist():
    session_id = request.headers.get("Authorization")
    session_doc = session_collection.find_one({"_id": session_id})
    if session_doc:
        username = session_doc["username"]
        item_id = request.json["item_id"]
        item_type = request.json.get("type")

        if item_type not in [
            "m",
            "t",
            "g",
        ]:  # Assuming 'm', 't', 'g' stand for movie, tv-show, game respectively.
            return jsonify({"message": "Invalid item type."}), 400

        # Check if the item exists in the wishlist
        exists = (
            wish_list_mg.find_one(
                {"username": username, "item_id": item_id, "type": item_type}
            )
            is not None
        )
        return jsonify({"message": "Check completed.", "in_wishlist": exists})
    else:
        return jsonify({"message": "Invalid session ID."}), 401


@app.route("/get_wishlist", methods=["GET"])
def get_wishlist():
    session_id = request.headers.get("Authorization")
    session_doc = session_collection.find_one({"_id": session_id})
    if session_doc:
        username = session_doc["username"]
        # Retrieve all wishlist items for this user
        wish_list_cursor = wish_list_mg.find({"username": username})
        all_wish_list_items = [
            {"item_id": item["item_id"], "type": item.get("type", "general")}
            for item in wish_list_cursor
        ]
        return jsonify(
            {"message": "Wishlist retrieved successfully.", "data": all_wish_list_items}
        )
    else:
        return jsonify({"message": "Invalid session ID."}), 401


@app.route("/rate", methods=["POST"])
def rate():
    session_id = request.headers.get("Authorization")
    session_doc = session_collection.find_one({"_id": session_id})
    if session_doc:
        username = session_doc["username"]
        item_id = request.json["item_id"]
        rating = request.json["rating"]
        item_type = request.json["type"]
        # print(f'Recorde rating for {username} on item {item_id} with rating {rating} and type {item_type}')
        if item_type not in ["m", "t", "g"]:
            return jsonify({"message": "Invalid item type."}), 400

        # check if the user has already rated the item
        existing_rating = ratings_collection.find_one(
            {"username": username, "item_id": item_id, "type": item_type}
        )

        if existing_rating:
            # if exists, update the rating
            ratings_collection.update_one(
                {"_id": existing_rating["_id"]},
                {"$set": {"rating": rating}},
                upsert=True,
            )
        else:
            # add new rating record
            ratings_collection.insert_one(
                {
                    "username": username,
                    "item_id": item_id,
                    "rating": rating,
                    "type": item_type,
                }
            )

        return {"message": "Rating recorded successfully."}
    else:
        return jsonify({"message": "Invalid session ID."}), 401


@app.route("/recommend", methods=["GET"])
def recommend():
    session_id = request.headers.get("Authorization")
    session_doc = session_collection.find_one({"_id": session_id})
    item_type = request.args.get("type")
    num_re = int(
        request.args.get("num_re", 10)
    )  # Default to 10 recommendations if not specified
    if item_type not in ["m", "t", "g"]:
        return jsonify({"message": "Invalid item type."}), 400
    if session_doc:
        username = session_doc["username"]

        ratings = list(
            ratings_collection.find({"username": username, "type": item_type})
        )
        rated_items = [x["item_id"] for x in ratings]

        recommendations = recommender.recommend(
            username, item_type, rated_items, n=num_re
        )
        return {
            "message": f"{num_re} recommendations for {item_type} generated successfully.",
            "data": recommendations,
        }
    else:
        return jsonify({"message": "Invalid session ID."}), 401


@app.route("/ratings", methods=["GET"])
def get_ratings():
    session_id = request.headers.get("Authorization")
    item_type = request.args.get("type")
    session_doc = session_collection.find_one({"_id": session_id})
    if session_doc:
        username = session_doc["username"]
        # print(f'Get ratings for {username} with type {item_type}')
        if item_type in ["m", "t", "g"]:
            # print(f'Get ratings for {username} with type {item_type} now is processing')
            ratings = list(
                ratings_collection.find(
                    {"username": username, "type": item_type}, {"_id": 0}
                )
            )
            return {"message": "Ratings retrieved successfully.", "data": ratings}
        else:
            return jsonify({"message": "Invalid item type."}), 400
    else:
        return jsonify({"message": "Invalid session ID."}), 401


@app.route("/import_genres", methods=["GET"])
def import_genres():
    headers = {
        "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}",
        "accept": "application/json",
    }

    # Import TMDB movie genres
    tmdb_movie_url = "https://api.themoviedb.org/3/genre/movie/list?language=en"
    tmdb_movie_response = requests.get(tmdb_movie_url, headers=headers).json()
    tmdb_movie_genres = tmdb_movie_response.get("genres", [])
    for genre in tmdb_movie_genres:
        genre_document = {
            "external_id": genre["id"],
            "name": genre["name"],
            "type": "m",  # 'm' for movies
            "source": "TMDB",
        }
        genres_collection.update_one(
            {"external_id": genre["id"], "type": "m", "source": "TMDB"},
            {"$set": genre_document},
            upsert=True,
        )

    # Import TMDB TV genres
    tmdb_tv_url = "https://api.themoviedb.org/3/genre/tv/list?language=en"
    tmdb_tv_response = requests.get(tmdb_tv_url, headers=headers).json()
    tmdb_tv_genres = tmdb_tv_response.get("genres", [])
    for genre in tmdb_tv_genres:
        genre_document = {
            "external_id": genre["id"],
            "name": genre["name"],
            "type": "t",  # 't' for TV shows
            "source": "TMDB",
        }
        genres_collection.update_one(
            {"external_id": genre["id"], "type": "t", "source": "TMDB"},
            {"$set": genre_document},
            upsert=True,
        )

    # Import RAWG genres
    rawg_url = f"https://api.rawg.io/api/genres?key={RAWG_API_KEY}"
    rawg_response = requests.get(rawg_url).json()
    rawg_genres = rawg_response.get("results", [])
    for genre in rawg_genres:
        genre_document = {
            "external_id": genre["id"],
            "name": genre["name"],
            "type": "g",  # 'g' for games
            "source": "RAWG",
        }
        genres_collection.update_one(
            {"external_id": genre["id"], "type": "g", "source": "RAWG"},
            {"$set": genre_document},
            upsert=True,
        )

    return {"message": "Genres imported successfully."}


@app.route("/get_genres_by_type", methods=["GET"])
def get_genres_by_type():
    genre_type = request.args.get("type")

    if not genre_type:
        return jsonify({"error": "Missing type parameter"}), 400

    query_result = genres_collection.find({"type": genre_type}, {"_id": 0})

    genres = list(query_result)

    if genres:
        return jsonify({"genres": genres})
    else:
        return jsonify({"error": "No genres found for the given type"}), 404


@app.route("/get_genre_id", methods=["GET"])
def get_genre_id():
    # Get genre ID by name and type
    genre_name = request.args.get("name")
    genre_type = request.args.get("type")

    # Make sure the name and type parameters are provided
    if not genre_name or not genre_type:
        return jsonify({"error": "Missing name or type parameter"}), 400

    regex_pattern = re.compile(".*" + re.escape(genre_name) + ".*", re.IGNORECASE)

    # Look up the genre in the database
    query_result = genres_collection.find(
        {"name": regex_pattern, "type": genre_type}, {"_id": 0, "external_id": 1}
    )

    # Extract the genre IDs
    genre_ids = [genre["external_id"] for genre in query_result]

    if genre_ids:
        return jsonify({"genre_ids": genre_ids})
    else:
        return jsonify({"error": "Genre not found"}), 404


@app.route("/random_rate", methods=["POST"])
def random_rate():
    session_id = request.headers.get("Authorization")
    session_doc = session_collection.find_one({"_id": session_id})

    if not session_doc:
        return jsonify({"message": "Invalid session ID."}), 401

    # Get the number of ratings to generate from the request, default to 10 if not specified
    num_ratings = request.json.get("num_ratings", 10)

    username = session_doc["username"]

    item_types = [
        "m",
        "t",
        "g",
    ]  # Assume these are your item types: movies, TV shows, and games

    for _ in range(num_ratings):
        item_type = random.choice(item_types)
        item_id = get_random_item_id(item_type)
        if item_id is None:
            continue  # Skip if no item was found

        rating = random.randint(
            1, 5
        )  # Generate a random rating between 1 and 5 (adjusted from 1-10)

        # Check if the user has already rated the item
        existing_rating = ratings_collection.find_one(
            {"username": username, "item_id": item_id, "type": item_type}
        )

        if existing_rating:
            # Update the rating if it already exists
            ratings_collection.update_one(
                {"_id": existing_rating["_id"]}, {"$set": {"rating": rating}}
            )
        else:
            # Add a new rating record if it doesn't exist
            ratings_collection.insert_one(
                {
                    "username": username,
                    "item_id": item_id,
                    "rating": rating,
                    "type": item_type,
                }
            )

    return {"message": f"{num_ratings} random ratings generated successfully."}


def get_random_item_id(item_type):
    max_retries = 5  # Maximum number of attempts to find a non-empty page
    attempts = 0

    while attempts < max_retries:
        page = random.randint(1, 500)  # Random page number between 1 and 500

        if item_type == "m":  # Movies
            url = "https://api.themoviedb.org/3/discover/movie"
            params = {
                "include_adult": "false",
                "include_video": "false",
                "language": "en-US",
                "sort_by": "popularity.desc",
                "page": page,
                "api_key": TMDB_API_KEY,
            }
        elif item_type == "t":  # TV Shows
            url = "https://api.themoviedb.org/3/discover/tv"
            params = {
                "include_adult": "false",
                "language": "en-US",
                "sort_by": "popularity.desc",
                "page": page,
                "api_key": TMDB_API_KEY,
            }
        elif item_type == "g":  # Games
            url = "https://api.rawg.io/api/games"
            params = {"page": page, "key": RAWG_API_KEY}
        else:
            return None  # Invalid item type

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            items = data["results"]
            if items:
                return random.choice(items)["id"]  # Successfully found a non-empty page
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            # Continue to the next attempt if the API call fails or the page is empty

        attempts += 1  # Increment the attempt counter

    return None  # Return None if all retries are exhausted without success


if __name__ == "__main__":
    app.run(debug=True)
