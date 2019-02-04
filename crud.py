# -*- coding: utf-8 -*-
import dblib
import untangle
from datetime import datetime
import config
import psycopg2.extras
import httplib
import utils
import request_data
from eutils import Client
from app import cache

eutils_key = config.EUTILS_KEY
eutils_email = config.EUTILS_EMAIL
eutils_tool = config.EUTILS_TOOL


def review_lock_status(review_id):
    """
    return status of review included trials (locked = T or F)
    @param review_id: pmid of review
    @return: boolean
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute(
        "SELECT included_complete FROM systematic_reviews WHERE review_id = %s;",
        (review_id,))
    locked = cur.fetchone()[0]
    conn.close()
    return locked


def get_saved_reviews(user_id):
    """ Retrieve all saved reviews for user """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("SELECT review_id from user_reviews where user_id = %s;", (user_id,))
    res = cur.fetchall()
    if not res:
        return None
    reviews = list(zip(*res)[0])
    return get_reviews_with_ids(reviews)


def save_review(review_id, user_id, bool):
    """
    Add or remove a saved review for user
    @param review_id: PMID of review
    @param user_id: user ID
    @param bool: T to add review, F to remove review
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    if bool:
        cur.execute(
            "INSERT INTO user_reviews(user_id, review_id) VALUES (%s, %s) ON CONFLICT (user_id, review_id) DO NOTHING ;",
            (user_id, review_id))
    else:
        cur.execute("DELETE FROM user_reviews where user_id = %s and review_id = %s;", (user_id, review_id))
    conn.commit()
    conn.close()


def get_locked():
    """
    Get the pubmed IDs of all locked reviews
    @return: list of locked reviews or None
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute(
        "SELECT review_id FROM systematic_reviews WHERE included_complete = TRUE;")
    reviews = cur.fetchall()
    conn.close()
    return list(zip(*reviews)[0]) if reviews else None


def review_publication(review_id, publication_id, user_id):
    """
    create a new record linking the specified review to the specified publication

    @param review_id: pmid of review
    @param publication_id: pmid of trial publication
    @param user_id: id of user submitting this publication
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO review_trialpubs (review_id, trialpub_id, user_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;",
            (review_id, publication_id, user_id))
        conn.commit()
    except psycopg2.IntegrityError as e:
        print e
        conn.rollback()
        ec = Client(api_key=eutils_key)
        article = ec.efetch(db='pubmed', id=publication_id)
        for a in article:
            pubmedarticle_to_db(a, 'trial_publications')
        cur.execute(
            "INSERT INTO review_trialpubs (review_id, trialpub_id, user_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;",
            (review_id, publication_id, user_id))
        conn.commit()
    conn.close()


def review_trial(review_id, nct_id, verified, relationship, nickname, user_id, vote_type='up'):
    """
    create a new record linking the specified review to the specified trial registry entry
    @param review_id: pmid of review
    @param nct_id: nct id of trial registry entry
    @param verified: whether trial is definitely included in review
    @param relationship: included or relevant
    @param nickname: of submitting user
    @param user_id: of submitting user
    """
    existing = check_existing_review_trial(review_id, nct_id)
    lock = review_lock_status(review_id)
    if lock and relationship is 'included':
        if existing:
            vote(existing[0], vote_type, user_id)
        return
    if existing:
        vote(existing[0], vote_type, user_id)
        if existing[1] == 'relevant' and relationship == 'included':
            change_relationship(existing[0], relationship)
        elif existing[1] == 'included' and relationship == 'relevant' and user_id is 17:
            change_relationship(existing[0], relationship)
    else:
        link_review_trial(review_id, nct_id, verified, relationship, nickname, user_id)
        # link_id = get_link_id(nct_id, review_id)
        # vote(link_id, vote_type, user_id)


def link_review_trial(review_id, nct_id, verified, relationship, nickname, user_id):
    """
    create a new link between the specified review & trial
    @param review_id: PMID of review
    @param nct_id: NCTID of trial
    @param verified: T or F
    @param relationship: included or relevant
    @param nickname: of user submitting trial
    @param user_id: of user submitting trisl
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO review_rtrial(review_id, nct_id, verified,  upvotes, downvotes, relationship, nickname, user_id) VALUES (%s, %s, %s, %s,"
            " %s , %s, %s, %s) ON CONFLICT (review_id, nct_id) DO NOTHING;",
            (review_id, nct_id, verified, 0, 0, relationship, nickname, user_id))
        conn.commit()
    except psycopg2.IntegrityError as e:
        print e
        conn.rollback()
        if add_missing_trial(nct_id):
            cur.execute(
                "INSERT INTO review_rtrial(review_id, nct_id, verified,  upvotes, downvotes, relationship, nickname, user_id) VALUES (%s, %s, %s, %s,"
                " %s , %s, %s, %s) ON CONFLICT (review_id, nct_id) DO NOTHING;",
                (review_id, nct_id, verified, 0, 0, relationship, nickname, user_id))
            conn.commit()
    conn.close()


def add_missing_trial(nct_id):
    """ retrieve and insert trial with speficied ID """
    xml = get_trial_xml(nct_id)
    if xml:
        update_record(xml)
        return True
    else:
        return False


def change_relationship(id, relationship):
    """ set relationship of review-trial link with specified ID """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("UPDATE review_rtrial SET relationship = %s WHERE id = %s;", (relationship, id))
    conn.commit()
    conn.close()


def check_existing_review_trial(review_id, nct_id):
    """ check whether there exists a link between the specified review & trial """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, relationship FROM review_rtrial WHERE nct_id = %s AND review_id = %s;", (nct_id, review_id))
    existing = cur.fetchone()
    conn.close()
    return existing if existing else None


def get_link_id(nct_id, review_id):
    """ get the link id of the specified review-trial link """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("SELECT id from review_rtrial where review_id = %s and nct_id = %s;", (review_id, nct_id))
    link_id = cur.fetchone()
    conn.close()
    return link_id[0] if link_id else None


def vote(link_id, vote_type, user_id):
    """
    vote on specified review-trial link
    @param link_id: review-trial link id
    @param vote_type: up or down
    @param user_id: of voting user
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO votes(link_id, vote_type, user_id) VALUES (%s,%s,%s) ON CONFLICT (link_id, user_id) do update set vote_type = %s where (votes.vote_type) is distinct from(EXCLUDED.vote_type);",
        (link_id, vote_type, user_id, vote_type))
    conn.commit()
    conn.close()


def publication_trial(publication_id, nct_id, user_id):
    """
    create a new record linking the specfied publication to the specified trial registry entry
    @param publication_id: pmid of publication
    @param nct_id: nct id of trial registry entry
    @param user_id: of submitting user
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO trialpubs_rtrial (trialpub_id, nct_id, user_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING ;",
            (publication_id, nct_id, user_id))
        conn.commit()
    except psycopg2.IntegrityError as e:
        print e
        conn.rollback()
        add_missing_trial(nct_id)
        cur.execute(
            "INSERT INTO trialpubs_rtrial (trialpub_id, nct_id, user_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING ;",
            (publication_id, nct_id, user_id))
        conn.commit()
    conn.close()


def convert_id(known_id, desired_id):
    """
    convert from PMID to DOI or vice versa
    @param known_id: id we have (pmid/doi)
    @param desired_id: type of id we want (pmid/doi)
    @return: desired id (in pmid/doi form)
    """

    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if desired_id == 'doi':
        try:
            cur.execute("SELECT doi FROM systematic_reviews WHERE review_id = %s;", (known_id,))
        except psycopg2.DataError:
            return None
    elif desired_id == "pmid":
        try:
            cur.execute("SELECT review_id FROM systematic_reviews WHERE doi = %s;", (known_id,))
        except psycopg2.DataError:
            return None
    existing = cur.fetchone()
    conn.close()
    if existing:
        return existing[0]
    else:
        request_data.pubmed_convert_id(known_id, desired_id)


def complete_studies(review_id, value):
    """ set the completeness of the list of trials for the specified review (T or F) """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("UPDATE systematic_reviews SET included_complete = %s WHERE review_id = %s;", (value, review_id))
    cur.execute("UPDATE review_rtrial SET verified = %s WHERE relationship = "
                " 'included' AND review_id = %s;", (value, review_id))
    conn.commit()
    conn.close()


@cache.memoize(timeout=86400)
def get_categories():
    """ get the complete list of trial categories """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT category, code, id from ct_categories;")
    categories = cur.fetchall()
    conn.close()
    return [{'name': c['category'], "code": c['code'], "id": c['id']} for c in categories]


@cache.memoize(timeout=86400)
def category_counts():
    """ get the # reviews with linked trials in each category """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT ct.category, ct.code, count(distinct r.review_id) as review_count from ct_categories ct inner join category_condition cd on cd.category_id = ct.id inner join trial_conditions tc on tc.condition_id = cd.condition_id inner join review_rtrial r on r.nct_id = tc.nct_id where r.relationship = 'included' group by ct.category ORDER BY count(*) desc;")
    categories = cur.fetchall()
    conn.close()
    return [{'name': c['category'], "code": c['code'], "count": c['review_count']} for c in categories]


@cache.memoize(timeout=86400)
def get_conditions(category):
    """ get complete list of coditions for the specified category """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "select condition, id from ct_conditions where id in (select distinct condition_id from category_condition where category_id = %s)"
        "and exists (select 1 from trial_conditions tr where tr.condition_id = ct_conditions.id) order by condition;",
        (category,))
    conditions = cur.fetchall()
    conn.close()
    return conditions


@cache.memoize(timeout=86400)
def category_name(category_id):
    """ get the name of category from its ID """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("select category from ct_categories where id = %s;",
                (category_id,))
    category = cur.fetchall()
    conn.close()
    return category


@cache.memoize(timeout=86400)
def condition_counts(category):
    """ get the # reviews with linked trials for each condition in the specified category """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT ct.condition, ct.id, count(distinct r.review_id) as review_count from ct_conditions ct inner join trial_conditions tc on tc.condition_id = ct.id inner join review_rtrial r on r.nct_id = tc.nct_id inner join category_condition cd on cd.condition_id = tc.condition_id inner join ct_categories cat on cat.id = cd.category_id where r.relationship = 'included' and cd.category_id = %s group by ct.condition, cat.category ORDER BY count(*) desc;",
        (category,))
    conditions = cur.fetchall()
    conn.close()
    return [{'name': c['condition'], "id": c['id'], "count": c['review_count']} for c in conditions]


@cache.memoize(timeout=86400)
def reviews_for_condition(condition):
    """ get a list of reviews with linked trials with the specified condition """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT r.review_id, sr.title, sr.publish_date as year, ct.condition from ct_conditions ct inner join trial_conditions tc on tc.condition_id = ct.id inner join review_rtrial r on r.nct_id = tc.nct_id inner join systematic_reviews sr on r.review_id = sr.review_id where r.relationship = 'included' and tc.condition_id = %s group by r.review_id, sr.title, ct.condition, sr.publish_date order by sr.publish_date desc;",
        (condition,))
    reviews = cur.fetchall()
    conn.close()
    return reviews


def get_reviews_with_ids(ids):
    """ get a list of reviews from their PMIDs """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT review_id, title, publish_date as year from systematic_reviews where review_id in %s;",
                (tuple(x for x in ids),))
    matches = cur.fetchall()
    conn.close()
    return matches if matches else None


@cache.memoize(timeout=86400)
def unique_reviews_trials():
    """ get the count of unique reviews and unique trials that have links """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "select count(distinct review_id) as reviews, count(distinct nct_id) as trials from review_rtrial where relationship = 'included';")
    reviews = cur.fetchone()
    conn.close()
    return {"reviews": reviews['reviews'], "trials": reviews['trials']}


httplib.HTTPResponse.read = utils.patch_http_response_read(httplib.HTTPResponse.read)


def update_record(xml_file):
    """
    update trial in the database with data in XML specified file
    @param xml_file: path for xml file
    """
    try:
        obj = untangle.parse(xml_file)
    except Exception as e:
        print e
        return False
    result = {'condition': []}
    result['completion_date'] = None
    result['nct_id'] = obj.clinical_study.id_info.nct_id.cdata.rstrip("\r\n")
    result['brief_title'] = obj.clinical_study.brief_title.cdata.rstrip("\r\n")
    result['status'] = obj.clinical_study.overall_status.cdata.rstrip("\r\n")
    if hasattr(obj.clinical_study, 'official_title'):
        result['official_title'] = obj.clinical_study.official_title.cdata.rstrip("\r\n")
    else:
        result['official_title'] = None
    if hasattr(obj.clinical_study, 'brief_summary'):
        result['brief_summary'] = obj.clinical_study.brief_summary.textblock.cdata.rstrip("\r\n")
    else:
        result['brief_summary'] = None
    if hasattr(obj.clinical_study, 'enrollment'):
        result['enrollment'] = obj.clinical_study.enrollment.cdata
    else:
        result['enrollment'] = None
    if hasattr(obj.clinical_study, 'detailed_description'):
        result['detailed_description'] = obj.clinical_study.detailed_description.textblock.cdata.rstrip("\r\n")
    else:
        result['detailed_description'] = None

    if hasattr(obj.clinical_study, 'study_type'):
        result['study_type'] = obj.clinical_study.study_type.cdata.rstrip("\r\n")
    else:
        result['study_type'] = None
    if hasattr(obj.clinical_study, 'completion_date'):
        result['completion_date'] = obj.clinical_study.completion_date.cdata.rstrip("\r\n")
    if hasattr(obj.clinical_study, 'condition'):
        for condition in obj.clinical_study.condition:
            result['condition'].append(condition.cdata.rstrip("\r\n"))
    else:
        result['condition'] = None
    result['mesh_terms'] = []
    if hasattr(obj.clinical_study, 'condition_browse'):
        if hasattr(obj.clinical_study.condition_browse, 'mesh_term'):
            for mesh_term in obj.clinical_study.condition_browse.mesh_term:
                result['mesh_terms'].append(mesh_term.cdata.rstrip("\r\n"))
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("SELECT * FROM tregistry_entries WHERE nct_id = %s;", (obj.clinical_study.id_info.nct_id.cdata,))
    nct_id = cur.fetchone()
    if nct_id:
        cur.execute(
            "UPDATE tregistry_entries SET retrieval_timestamp = %s, study_type=%s, brief_title=%s, overall_status=%s, official_title=%s, brief_summary=%s, detailed_description=%s, enrollment=%s, completion_date=%s WHERE nct_id=%s;",
            (datetime.now(), result['study_type'], result['brief_title'], result['status'], result['official_title'],
             result['brief_summary'], result['detailed_description'], result['enrollment'], result['completion_date'],
             result['nct_id'],))
    else:
        cur.execute(
            "INSERT INTO tregistry_entries (nct_id, retrieval_timestamp, study_type, brief_title, overall_status, official_title, brief_summary, detailed_description, enrollment,completion_date) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s, %s,%s);", (
                result['nct_id'], datetime.now(), result['study_type'], result['brief_title'], result['status'],
                result['official_title'], result['brief_summary'], result['detailed_description'],
                result['enrollment'], result['completion_date'],))
    conn.commit()
    if result['mesh_terms']:
        for c in result['mesh_terms']:
            c = c.strip()
            cur.execute("SELECT id from ct_conditions where condition = %s;", (c,))
            c_id = cur.fetchone()
            if c_id:
                cur.execute(
                    "INSERT INTO trial_conditions(nct_id, condition_id, mesh_term) VALUES (%s, %s, TRUE) on CONFLICT(nct_id, condition_id) DO NOTHING;",
                    (result['nct_id'], c_id[0]))
                conn.commit()

    if result['condition']:
        for c in result['condition']:
            c = c.strip()
            cur.execute("SELECT id from ct_conditions where condition = %s;", (c,))
            c_id = cur.fetchone()
            if c_id:
                cur.execute(
                    "INSERT INTO trial_conditions(nct_id, condition_id) VALUES (%s, %s) on CONFLICT(nct_id, condition_id) DO NOTHING;",
                    (result['nct_id'], c_id[0]))
                conn.commit()
            else:
                cur.execute(
                    "INSERT INTO ct_conditions(condition, original) VALUES (%s, FALSE) on CONFLICT(condition) DO NOTHING RETURNING ID;",
                    (c,))
                conn.commit()
                id = cur.fetchone()
                cur.execute(
                    "INSERT INTO trial_conditions(nct_id, condition_id) VALUES (%s, %s) on CONFLICT(nct_id, condition_id) DO NOTHING;",
                    (result['nct_id'], id[0]))
                conn.commit()

    conn.commit()
    conn.close()


def get_trialpubs(nct_id):
    """
    get all known publications for a specified trial registry entry
    @param nct_id: id of trial registry entry
    @return: tuples of PMID & NCTID links
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT nct_id, trialpub_id FROM trialpubs_rtrial WHERE nct_id = %s;", (nct_id,))
    result = cur.fetchall()
    conn.close()
    return result


def pubmedarticle_to_db(article, table):
    """ save PubMedArticle object to the specified table """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    if table is 'trial_publications':
        cur.execute(
            "INSERT INTO trial_publications(trialpub_id, title, source, authors, publish_date, abstract, doi)" \
            " VALUES (%s,%s,%s,%s,%s,%s,%s) on conflict(trialpub_id) do nothing;",
            (article.pmid, article.title, article.jrnl, ', '.join(article.authors), article.year.split(' ')[0],
             article.abstract,
             article.doi))
        conn.commit()
    elif table is 'systematic_reviews':
        cur.execute(
            "INSERT INTO systematic_reviews(review_id, title, source, authors, publish_date, abstract, doi)" \
            " VALUES (%s,%s, %s,%s,%s,%s,%s) on conflict(review_id) do nothing;",
            (article.pmid, article.title, article.jrnl, ', '.join(article.authors), article.year.split(' ')[0],
             article.abstract, article.doi))
        conn.commit()
    conn.close()


def articles_with_nctids(pmid_list):
    """ get subset of PMIDs in pmid_list that have links to ClinicalTrials.gov """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("select distinct(trialpub_id) from trialpubs_rtrial where trialpub_id in %s;", (tuple(pmid_list),))
    matches = cur.fetchall()
    conn.close()
    return list(zip(*matches)[0]) if matches else None


def linked_nctids(pmid):
    """ Get the linked NCTIDs for the specified PMID """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("select nct_id from trialpubs_rtrial where trialpub_id = %s;", (pmid,))
    ids = cur.fetchall()
    conn.close()
    return list(zip(*ids)[0]) if ids else None


def related_reviews(review_id):
    """  get a list of review PMIDs that share trials with the specified review PMID, ordered by # of shared trials  """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT r.review_id, sr.title, count(r.*) FROM review_rtrial r INNER JOIN systematic_reviews sr ON r.review_id = "
        "sr.review_id WHERE r.relationship = 'included' AND r.nct_id IN (SELECT nct_id FROM review_rtrial WHERE"
        " review_id = %s AND relationship = 'included') and r.review_id != %s GROUP BY r.review_id, sr.title "
        " ORDER BY count(*) DESC LIMIT 10;", (review_id, review_id))
    result = cur.fetchall()
    conn.close()
    return result


def review_medtadata_db(pmid):
    """ get metadata for review with specified PMID  """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM systematic_reviews WHERE review_id = %s;", (pmid,))
    result = cur.fetchone()
    conn.close()
    return result


def is_starred(review_id, user_id):
    """ retrieve starred status of review for specified user  """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("select * from user_reviews where user_id = %s and review_id=%s;", (user_id, review_id))
    res = cur.fetchone()
    conn.close()
    return True if res else False


def get_review_trials_fast(review_id, order='total_votes', usr=None):
    """
    retrieve all trial registry entries and publications associated with a review in a specified order
    @param review_id: pmid of review
    @param order: 'total_votes', 'net_upvotes' or 'completion_date'
    @return: all registered trials and their linked publications
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if order == 'total_votes' or order == None:
        cur.execute(
            "SELECT "
            "tregistry_entries. *, review_rtrial. *, COALESCE(review_rtrial.upvotes, 0) + COALESCE(review_rtrial.downvotes, 0) AS sum, json_agg(distinct array[v.vote_type::TEXT, u.nickname::TEXT]) as voters, json_agg(distinct t.trialpub_id::TEXT) as trialpubs "
            " FROM "
            "tregistry_entries "
            "INNER "
            "JOIN "
            "review_rtrial "
            "ON "
            "tregistry_entries.nct_id = review_rtrial.nct_id "
            "left JOIN votes v ON review_rtrial.id = v.link_id "
            "left JOIN users u ON v.user_id = u.id "
            "  left join trialpubs_rtrial t on tregistry_entries.nct_id = t.nct_id "
            "where "
            "review_rtrial.review_id = %s GROUP BY tregistry_entries.nct_id, review_rtrial.review_id, review_rtrial.nct_id, review_rtrial.confidence_score,"
            "review_rtrial.upvotes, review_rtrial.downvotes, review_rtrial.verified, review_rtrial.relationship, review_rtrial.nickname, review_rtrial.id ORDER BY sum DESC;",
            (review_id,))
    elif order == 'completion_date':
        cur.execute(
            " SELECT tregistry_entries. *, review_rtrial. *, COALESCE(review_rtrial.upvotes, 0) + COALESCE(review_rtrial.downvotes, 0) AS sum, json_agg(distinct array[v.vote_type::TEXT, u.nickname::TEXT]) as voters, json_agg(distinct t.trialpub_id::TEXT) as trialpubs FROM tregistry_entries INNER JOIN review_rtrial ON tregistry_entries.nct_id = review_rtrial.nct_id left JOIN votes v ON review_rtrial.id = v.link_id left JOIN users u ON v.user_id = u.id left join trialpubs_rtrial t on tregistry_entries.nct_id = t.nct_id where review_rtrial.review_id = %s GROUP BY tregistry_entries.nct_id, review_rtrial.review_id, review_rtrial.nct_id, review_rtrial.confidence_score, review_rtrial.upvotes, review_rtrial.downvotes, review_rtrial.verified, review_rtrial.relationship, review_rtrial.nickname, review_rtrial.id ORDER BY to_date(completion_date, 'Month YYYY') desc NULLS LAST;",
            (review_id,))
    elif order == 'net_upvotes':
        cur.execute(
            "SELECT tregistry_entries.*, review_rtrial.*, json_agg(distinct array [v.vote_type :: TEXT, u.nickname :: TEXT]) as voters, json_agg(distinct t.trialpub_id :: TEXT)                                  as trialpubs FROM tregistry_entries INNER JOIN review_rtrial ON tregistry_entries.nct_id = review_rtrial.nct_id left JOIN votes v ON review_rtrial.id = v.link_id left JOIN users u ON v.user_id = u.id left join trialpubs_rtrial t on tregistry_entries.nct_id = t.nct_id where review_rtrial.review_id = %s GROUP BY tregistry_entries.nct_id, review_rtrial.review_id, review_rtrial.nct_id, review_rtrial.confidence_score, review_rtrial.upvotes, review_rtrial.downvotes, review_rtrial.verified, review_rtrial.relationship, review_rtrial.nickname, review_rtrial.id ORDER BY review_rtrial.upvotes desc NULLS LAST;",
            (review_id,))
    reg_trials = cur.fetchall()
    reg_trials = list(reg_trials)
    for i, trial in enumerate(reg_trials):
        trial = dict(trial)
        if usr:
            for v in trial['voters']:
                if usr and usr.nickname == v[1]:
                    trial['user_vote'] = v[0]
            trial['nicknames'] = ['you' if x[1] == usr.nickname else x[1] for x in trial['voters'] if x[1] is not None]
        else:
            trial['nicknames'] = [x[1] for x in trial['voters'] if x[1] is not None]
        if trial['nicknames']:
            trial['voters'] = str(', '.join(trial['nicknames']))
        else:
            trial['voters'] = ""
        reg_trials[i] = trial.copy()
    return {'reg_trials': reg_trials}

def get_trials_by_id(nct_list):
    """
    get the details of all trials specified in nct_list
    :param nct_list:
    :return: list of trial dicts
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT tr.nct_id, tr.brief_title, tr.overall_status, tr.enrollment, tr.completion_date,json_agg(distinct t.trialpub_id::TEXT) as trialpubs FROM tregistry_entries tr left join trialpubs_rtrial t on (tr.nct_id = t.nct_id and tr.nct_id in %s ) where tr.nct_id in %s  GROUP BY tr.nct_id, tr.brief_title, tr.overall_status, tr.enrollment, tr.completion_date;",(tuple(nct_list),tuple(nct_list)))
    trials = cur.fetchall()
    conn.close()
    return trials


def get_trial_xml(nct_id):
    """ download & return the XML for the specified trial from ClincialTrials.gov  """
    base_url = 'https://clinicaltrials.gov/ct2/show/'
    r = utils.retry_get(base_url + nct_id, params={'displayxml': 'true'})
    if r and r.status_code is 200:
        return r.text.encode('utf-8')
    else:
        return None
