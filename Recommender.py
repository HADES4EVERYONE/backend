# Recommender.py
import pandas as pd
from surprise import SVD, KNNBasic
from surprise import Dataset, Reader
from collections import defaultdict
from db import ratings_collection

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

    def train(self, username, item_id, rating, item_type):
        ratings = list(ratings_collection.find({'username': username, 'type': item_type}))
        reader = Reader(rating_scale=(1, 5))
        data = Dataset.load_from_df(pd.DataFrame([(x['username'], x['item_id'], x['rating']) for x in ratings] + [(username, item_id, rating)], columns=['user', 'item', 'rating']), reader)
        trainset = data.build_full_trainset()
        self.svd_models[item_type].fit(trainset)
        self.als_models[item_type].fit(trainset)

    def predict(self, username, item_id, item_type):
        return (self.svd_models[item_type].predict(username, item_id).est + self.als_models[item_type].predict(username, item_id).est) / 2

    def recommend(self, username, item_type, rated_items, n=10):
        recommendations = []
        for item_id in range(1, n+1):
            if item_id not in rated_items:
                rating = self.predict(username, item_id, item_type)
                recommendations.append((item_id, rating))
        return sorted(recommendations, key=lambda x: x[1], reverse=True)