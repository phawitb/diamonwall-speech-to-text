from pymongo import MongoClient
from datetime import datetime

def get_ngrok_tunnel_url():
    uri = "mongodb+srv://phawitboo:JO3hoCXWCSXECrGB@cluster0.fvc5db5.mongodb.net/?retryWrites=true&w=majority"
    client = MongoClient(uri)

    db = client["my_database"]
    collection = db["ngrok_tunnels"]

    return collection.find_one({})['ngrok_url']


z = get_ngrok_tunnel_url()
print("Current ngrok URL:", z)



