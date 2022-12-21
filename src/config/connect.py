import psycopg
from psycopg.rows import dict_row
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError 

def connect_elastic() -> Elasticsearch:
    """ Connects to Elastic """

    try:
        es = Elasticsearch('http://localhost:9200')
        es.info()
    except (Exception, ConnectionError) as error:
        print(error)
        es = None

    return es


def connect_postgres() -> psycopg.Connection:
    """ Connects to the Postgres database """

    conn = None
    try:
        # print('Connecting to the PostgreSQL database...')
        conn = psycopg.connect(
            host='127.0.0.1',
            dbname='pdt',
            user='mac',
            password='',
            row_factory=dict_row
        )

    except (Exception, psycopg.DatabaseError) as error:
        print(error)

    return conn
    

if __name__ == '__main__':
    connect_postgres()
    connect_elastic()