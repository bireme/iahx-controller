from pymongo import MongoClient
from loguru import logger
from dotenv import load_dotenv
from os import getenv

import redis
import json
import pandas as pd

def db_connect():
    """Returns a connection with MongoDB database"""

    # Build MongoDB connection string
    mongodb_host = getenv('MONGODB_HOST')
    mongodb_port = getenv('MONGODB_PORT')
    mongodb_username = getenv('MONGODB_USERNAME')
    mongodb_password = getenv('MONGODB_PASSWORD')
    mongodb_database = getenv('MONGODB_DATABASE')

    # Build connection URI
    if mongodb_username and mongodb_password:
        connection_uri = f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_host}:{mongodb_port}/{mongodb_database}"
    else:
        connection_uri = f"mongodb://{mongodb_host}:{mongodb_port}/{mongodb_database}"

    # Establish MongoDB client connection
    client = MongoClient(connection_uri)

    # Return the database object
    database = client[mongodb_database]

    return database


def load_decs_in_redis(db_client, redis_client):
    """
    Load descriptors and qualifiers from MongoDB database into Redis cache database.
    MongoDB collections are used based on the MONGODB_COLLECTION environment variable
    """

    # Get collection name from environment variable
    mongodb_collection = getenv('MONGODB_COLLECTION')

    if not mongodb_collection:
        logger.error("MONGODB_COLLECTION environment variable not set")
        return

    decs_collections = [f"{mongodb_collection}_descriptor_decs_active", f"{mongodb_collection}_qualifier_decs_active"]

    for decs_collection in decs_collections:
        logger.info(f"Loading collection {decs_collection}")

        # Get collection from MongoDB
        collection = db_client[decs_collection]

        # Query documents with required fields
        cursor = collection.find({"decs_code": {"$exists": True}, "label": {"$exists": True}},
                               {"decs_code": 1, "label": 1, "_id": 0})

        # Convert cursor to DataFrame
        documents = list(cursor)
        df = pd.DataFrame(documents)

        # For each row in the DataFrame, store it in Redis
        for _, row in df.iterrows():
            id_value = row['decs_code']
            label = row['label']

            # Convert label string to a Python list (JSON object)
            json_label = json.loads(label)

            if json_label:
                dic_label = dict()
                for lang in json_label:
                    label_lang = lang['@language']
                    label_text = lang['@value']
                    dic_label[label_lang] = label_text

                # Using HSET to create a row in Redis with the ID as the key
                redis_client.hset(f"decs:{id_value}", mapping=dic_label)

                logger.info(f"Descriptor ID: {id_value} loaded in Redis")

    # Tell the Redis server to save its data to disk, blocking until the save is complete
    redis_client.save()
    logger.info("Data saved in Redis")
    redis_client.quit()


if __name__ == "__main__":

    # Load environment variables
    load_dotenv()

    db_client = redis_client = None
    # Connect to MongoDB database
    try:
        db_client = db_connect()
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")

    # Connect to Cache Database (Redis)
    try:
        redis_client = redis.Redis(host=getenv('REDIS_SERVER'), port=getenv('REDIS_PORT'), db=0)
        redis_client.ping()
    except Exception as e:
        logger.error(f"Error connecting to Redis: {e}")

    if db_client and redis_client:
        logger.info("Connected to databases. Process load DeCS")

        # Load descriptors as keys in cache database
        load_decs_in_redis(db_client, redis_client)

