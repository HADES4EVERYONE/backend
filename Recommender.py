import re
import pandas as pd
from surprise import SVD, KNNBasic
from surprise import Dataset, Reader
from collections import defaultdict
from db import ratings_collection, user_model_mg, genres_collection
import requests
from config import TMDB_API_KEY, RAWG_API_KEY, TMDB_ACCESS_TOKEN


class OnlineRecommender:
    def __init__(self):
        self.svd_models = {
            'm': SVD(),
            't': SVD(),
            'g': SVD()
        }
        self.als_models = {
            'm': KNNBasic(sim_options={'user_based': False}),
            't': KNNBasic(sim_options={'user_based': False}),
            'g': KNNBasic(sim_options={'user_based': False})
        }
        self.user_ratings = defaultdict(lambda: defaultdict(list))
        self.is_trained = {
            'm': False,
            't': False,
            'g': False
        }

    def reset_training_flags(self, item_type):
        self.is_trained[item_type] = False

    def get_items_by_genre(self, item_type, genre_id, page=1):
        if item_type == 'm':
            url = f'https://api.themoviedb.org/3/discover/movie?with_genres={genre_id}&page={page}&api_key={TMDB_API_KEY}'
        elif item_type == 't':
            url = f'https://api.themoviedb.org/3/discover/tv?with_genres={genre_id}&page={page}&api_key={TMDB_API_KEY}'
        elif item_type == 'g':
            url = f'https://api.rawg.io/api/games?genres={genre_id}&page={page}&key={RAWG_API_KEY}'

        headers = {}
        if item_type in ['m', 't']:
            headers['Authorization'] = f'Bearer {TMDB_ACCESS_TOKEN}'

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return None

    def train(self, username, item_id, rating, item_type):
        ratings = list(ratings_collection.find({'username': username, 'type': item_type}))
        reader = Reader(rating_scale=(1, 5))
        data = Dataset.load_from_df(pd.DataFrame([(x['username'], x['item_id'], x['rating']) for x in ratings] + [(username, item_id, rating)], columns=['user', 'item', 'rating']), reader)
        trainset = data.build_full_trainset()
        self.svd_models[item_type].fit(trainset)
        self.als_models[item_type].fit(trainset)
        self.is_trained[item_type] = True

    def predict(self, username, item_id, item_type):
        if not self.is_trained[item_type]:
            ratings = list(ratings_collection.find({'type': item_type}))
            if not ratings:
                return 0
            reader = Reader(rating_scale=(1, 5))
            data = Dataset.load_from_df(pd.DataFrame([(x['username'], x['item_id'], x['rating']) for x in ratings], columns=['user', 'item', 'rating']), reader)
            trainset = data.build_full_trainset()
            self.svd_models[item_type].fit(trainset)
            self.als_models[item_type].fit(trainset)
            self.is_trained[item_type] = True

        return (self.svd_models[item_type].predict(username, item_id).est + self.als_models[item_type].predict(username, item_id).est) / 2

    def recommend(self, username, item_type, rated_items, n=10):
        user_model = user_model_mg.find_one({'username': username})
        if user_model and 'genres' in user_model['model']:
            genre_weights = {genre['name']: (genre['weight'], genre['type']) for genre in user_model['model']['genres']}
        else:
            genre_weights = {}

        # Find the top genres in the selected item type (movies)
        selected_type_genres = [(genre_name, weight) for genre_name, (weight, genre_type) in genre_weights.items() if
                                genre_type == item_type]
        selected_type_genres = sorted(selected_type_genres, key=lambda x: x[1], reverse=True)[:3]

        # Find similar genres in other item types and adjust weights
        for genre_name, (weight, genre_type) in genre_weights.items():
            if genre_type != item_type:
                # Split the genre name into individual words
                genre_words = re.findall(r'\w+', genre_name)
                for word in genre_words:
                    similar_genre_ids = self.get_genre_ids(word, item_type)
                    if similar_genre_ids:
                        for i, (selected_genre_name, selected_genre_weight) in enumerate(selected_type_genres):
                            if selected_genre_name in similar_genre_ids:
                                selected_type_genres[i] = (selected_genre_name, selected_genre_weight + weight)
                                break

        items = []
        for genre_name, weight in selected_type_genres:
            genre_ids = self.get_genre_ids(genre_name, item_type)
            for genre_id in genre_ids:
                page = 1
                while True:
                    genre_items = self.get_items_by_genre(item_type, genre_id, page)
                    if not genre_items:
                        break
                    if item_type == 'g':
                        items.extend([(item['id'], weight * 1.5, item['rating']) for item in genre_items['results']])
                    else:
                        items.extend(
                            [(item['id'], weight * 1.5, item['vote_average']) for item in genre_items['results']])
                    page += 1
                    if len(items) >= weight * 20:
                        break

        recommendations = []
        for item_id, weight, avg_rating in items:
            if item_id not in rated_items:
                rating = self.predict(username, item_id, item_type)
                score = rating * weight * (avg_rating / 10)
                recommendations.append((item_id, score))

        self.reset_training_flags(item_type)
        return sorted(recommendations, key=lambda x: x[1], reverse=True)[:n]


    def get_genre_ids(self, genre_name, genre_type):
        regex_pattern = re.compile('.*' + re.escape(genre_name) + '.*', re.IGNORECASE)

        query_result = genres_collection.find({
            'name': regex_pattern,
            'type': genre_type
        }, {'_id': 0, 'external_id': 1})

        genre_ids = [genre['external_id'] for genre in query_result]

        # print(f"Fetched genre IDs for {genre_name} of type {genre_type}: {genre_ids}")
        return genre_ids
