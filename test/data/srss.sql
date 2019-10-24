create type vote as enum ('up', 'down')
;

create table citations
(
	citing_pmid integer not null,
	cited_pmid integer not null,
	constraint citations_pkey
		primary key (citing_pmid, cited_pmid)
)
;

create table systematic_reviews
(
	review_id integer not null
		constraint systematic_reviews_pkey
			primary key,
	included_complete boolean default false,
	title text,
	source text,
	authors text,
	abstract text,
	doi varchar(255),
	verified_review boolean,
	date_added timestamp default now() not null,
	publish_date integer,
    publish_date_full timestamp
)
;

create table tregistry_entries
(
	nct_id char(11) not null
		constraint tregistry_entries_pkey
			primary key,
	retrieval_timestamp timestamp DEFAULT now(),
	brief_title text,
	overall_status varchar(255),
	official_title text,
	brief_summary text,
	detailed_description text,
	condition text,
	study_type text,
	enrollment integer,
	completion_date varchar(20)
)
;

create table users
(
	user_name varchar(60) not null,
	salt varchar(36),
	salted_password varchar(100),
	user_type varchar(8),
	nickname varchar(20),
	id serial not null
		constraint users_pkey
			primary key
)
;

create table review_rtrial
(
	review_id integer not null
		constraint review_rtrial_review_id_fkey
			references systematic_reviews,
	nct_id char(11) not null
		constraint review_rtrial_nct_id_fkey
			references tregistry_entries,
	confidence_score integer,
	upvotes integer,
	downvotes integer,
	verified boolean,
	relationship varchar(8),
	nickname varchar(20),
	id serial not null
		constraint review_rtrial_pkey
			primary key,
	user_id integer
		constraint review_rtrial_users_id_fk
			references users,
	constraint review_rtrial_review_id_nct_id_key
		unique (review_id, nct_id)
)
;

create table trial_publications
(
	trialpub_id integer not null
		constraint trial_publications_pkey
			primary key,
	title text,
	source text,
	authors text,
	abstract text,
	doi varchar(255),
	user_id integer
		constraint trial_publications_users_id_fk
			references users,
	publish_date integer
)
;

create table review_trialpubs
(
	review_id integer not null
		constraint review_trialpubs_review_id_fkey
			references systematic_reviews,
	trialpub_id integer not null
		constraint review_trialpubs_trialpub_id_fkey
			references trial_publications,
	user_id integer
		constraint review_trialpubs_users_id_fk
			references users,
	constraint review_trialpubs_pkey
		primary key (review_id, trialpub_id)
)
;

create table trialpubs_rtrial
(
	trialpub_id integer not null
		constraint trialpubs_rtrial_trial_publications_trialpub_id_fk
			references trial_publications,
	nct_id char(11) not null
		constraint trialpubs_rtrial_nct_id_fkey
			references tregistry_entries,
	user_id integer
		constraint trialpubs_rtrial_users_id_fk
			references users,
	constraint trialpubs_rtrial_pkey
		primary key (trialpub_id, nct_id)
)
;

create unique index users_nickname_uindex
	on users (nickname)
;

create unique index users_user_name_uindex
	on users (user_name)
;

create table votes
(
	vote_id serial not null
		constraint votes_pkey
			primary key,
	link_id serial not null
		constraint votes_review_rtrial_id_fk
			references review_rtrial,
	vote_type vote,
	timestamp timestamp with time zone default now(),
	user_id integer
		constraint votes_users_id_fk
			references users,
	constraint votes_link_id_user_id_key
		unique (link_id, user_id)
)
;

create table ct_categories
(
	category varchar(255) not null
		constraint ct_categories_category_pk
			primary key,
	code varchar(20),
	id serial not null
)
;

create unique index ct_categories_category_uindex
	on ct_categories (category)
;

create unique index ct_categories_id_uindex
	on ct_categories (id)
;

create table ct_conditions
(
	condition varchar(255) not null
		constraint ct_conditions_condition_pk
			primary key,
	id serial not null,
	original boolean
)
;

create unique index ct_conditions_id_uindex
	on ct_conditions (id)
;

create table category_condition
(
	category_id integer,
	condition_id integer
)
;

create table trial_conditions
(
	nct_id char(11)
		constraint trial_conditions_tregistry_entries_nct_id_fk
			references tregistry_entries,
	condition_id integer
		constraint trial_conditions_ct_conditions_id_fk
			references ct_conditions (id),
	mesh_term boolean,
	constraint trial_conditions_nct_id_condition_id_pk
		unique (nct_id, condition_id)
)
;

create function add_vote() returns trigger
	language plpgsql
as $$
BEGIN
    insert into votes(link_id, vote_type, user_id) VALUES (NEW.id, 'up', NEW.user_id);
    RETURN NEW;
   END;
$$
;

create trigger add_vote
	after insert
	on review_rtrial
	for each row
	execute procedure add_vote()
;

create function change_vote() returns trigger
	language plpgsql
as $$
BEGIN
     IF NEW.vote_type = 'up' THEN
        UPDATE review_rtrial set upvotes = upvotes+1 where id = NEW.link_id;
        UPDATE review_rtrial set downvotes = downvotes-1 where id = NEW.link_id;
      ELSE
        UPDATE review_rtrial set upvotes = upvotes-1 where id = NEW.link_id;
        UPDATE review_rtrial set downvotes = downvotes+1 where id = NEW.link_id;
     END IF;
    RETURN NEW;
   END;
$$
;

create trigger vote_change
	after update
	on votes
	for each row
	execute procedure change_vote()
;

create function remove_trial() returns trigger
	language plpgsql
as $$
BEGIN
    DELETE from review_rtrial where upvotes = 0 and downvotes = 0;
   END;
$$
;

create function remove_vote() returns trigger
	language plpgsql
as $$
BEGIN
     IF OLD.vote_type = 'down' THEN
        UPDATE review_rtrial set downvotes = downvotes-1 where id = OLD.link_id;
      ELSE
        UPDATE review_rtrial set upvotes = upvotes-1 where id = OLD.link_id;
     END IF;
    RETURN OLD;
   END;
$$
;

create trigger remove_vote
	after delete
	on votes
	for each row
	execute procedure remove_vote()
;

create function update_votes() returns trigger
	language plpgsql
as $$
BEGIN
     IF NEW.vote_type = 'up' THEN
        UPDATE review_rtrial set upvotes = upvotes+1 where id = NEW.link_id;
      ELSE
        UPDATE review_rtrial set downvotes = downvotes+1 where id = NEW.link_id;
     END IF;
    RETURN NEW;
   END;
$$
;

create trigger vote_counts
	after insert
	on votes
	for each row
	execute procedure update_votes()
;
INSERT INTO users(user_name, salt, salted_password, user_type, nickname,id)  VALUES ('admin@admin.com', 'b27315059583471db9739708a479f8cb','f1a6f062d3a695abe9beb5de652ffa3d5744c01301c9eedfcb167934f18aa66a','admin','admin',1);
INSERT INTO users(user_name, user_type, nickname,id)  VALUES ('crossrefbot','standard','crossrefbot',9);
INSERT INTO users(user_name, user_type, nickname,id)  VALUES ('basicbot1','standard','basicbot1',3);
INSERT INTO users(user_name, user_type, nickname,id)  VALUES ('basicbot2','standard','basicbot2',10);
INSERT INTO users(user_name, user_type, nickname,id)  VALUES ('matfacbot','standard','matfacbot',11);
INSERT INTO users(user_name, user_type, nickname,id)  VALUES ('cochranebot','standard','cochranebot',17);
