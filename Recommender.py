import pandas as pd
from surprise import SVD, KNNBasic
from surprise import Dataset, Reader
from collections import defaultdict
from db import ratings_collection, user_model_mg
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
            genre_weights = {genre['id']: genre['weight'] for genre in user_model['model']['genres'] if
                             genre['type'] == item_type}
        else:
            genre_weights = {}

        items = []
        for genre_id, weight in genre_weights.items():
            page = 1
            while True:
                genre_items = self.get_items_by_genre(item_type, genre_id, page)
                if not genre_items:
                    break
                if item_type == 'g':
                    items.extend([(item['id'], weight, item['rating']) for item in genre_items['results']])
                else:
                    items.extend([(item['id'], weight, item['vote_average']) for item in genre_items['results']])
                page += 1
                if len(items) >= weight * 20:
                    break

        recommendations = []
        for item_id, weight, avg_rating in items:
            if item_id not in rated_items:
                rating = self.predict(username, item_id, item_type)
                score = rating * weight * (avg_rating / 10)  # Adjust the score based on the average rating
                recommendations.append((item_id, score))

        return sorted(recommendations, key=lambda x: x[1], reverse=True)[:n]

