from pymongo.mongo_client import MongoClient
from urllib.parse import quote_plus

user = 'hades'
password = 'hades'
host = '16.171.7.170'
port = 27017
uri = "mongodb://%s:%s@%s:%s" % (
                quote_plus(user), quote_plus(password), host, port)
client = MongoClient(uri)

ratings_collection = client['hades']['ratings']
user_model_mg = client['hades']['user_model']
wish_list_mg = client['hades']['wishlist']
genres_collection = client['hades']['all_genres']
