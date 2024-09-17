from dremio_simple_query.connect import get_token, DremioConnection
from loguru import logger
from dotenv import load_dotenv
from os import getenv

import redis
import json
import pandas as pd

def db_connect():
    """Returns a connection with Dremio Datalake"""

    # Login url endpoint
    login_endpoint = f"http://{getenv('DREMIO_HOSTNAME')}:{getenv('DREMIO_PORT')}/apiv2/login"

    # Payload for Login
    payload = {
        "userName": getenv("DREMIO_AUTH_USERNAME"),
        "password": getenv("DREMIO_AUTH_PASSWORD")
    }

    # Get token from API
    token = get_token(uri = login_endpoint, payload=payload)

    # URL Dremio Software Flight Endpoint
    arrow_endpoint=f"grpc://{getenv('DREMIO_HOSTNAME')}:32010"

    # Establish Client
    connection = DremioConnection(token, arrow_endpoint)

    return connection


def load_decs_in_redis(db_client, redis_client):
    """
    Load descriptors and qualifiers from Thesaurus database into Redis cache database.
    Thesaurus tables are used: thesaurus_descriptor_decs_active and thesaurus_qualifier_decs_active
    """

    decs_tables = ['thesaurus_descriptor_decs_active', 'thesaurus_qualifier_decs_active']

    for decs_table in decs_tables:
        logger.info(f"Loading table {decs_table}")

        # SQL query to execute
        sql_query = f"SELECT decs_code, label FROM DECS.intermediate.{decs_table}"

        df = db_client.toPandas(sql_query)

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
    # Connnect to DeCS database
    try:
        db_client = db_connect()
    except Exception as e:
        logger.error(f"Error connecting to Dabase: {e}")

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

