from loguru import logger
from dotenv import load_dotenv
from os import getenv

import redis
import json
import pandas as pd
import mysql.connector

def db_connect():
    """Returns a connection with MySQL database"""

    # Establish MySQL connection
    connection = mysql.connector.connect(
        host=getenv('DECS_DATABASE_HOST'),
        port=getenv('DECS_DATABASE_PORT', '3306'),
        user=getenv('DECS_DATABASE_USER'),
        password=getenv('DECS_DATABASE_PASSWORD'),
        database=getenv('DECS_DATABASE_NAME')
    )

    return connection


def load_decs_in_redis(db_client, redis_client):
    """
    Load descriptors and qualifiers from Thesaurus database into Redis cache database.
    Thesaurus tables are used: thesaurus_descriptor and thesaurus_qualifier
    """

    decs_tables = ['thesaurus_descriptor', 'thesaurus_qualifier']

    for decs_table in decs_tables:
        logger.info(f"Loading table {decs_table}")

        # SQL query to execute
        sql_query = f"SELECT decs_code, label FROM {decs_table} AS t WHERE t.thesaurus = 1 and t.active = TRUE"

        df = pd.read_sql(sql_query, db_client)

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
    # Connect to MySQL database
    try:
        db_client = db_connect()
    except Exception as e:
        logger.error(f"Error connecting to MySQL: {e}")

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

