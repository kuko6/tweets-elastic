CREATE INDEX c_author_id ON conversations(author_id);
CREATE INDEX ca_conversation_id ON context_annotations(conversation_id);
CREATE INDEX ca_domain_id ON context_annotations(context_domain_id);
CREATE INDEX ca_entity_id ON context_annotations(context_entity_id);
CREATE INDEX h_conversation_id ON conversation_hashtags(conversation_id);
CREATE INDEX h_hashtag_id ON conversation_hashtags(hashtag_id);
CREATE INDEX an_conversation_id ON annotations(conversation_id);
CREATE INDEX l_conversation_id ON links(conversation_id);
CREATE INDEX cr_conversation_id ON conversation_references(conversation_id);
CREATE INDEX cr_parent_id ON conversation_references(parent_id);

VACUUM ANALYSE;

SELECT COUNT(*) FROM conversations;

------------------------------------------------------------------------------------

SELECT 
	-- COUNT(*)
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
) cr ON cr.conversation_id = c.id;
--WHERE c.id = '1496733334587777024';
-- LIMIT 1000;
