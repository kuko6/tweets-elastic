# PDT protokol 5

Jakub Povinec

[https://github.com/kuko6/tweets-elastic](https://github.com/kuko6/tweets-elastic)

----

(tento protokol som písal v markdown-e a teda export do pdf nie je ideálny. Originál je v `docs/protokol.md`)

## Úloha 1

Elasticsearch som spúšťal pomocou dockeru, resp. `docker compose`, kde konfigurácia jednotlivých inštancií/kontajnerov elasticu je obsiahnutá v súbore `docker-compose.yml` . Inštancie elasticu sa dajú spustiť pomocou príkazu `docker compose up` a vypnúť pomocou `docker compose down` alebo postupne, napr. pomocou `docker compose stop [názov kontajnera]`

Stav jednotlivých inštancií sa dá overiť pomocou `GET http://localhost:9200/_cat/nodes?v`

![Snímka obrazovky 2022-12-21 o 22.07.46.png](https://res.craft.do/user/full/c3363b00-79de-4d25-d963-64ad0ea4e431/083EADBD-AC79-422F-98FF-5EED1CADF57B_2/A47BIXWqwxcxRjW5EcOonnThyQ8MQW2bb7q6UJ9vUmcz/Snimka%20obrazovky%202022-12-21%20o%2022.07.46.png)

*Fig. 1 Stav jednotlivých elastic inštancií*

## Úloha 2

Optimálny počet shardov v elasticu záleží na počte nodov, veľkosti indexovaných dát a taktiež dostupných zdrojov (CPU a pamäte). Shardy umožňujú paralelizáciu dopytov s tým, že rozdelia indexované dáta medzi jednotlivé nody. Najideálnejšie je teda, aby bol počet shardov deliteľný počtom nodov, kedy by sa shardy vedeli rovnomerne rozdeliť medzi jednotlivé nody. Podľa tohto článku ([How many shards should I have in my Elasticsearch cluster?](https://www.elastic.co/blog/how-many-shards-should-i-have-in-my-elasticsearch-cluster)), by mal mať shard velkosť okolo 20GB až 40GB. V našom prípade majú dáta zhruba 70-80GB a teda ideálny počet shardov je buď 3 alebo 6. Aj keď je väčší počet shardov efektívnejší z hľadiska rýchlosti dopytov, každý shard si musí uchovávať ešte dodatočné informácie o uložených dátach, kde pri menšom počte shardov môže byť tento "overhead" výrazne menší. Keďže je pri tomto zadaní môj najväčší problém hlavne nedostatok voľného miesta, zvolil som radšej **menší počet shardov 3**.

Repliky zas predstavujú kópie jednotlivých shardov. Repliky sú vždy na inom node ako primárne shardy a slúžia na nahradenie daného shardu v prípade, že vypadne. Ideálne je mať aspoň jednu repliku.

Počet shardov a nodov sa zadáva pri vytváraní indexu pomocou `PUT http://localhost:9200/tweets`

```json
{
	"settings": {
		"index": {
			"number_of_shards": 3,
			"number_of_replicas": 1
		},
}
```

*Fig. 2 Špecifikovanie počtu shardov a replík pri vytváraní indexu*

V našom prípade bolo finálne rozdelenie shardov a replík nasledovné:

![Snímka obrazovky 2022-12-22 o 12.33.29.png](https://res.craft.do/user/full/c3363b00-79de-4d25-d963-64ad0ea4e431/2AC63479-3C96-4453-9130-0B34F2FD777B_2/npnJ611qp3azCSthNynvF5J2zc6OnyulGPeiJnWTPSkz/Snimka%20obrazovky%202022-12-22%20o%2012.33.29.png)

*Fig. 3 Rozdelenie shardov a replík*

## Úloha 3

Táto úloha je rozdelená na viac častí: vytvorenie mappingu a denormalizácia dát z postgres databázy.

### Mapping

Pri vytváraní mappingu som sa snažil zachovať podobnú štruktúru dát a tabuliek ako bola v postgres s tým, že som vynechal stĺpce s id z tabuliek: `context_annotations`, `conversation_hashtags` a `hashtags`, `annotations` a `links` pretože sa nenachádzajú v [twitter dokumentácií pre objekt tweet](https://developer.twitter.com/en/docs/twitter-api/data-dictionary/object-model/tweet) a teda mi prišli zbytočné.

```json
{
    "id": { "type": "long" },
    "content": { "type": "text", "analyzer": "englando" },
    "possibly_sensitive": { "type": "boolean" },
    "language": { "type": "keyword" },
    "source": { "type": "keyword" },
    "retweet_count": { "type": "integer" },
    "reply_count": { "type": "integer" },
    "like_count": { "type": "integer" },
    "quote_count": { "type": "integer" },
    "created_at": { "type": "date", "format": "yyyy-MM-dd'T'HH:mm:ssZZZZZ" }
}
```

*Fig. 4 Mapping pre dáta z tabuľky conversations*

V mapovaní dát pre tabuľku `conversations` som pre pole `content` špecifikoval vlastný analyzér (definovaný v 4. úlohe). Polia `language` a `source` som zaindexoval ako `keyword`, keďže sa zvyčajne jedná len o samotné slová alebo frázy, ktoré nemusia byť analyzované. Taktiež som definoval formát dátumu pre pole `created_at`, ktoré zodpovedá formátu v postgrese.

```json
{
    "author": {
        "properties": {
            "id": { "type": "long" },
            "name": { 
                "type": "text",
                "fields": {
                    "ngram": { "type": "text", "analyzer": "custom_ngram" },
                    "shingles": { "type": "text", "analyzer": "custom_shingles" }
                } 
            },
            "username": { 
                "type": "text",
                "fields": {
                    "ngram": { "type": "text", "analyzer": "custom_ngram" }
                }  
            },
            "description": { 
                "type": "text",
                "analyzer": "englando",
                "fields": {
                    "shingles": { "type": "text", "analyzer": "custom_shingles" }
                }
            },
            "followers_count": { "type": "integer" },
            "following_count": { "type": "integer" },
            "tweet_count": { "type": "integer" },
            "listed_count": { "type": "integer" }
        }
    }
}
```

*Fig. 5 Mapping pre dáta z tabuľky authors*

Informácie o autorovi sú v dokumente uložené ako samostatný objekt `author`. Pre atribúty `name`, `username` a `description` som pridal aj dodatočné mapovanie pre vytvorené analyzéry `custom_ngram` a `custom_shingles`.

```json
{
    "context_annotations": {
        "type": "nested",
        "properties": {
            "entity": {
                "properties": {
                    "id": { "type": "long" },
                    "name": { "type": "keyword" },
                    "description": { "type": "text", "analyzer": "englando" }
                }
            },
            "domain": {
                "properties": {
                    "id": { "type": "long" },
                    "name": { "type": "keyword" },
                    "description": { "type": "text", "analyzer": "englando" }
                }
            }
        }
    }
}
```

*Fig. 6 Mapping pre dáta z tabuľky context_annotations*

Dáta z `context_annotations` sú reprezentované ako pole objektov `entity` a `domain`. Aby sa dalo dopytovať na jednotlivé objekty v poli, je potrebné `context_annotations` indexovať ako `nested`.

```json
{
    "conversation_hashtags": {
        "properties": {
            "tag": { "type": "text", "analyzer":"keyword_lowercase" }
        }
    }
}
```

*Fig. 7 Mapping pre dáta z tabuľky conversation_hashtags*

Hashtagy sú indexované ako pole objektov, ktoré majú atribút tag, reprezentujúci samotný hashtag. `Tag` je indexovaný ako `text` s vlastným analyzátorom, ktorý ich indexuje v lowercase. V tomto prípade netreba špecifikovať typ `nested`, keďže objekty obsahujú len jeden atribút.

```json
{
    "annotations": {
        "type": "nested",
        "properties": {
            "value": { "type": "keyword" },
            "type": { "type": "keyword" },
            "probability": { "type": "half_float" }
        }
    },
    "links": {
        "type": "nested",
        "properties": {
            "url": { "type": "keyword" },
            "title": { "type": "keyword" },
            "description": { "type": "keyword" }
        }
    }
}
```

*Fig. 8 Mapping pre dáta z tabuliek annotations a links*

Mapovanie tabuliek `annotations` a `links` je viacmenej rovnaké, kde obe tabuľky sú reprezentované ako pole objektov. V oboch prípadoch mi prišlo najlepšie indexovať textové polia ako `keyword`.

```json
{
    "conversation_references": {
        "type": "nested",
        "properties": {
            "id": { "type": "long" },
            "type": { "type": "keyword" },
            "author": {
                "properties": {
                    "id": { "type": "long" },
                    "name": { 
                        "type": "text",
                        "fields": {
                            "ngram": { "type": "text", "analyzer": "custom_ngram" },
                            "shingles": { "type": "text", "analyzer": "custom_shingles" }
                        } 
                    },
                    "username": { 
                        "type": "text",
                        "fields": {
                            "ngram": { "type": "text", "analyzer": "custom_ngram" }
                        }
                    }
                }
            },
            "content": { "type": "text", "analyzer": "englando" },
            "hashtags": {
                "properties":{
                    "tag": { "type": "text", "analyzer": "keyword_lowercase" }
                }
            }
        }
    }
}
```

*Fig. 9 Mapping pre dáta z tabuľky conversation_references*

Referencie sú reprezentované ako pole objetkov (tweetov), na ktoré sa odkazujú. Referencované tweety majú vybrané atribúty normálnych tweetov (aj s rovnakými typmi a indexovaním) s tým, že ešte obsahujú typ referencie, ktorý je indexovaný ako `keyword`.

### Denormalizácia

Keďže je pri denormalizácií potrebné joinovať veľké množstvo tabuliek, vytvoril som si pre zrýchlenie danej query dodatočné indexy pre všetky cudzie kľúče.

```sql
CREATE INDEX ca_conversation_id ON context_annotations(conversation_id);
CREATE INDEX ca_domain_id ON context_annotations(context_domain_id);
CREATE INDEX ca_entity_id ON context_annotations(context_entity_id);
CREATE INDEX h_conversation_id ON conversation_hashtags(conversation_id);
CREATE INDEX h_hashtag_id ON conversation_hashtags(hashtag_id);
CREATE INDEX an_conversation_id ON annotations(conversation_id);
CREATE INDEX l_conversation_id ON links(conversation_id);
CREATE INDEX cr_conversation_id ON conversation_references(conversation_id);
CREATE INDEX cr_parent_id ON conversation_references(parent_id);
```

*Fig. x SQL pre vytvorenie indexov pre cudzie kľúče*

Pri denormalizácií dát som postupne joinoval jednotlivé tabuľky s tabuľkou `conversations`. Kvôli lepšej prehladnosti, ako aj následnému importu dát do elasticu som sa rozhodol rovno uložiť dáta z ostatných tabuliek ako json, na čo v postgrese slúžia funkcie `to_json()` a `json_build_object()`.

Tabuľky, ktoré pre daný tweet mohli vrátiť viac riadkov (všetky okrem `authors`) boli kvôli jednoduchšej agregácií výsledkov  ešte "zabalené" v subquery. Na agregáciu som použil funkciu `json_agg()`, ktorá tieto záznamy (json objekty) spojí do listu. Zaujímavou časťou je subquery pre získanie referencií z tabuľky `conversation_references`, kde sa na získanie autora ako aj hashtagov parent tweetu použijú samostatné subquery. Samotné query pre denormalizáciu je na obrázku (Fig. )

```sql
SELECT 
	c.id, c."content", c.possibly_sensitive, c."language", 
	c."source", c.retweet_count, c.reply_count, c.like_count, c.quote_count, c.created_at,
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
) cr ON cr.conversation_id = c.id;
```

*Fig. x SQL pre denormalizovanie tabuľky*

Ďalším krokom by ešte mohlo byť vytvorenie novej tabuľky a tieto získané dáta do nej pridať, čo by následne zrýchlilo samotný import dát do elasticu, keďže by sa jednotlivé riadky len vyberali z databázy. Ja som nemohol urobiť tento krok kvôli nedostatočnému voľnému miestu.

