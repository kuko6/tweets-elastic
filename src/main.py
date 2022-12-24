from config.connect import connect_postgres, connect_elastic
import psycopg
from elasticsearch import Elasticsearch
from elasticsearch.helpers import parallel_bulk
import json
import os
import time


INDEX_NAME = 'tweets'

def create_index(es: Elasticsearch) -> None:
    """ Create new Elelastic index or delete the old one """

    exists = es.indices.exists(index=INDEX_NAME)
    if exists: 
        print(f'Index {INDEX_NAME} already exists')
        c = input('Do you want to replace the old one? (y/n): ')
        if c != 'y': return
        
        a = es.indices.delete(index=INDEX_NAME)
        if a['acknowledged']: print('Deleted the old index')
        else: print('Something went wrong :(')

    with open('src/config/settings.json', 'r') as s, open('src/config/mapping.json', 'r') as m:
        settings = json.load(s)
        mapping = json.load(m)

    es.indices.create(
        index=INDEX_NAME,
        settings=settings,
        mappings=mapping
    )

    print(f'Created new index {INDEX_NAME}')


def query_data(conn: psycopg.Connection, last_id=0, limit=5000) -> psycopg.ServerCursor:
    """ Create server cursor and execute the query with given `limit` and from given `id` """

    cur = conn.cursor(name='tweets')
    #cur.itersize = 10000
    cur.execute("""
    SELECT 
        c.id, c."content", c.possibly_sensitive, c."language", c."source", c.retweet_count, c.reply_count, c.like_count, c.quote_count, c.created_at,
        to_json(a.*) author,
        COALESCE(ca.jsons, '[]') context_annotations,
        COALESCE(ch.jsons, '[]') conversation_hashtags,
        COALESCE(an.jsons, '[]') annotations,
        COALESCE(l.jsons, '[]') links,
        COALESCE(cr.jsons, '[]') conversation_references
    FROM conversations c
    JOIN authors a ON c.author_id = a.id
    LEFT JOIN (
        SELECT ca.conversation_id, json_agg(json_build_object('entity', ce.*, 'domain', cd.*)) jsons
        FROM context_annotations ca
        JOIN context_entities ce ON ca.context_entity_id = ce.id
        JOIN context_domains cd ON ca.context_domain_id = cd.id 
        GROUP BY ca.conversation_id
    ) ca ON ca.conversation_id = c.id
    LEFT JOIN (
        SELECT ch.conversation_id, json_agg(json_build_object('tag', h.tag)) jsons 
        FROM conversation_hashtags ch
        JOIN hashtags h ON ch.hashtag_id = h.id
        GROUP BY ch.conversation_id
    ) ch ON ch.conversation_id = c.id
    LEFT JOIN (
        SELECT an.conversation_id, json_agg(json_build_object('value', an."value", 'probability', an.probability, 'type', an."type")) jsons 
        FROM annotations an
        GROUP BY an.conversation_id
    ) an ON an.conversation_id = c.id
    LEFT JOIN (
        SELECT l.conversation_id, json_agg(json_build_object('url', l.url, 'title', l.title, 'description', l.description)) jsons 
        FROM links l
        GROUP BY l.conversation_id
    ) l ON l.conversation_id = c.id
    LEFT JOIN (
        SELECT 
            cr.conversation_id,
            json_agg(json_build_object(
                'id', p.id, 'type', cr."type", 'content', p."content",
                'author', (
                    SELECT json_build_object('id', pa.id, 'name', pa."name", 'username', pa.username) 
                    FROM authors pa 
                    WHERE pa.id = p.author_id
                ),
                'hashtags', (
                    SELECT json_agg(json_build_object('tag', h.tag)) 
                    FROM conversation_hashtags ch 
                    JOIN hashtags h ON ch.hashtag_id = h.id
                    WHERE ch.conversation_id = p.id
                )
            )) jsons
        FROM conversation_references cr
        JOIN conversations p ON cr.parent_id = p.id
        GROUP BY cr.conversation_id
    ) cr ON cr.conversation_id = c.id
    WHERE c.id > (%s)
    ORDER BY c.id ASC
    LIMIT (%s);
    """, (last_id, limit))
    
    return cur


def import_data(conn: psycopg.Connection, es: Elasticsearch, data_size=-1) -> None:
    """ Bulk import data from postgresql to elastic """

    batch_size = 200 # seems to be the best amount of documents to be inserted at once 
    limit = 8000000 # how many rows will be selected from postgres at once

    total_time = start_time = time.time()
    total_processed_rows = 0
    
    if data_size != -1 and data_size < limit:
        limit = data_size

    last_id = 0 # used as pagination, faster than using offset 
    
    # Since the `conversations` table includes around 32mil rows it is not very effective to select all of them at once.
    # Instead the data is split into multiple groups by the specified limit. 
    # After iterating over the entire group, the new data is selected with a `WHERE` condition that ensures that this batch 
    # includes only the rows that are further in the table then the last imported row from the last group (`last_id`)
    while True: 
        cur = query_data(conn, last_id, limit)

        data = []
        start_time = time.time()
        processed_rows = 0

        # Import data in batches
        while True:
            rows = cur.fetchmany(batch_size)
            if len(rows) == 0:  break

            # Iterate over the batch to create bulk import for elastic
            for row in rows:
                # Each insert has to also include a header, that specifies the action, selected index and id for the document
                header = {'index': {'_index': INDEX_NAME, '_id': row.pop('id')}}
                data.extend([header, row])
                processed_rows += 1

            last_id = header['index']['_id']
            
            # Import the created batch into elastic
            a = es.bulk(index=INDEX_NAME, operations=data)
            if a['errors']: print(a['items'])
            else: print(f'Succesfully inserted: {len(data)/2} documents')

            data.clear()

            if processed_rows%10000 == 0:
                print(f'Execution after {processed_rows} rows: {round(time.time() - start_time, 3)}s')
        
        total_processed_rows += processed_rows
        print(f'Total execution after {total_processed_rows} rows: {round(time.time() - total_time, 3)}s') 

        cur.close()
        print(last_id)

        if processed_rows == 0 or total_processed_rows >= data_size:
            break


def main() -> None:
    conn = connect_postgres()
    if conn == None:
        print('Connection to the database failed :(')
        return

    es = connect_elastic()
    if es == None:
        print('Connection to Elastic failed :(')
        return
    
    create_index(es)
    import_data(conn, es, data_size=-1)
    
    es.close()
    conn.close()


if __name__ == '__main__':
    main()
