from config.connect import connect_postgres, connect_elastic
import psycopg
from elasticsearch import Elasticsearch
import json
import os

INDEX_NAME = 'tweets'

def create_index(es: Elasticsearch) -> None:
    """ Creates new Elelastic index or deletes the old one """

    exists = es.indices.exists(index=INDEX_NAME)
    if exists: 
        print(f'Index {INDEX_NAME} already exists')
        c = input('Do you want to replace the old one? (y/n): ')
        if c != 'y': return
        
        a = es.indices.delete(index=INDEX_NAME)
        if a['acknowledged']: print('Deleted the old index')
        else: print('Something went wrong :(')

    with open('src/settings.json', 'r') as s, open('src/mapping.json', 'r') as m:
        settings = json.load(s)
        mapping = json.load(m)

    es.indices.create(
        index=INDEX_NAME,
        settings=settings,
        mappings=mapping
    )

    print(f'Created new index {INDEX_NAME}')


def fetch_data(conn: psycopg.Connection) -> list[dict]:
    pass


def import_data(conn: psycopg.Connection, es: Elasticsearch) -> None:
    with conn.cursor(name='tweets') as cur:
        cur.itersize = 5000
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
        -- WHERE c.id = '1496733334587777024';
        LIMIT 10000;
        """)
        
        data = []
        # while True:
        #     rows = cur.fetchmany(10)
        #     if len(rows) == 0:
        #         break

        #     #print(len(rows))
        #     i = 0
        #     data.clear()
        #     print('|New batch|')
        #     for row in rows:
        #         header = {'index': {'_index': INDEX_NAME, '_id': row.pop('id')}}
        #         data.extend([header, row])
        #         i += 1
        #         print(i)

        i = 0
        for row in cur:
            header = {'index': {'_index': INDEX_NAME, '_id': row.pop('id')}}
            data.extend([header, row])
            i += 1
            if i%5000==0: 
                print(i)
                data.clear()
        
        # print(data)
        # a = es.bulk(index=INDEX_NAME, operations=data)
        # if a['errors']: 
        #     print(a['items'])
        # else: 
        #     print(f'Succesfully inserted: {len(rows)}')

        # rows[0]['created_at'] = str(rows[0]['created_at'])
        # print(json.dumps(rows[0]))


def main() -> None:
    conn = connect_postgres()
    if conn == None:
        print('Connection to the database failed :(')
        return
    
    # es = connect_elastic()
    # if es == None:
    #     print('Connection to Elastic failed :(')
    #     return
    
    #create_index(es)
    import_data(conn, None)

    conn.close()
    #es.close()


if __name__ == '__main__':
    main()
