from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity, linear_kernel
import crud
import scipy
import numpy as np
from scipy.sparse import csr_matrix
import pickle
import dblib
import requests
import config
from habanero import Crossref, cn
import json
from app import celery_inst
from flask_socketio import SocketIO
import eventlet
import re
import bs4
import collections
import sys
from eutils import Client
import eutils
import utils
reload(sys)
from celery.task.control import inspect, revoke
import time
import lxml
import request_data

sys.setdefaultencoding("utf8")

eutils_key = config.EUTILS_KEY


def check_trialpubs_nctids(review_id, review_doi=None, sess_id=None):
    """
    resolve the references of a review to PMIDs and NCTIDs
    @param review_id: PubMed ID of review
    @param review_doi: DOI of review
    @param sess_id: session ID if transitting progress via websocket
    @return: namedtuple with found PMIDs and NCTIDs
    """
    if sess_id:
        socketio = SocketIO(message_queue='amqp://localhost')
    ec = Client(api_key=eutils_key)
    cr = Crossref(mailto='paige.newman@mq.edu.au')
    if not review_doi:
        while True:
            try:
                paset = ec.efetch(db='pubmed', id=review_id)
                break
            except (
            eutils.exceptions.EutilsNCBIError, eutils.exceptions.EutilsRequestError, requests.exceptions.SSLError,
            requests.exceptions.ConnectionError) as e:
                print e
                time.sleep(5)
        pa = iter(paset).next()
        if hasattr(pa, 'doi'):
            review_doi = pa.doi
        if not review_doi:
            if sess_id:
                socketio.emit('crossrefbot_update', {'msg': 'No trials found. Crossrefbot complete'}, room=sess_id)
            return
    try:
        if review_doi[-1] == '.':
            review_doi = review_doi[:-1]
        resp = cr.works(ids=[str(review_doi)])
    except requests.HTTPError as e:
        if sess_id:
            socketio.emit('crossrefbot_update', {'msg': 'No trials found. Crossrefbot complete'}, room=sess_id)
        print e
        return
    if resp['status'] == 'ok':
        parsed = resp['message']
        if "reference" in parsed:
            if sess_id:
                socketio.emit('crossrefbot_update', {'msg': str(len(parsed[
                                                                        'reference'])) + ' references found in crossref. trying to resolve these to PubMed articles...'},
                              room=sess_id)
                eventlet.sleep(0)
            print str(len(parsed['reference'])) + ' references found in crossref'
            to_resolve = []
            references = parsed['reference']
            dois = [doi["DOI"] for doi in references if 'DOI' in doi]
            if dois:
                # if we get pubmed metadata for these DOIs, we can cross-check which dois match the ones in our set of references
                # what if > 250
                chunk_dois = utils.chunks(dois, 250)
                for dois in chunk_dois:
                    while True:
                        try:
                            esr = ec.esearch(db='pubmed', term=' OR '.join(['"' + doi + '"[AID]' for doi in dois]))
                            break
                        except (eutils.exceptions.EutilsNCBIError, eutils.exceptions.EutilsRequestError,
                                requests.exceptions.SSLError, requests.exceptions.ConnectionError,
                                lxml.etree.XMLSyntaxError) as e:
                            print e
                            time.sleep(5)
                    if esr.ids:
                        while True:
                            try:
                                paset = ec.efetch(db='pubmed', id=esr.ids)
                                break
                            except (eutils.exceptions.EutilsNCBIError, eutils.exceptions.EutilsRequestError,
                                    requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                                print e
                                time.sleep(5)
                        pa_iter = iter(paset)
                        while True:
                            try:
                                pma = pa_iter.next()
                            except StopIteration:
                                break
                            if pma.doi is not None and pma.doi in dois:
                                dois.remove(pma.doi)
                                to_resolve.append(pma.pmid)
            remaining = [x for x in references if ('DOI' not in x or ('DOI' in x and x['DOI'] in dois)) and (
                        'first-page' in x or 'author' in x or 'article-title' in x or 'volume' in x or 'journal-title' in x or 'year' in x)]
            if remaining:
                citation_pmids = request_data.batch_pmids_for_citation(remaining, debug=False)
                check_metadata = []
                if citation_pmids:
                    for i, citation in enumerate(citation_pmids):
                        if utils.RepresentsInt(citation):
                            to_resolve.append(citation)
                            check_metadata.append(citation)
                            continue
                        elif citation_pmids[i].startswith('AMBIGUOUS'):
                            cand = citation[10:].split(',')
                            if utils.RepresentsInt(cand[0]):
                                to_resolve.extend(cand)
                                check_metadata.append(cand)
                if check_metadata:
                    while True:
                        try:
                            paset = ec.efetch(db='pubmed', id=check_metadata)
                            break
                        except (eutils.exceptions.EutilsNCBIError, eutils.exceptions.EutilsRequestError,
                                requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                            print  e
                            time.sleep(5)
                    pa_iter = iter(paset)
                    while True:
                        try:
                            pma = pa_iter.next()
                        except StopIteration:
                            break
                        if pma.doi is not None and pma.doi in dois:
                            dois.remove(pma.doi)
                            to_resolve.append(pma.pmid)
            try_doi = batch_doi2pmid(dois)
            if try_doi:
                for doi in try_doi:
                    if utils.RepresentsInt(str(doi)):
                        to_resolve.append(doi)
            nct_ids = []
            for i, citation in enumerate(references):
                if 'unstructured' in citation.keys():
                    spl = citation['unstructured'].split(' ')
                    for i in spl:
                        if re.match(r"(NCT|nct)[0-9]{8}", i):
                            if len(i) == 11:
                                nct_ids.append(i)
                                continue
            to_resolve = [str(x) for x in to_resolve]
            to_resolve = list(set(to_resolve))
            content = collections.namedtuple('ids', ['pmids', 'nctids'])
            return content(to_resolve, nct_ids)
    return False


@celery_inst.task()
def check_citations(review_id, sess_id=None, review_doi=None):
    """
    check IDs obtained from the references of a review for automatic links, and save these links
    @param review_id: PubMed ID of review
    @param sess_id: session ID if transitting progress via websocket
    @param review_doi: DOI of review
    @return:
    """
    if sess_id:
        socketio = SocketIO(message_queue='amqp://localhost')
    ec = Client(api_key=eutils_key)
    while True:
        try:
            articles = ec.efetch(db='pubmed', id=review_id)
            break
        except (eutils.exceptions.EutilsNCBIError, eutils.exceptions.EutilsRequestError, requests.exceptions.SSLError,
                requests.exceptions.ConnectionError) as e:
            print e
            time.sleep(5)
    a_iter = iter(articles)
    while True:
        try:
            article = a_iter.next()
        except StopIteration:
            break
        print '-----------------' + article.pmid + '-------------------------'
        if article.doi is not None:
            ids = check_trialpubs_nctids(article.pmid, article.doi, sess_id=sess_id)
        else:
            ids = check_trialpubs_nctids(article.pmid, sess_id=sess_id)
        if ids:
            if ids.pmids:
                if sess_id:
                    socketio.emit('crossrefbot_update', {'msg': 'crossrefbot found references to ' + str(
                        len(ids.pmids)) + ' PubMed articles. Checking articles for links to included trials...'},
                                  room=sess_id)
                count = crud.articles_with_nctids(ids.pmids)
                if count and len(count) > 0:
                    if sess_id:
                        socketio.emit('crossrefbot_update',
                                      {'msg': str(len(count)) + ' articles have links to included trials'},
                                      room=sess_id)
                    for trialpub in count:
                        crud.review_publication(article.pmid, trialpub, 9)
                        linked_ncts = crud.linked_nctids(trialpub)
                        for nct in linked_ncts:
                            crud.review_trial(review_id, nct, False, 'included', user_id=9, nickname='crossrefbot')
            if ids.nctids:
                print 'nct ids in crossref = ' + str(len(ids.nctids))
                if sess_id:
                    socketio.emit('crossrefbot_update',
                                  {'msg': str(len(ids.nctids)) + ' included trials were listed directly in crossref'},
                                  room=sess_id)
                for nct_id in ids.nctids:
                    crud.review_trial(article.pmid, nct_id, False, 'included', 'crossrefbot', 9)
            if not ids.nctids and not ids.pmids:
                if sess_id:
                    socketio.emit('crossrefbot_update', {'msg': 'No trials found. Crossrefbot complete'}, room=sess_id)
            elif sess_id:
                socketio.emit('crossrefbot_update', {'msg': 'crossrefbot complete'}, room=sess_id)
        elif sess_id:
            socketio.emit('crossrefbot_update', {'msg': 'No trials found. Crossrefbot complete'}, room=sess_id)


def batch_doi2pmid(dois):
    """
    resolve article PMID from DOI by feeding article citation to PubMed advanced search
    @param dois: list of DOIs to resolve
    @return: list of corresponding PMIDs
    """
    citations = []
    for doi in dois:
        if doi[-1] == '.':
            doi = doi[:-1]
        try:
            # what if one fails?!
            cit = cn.content_negotiation(ids=doi, format="citeproc-json")
            if isinstance(cit, list):
                for c in cit:
                    citations.append(c)
            else:
                citations.append(cit)
        except Exception as e:
            print e
            continue
    parsed_citations = []
    for x in citations:
        try:
            cit = json.loads(x)
        except TypeError as e:
            print e
            continue
        parsed_cit = {}
        if 'page' in cit:
            parsed_cit['first_page'] = cit['page'].split('-')[0]
        if 'volume' in cit:
            parsed_cit['volume'] = cit['volume']
        if 'container-title' in cit:
            parsed_cit['journal'] = cit['container-title']
        if 'issued' in cit:
            parsed_cit['year'] = cit['issued']['date-parts'][0][0]
        if 'author' in cit:
            if 'family' in cit['author'][0]:
                parsed_cit['aulast'] = cit['author'][0]['family']
        parsed_citations.append(parsed_cit)
    pmids = request_data.batch_pmids_for_citation(parsed_citations, debug=False)
    return pmids


def check_basicbot2_running(review_id):
    """ determine if basicbot2 is already running for the specified review """
    i = inspect()
    active_tasks = i.active()
    if active_tasks:
        for task in active_tasks['worker@ip-172-31-14-248.ap-southeast-2.compute.internal']:
            if task['name'] == 'bot.basicbot2':
                if 'review_id' in task['kwargs'] and str(review_id) in task['kwargs']:
                    return True
    return False


@celery_inst.task()
def basicbot2(review_id=None, sess_id=None):
    """
    use document similarity to recommend trials for a review based on similarity to current included trials
    @param review_id: PMID of review
    @param sess_id: session ID if transitting progress via websocket
    """
    if sess_id:
        socketio = SocketIO(message_queue='amqp://localhost')
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("SELECT nct_id FROM review_rtrial WHERE relationship = 'included' AND review_id = %s;",
                (review_id,))
    trials = cur.fetchall()
    if len(trials) < 1:
        print 'no trials for basicbot2'
        conn.close()
        return False
    if trials:
        cur.execute(
            "delete from votes where link_id in (select id from review_rtrial where review_id = %s) and user_id = %s;",
            (review_id, 10))
        conn.commit()
        cur.execute("delete from review_rtrial where upvotes = 0 and downvotes = 0 and user_id = 10;")
        conn.commit()
        conn.close()
        if sess_id:
            socketio.emit('basicbot2_update', {'msg': 'triggering basicbot2'}, room=sess_id)
        tfidf_matrix = scipy.sparse.load_npz(utils.most_recent_tfidf())
        ids = np.load(utils.most_recent_tfidf_labels())
        trials = list(zip(*trials)[0])
        ix = np.isin(ids, trials)
        trial_indices = np.where(ix)[0]
        if sess_id:
            socketio.emit('basicbot2_update', {'msg': 'vectorizing stuff'}, room=sess_id)
        trial_vecs = tfidf_matrix[trial_indices, :]
        cos_sim = linear_kernel(trial_vecs, tfidf_matrix)
        if sess_id:
            socketio.emit('basicbot2_update', {'msg': 'calculating cosine similarity'}, room=sess_id)
        final = cos_sim.sum(axis=0)
        top = np.argpartition(final, -100)[-100:]
        top_ranked = set(ids[np.array(top)]) - set(ids[trial_indices])
        if sess_id:
            socketio.emit('basicbot2_update', {'msg': 'inserting basicbot 2 predictions'}, room=sess_id)
        for nct_id in top_ranked:
            crud.review_trial(review_id, nct_id, False, 'relevant', 'basicbot2', 10)
        if sess_id:
            socketio.emit('basicbot2_update', {'msg': 'basicbot2 complete!'}, room=sess_id)


@celery_inst.task()
def docsim(review_id, sess_id=None):
    """
    use document similarity to recommend trials based on similarity to title & abstract text of review
    @param review_id: PMID of review
    @param sess_id: session ID if transitting progress via websocket
    """
    if sess_id:
        socketio = SocketIO(message_queue='amqp://localhost')
        socketio.emit('docsim_update', {'msg': 'started basicbot'}, room=sess_id)
        eventlet.sleep(0)
    review = crud.review_medtadata_db(review_id)
    document = (review['title'] + """ """ + review['abstract']) if review['abstract'] else review['title']
    if not document:
        if sess_id:
            socketio.emit('docsim_update', {'msg': 'Unable to make predictions. Basicbot complete'}, room=sess_id)
        return
    tf_transformer = TfidfVectorizer(use_idf=False)
    trials_vectorizer = pickle.load(open(utils.most_recent_tfidf_vec()))
    normalised_tf_vector = tf_transformer.fit_transform([document])
    if sess_id:
        socketio.emit('docsim_update', {'msg': 'vectorising stuff...'}, room=sess_id)
        eventlet.sleep(0)
    tfidf_matrix = scipy.sparse.load_npz(utils.most_recent_tfidf())
    idf_indices = [trials_vectorizer.vocabulary_[feature_name] for feature_name in tf_transformer.get_feature_names() if
                   feature_name in trials_vectorizer.vocabulary_.keys()]
    tf_indices = [tf_transformer.vocabulary_[feature_name] for feature_name in trials_vectorizer.get_feature_names() if
                  feature_name in tf_transformer.vocabulary_.keys()]
    final_idf = trials_vectorizer.idf_[np.array(idf_indices)]
    final_tf = np.array(normalised_tf_vector.toarray()[0])[np.array(tf_indices)]
    review_tfidf = np.asmatrix(final_tf * final_idf)
    tfidf_matrix = tfidf_matrix[:, np.array(idf_indices)]
    if sess_id:
        socketio.emit('docsim_update', {'msg': 'calculating similarity...'}, room=sess_id)
        eventlet.sleep(0)
    cos_sim = cosine_similarity(review_tfidf, tfidf_matrix).flatten()
    related_docs_indices = cos_sim.argsort()[:-100:-1]
    ids = np.load(utils.most_recent_tfidf_labels())
    to_insert = ids[np.array(related_docs_indices)]
    if sess_id:
        socketio.emit('docsim_update', {'msg': 'inserting predictions'}, room=sess_id)
        eventlet.sleep(0)
    for id in to_insert:
        crud.review_trial(review_id, id, False, 'relevant', 'basicbot1', 3)
    if sess_id:
        socketio.emit('docsim_update', {'msg': 'basicbot complete!'}, room=sess_id)
        eventlet.sleep(0)


@celery_inst.task()
def cochrane_ongoing_excluded(doi, review_id, sess_id=None):
    """
    extract & save ongoing and excluded trial IDs for a review from Cochrane Library website text
    @param doi: DOI of review
    @param review_id: PMID of review
    @param sess_id: session ID if transitting progress via websocket
    @return:
    """
    if sess_id:
        socketio = SocketIO(message_queue='amqp://localhost')
        socketio.emit('cochranebot_update', {'msg': 'searching cochrane for ongoing or excluded studies'}, room=sess_id)
        socketio.sleep(0)
    base_url = "https://www.cochranelibrary.com/cdsr/doi/{}/references".format(doi)
    try:
        r = requests.get(base_url)
    except requests.exceptions.TooManyRedirects:
        if sess_id:
            socketio.emit('cochranebot_update', {'msg': 'nothing found by cochranebot'}, room=sess_id)
            socketio.sleep(0)
            socketio.emit('cochranebot_update', {'msg': 'cochranebot complete'}, room=sess_id)
        return
    if r.status_code == 200:
        soup = bs4.BeautifulSoup(r.content, 'html.parser')
        spl_doi = doi.split('.')[2]
        if 'CD' not in spl_doi:
            if sess_id:
                socketio.emit('cochranebot_update', {'msg': 'nothing found by cochranebot'}, room=sess_id)
                socketio.sleep(0)
                socketio.emit('cochranebot_update', {'msg': 'cochranebot complete'}, room=sess_id)
            return
        excluded_studies = soup.find_all("div", {"class": "references_excludedStudies"})
        if excluded_studies:
            nct_ids = []
            pmids = []
            for b in excluded_studies:
                for x in re.finditer(r"(NCT|nct)[0-9]{8}", str(b)):
                    nct_ids.append(x.group().upper())
                    if sess_id:
                        socketio.emit('cochranebot_update', {'msg': 'found nct ID ' + nct_ids[-1]}, room=sess_id)
                        socketio.sleep(0)
                for x in re.finditer(r"pubmed/[0-9]{8}", str(b)):
                    pmids.append(x.group().split('/')[1])
                    if sess_id:
                        socketio.emit('cochranebot_update', {'msg': 'found PMID ' + pmids[-1]}, room=sess_id)
                        socketio.sleep(0)
                for x in re.finditer(r"PUBMED: [0-9]{8}", str(b)):
                    pmids.append(x.group().split(' ')[1])
                    if sess_id:
                        socketio.emit('cochranebot_update', {'msg': 'found PMID ' + pmids[-1]}, room=sess_id)
                        socketio.sleep(0)
            # if included by crossrefbot, move it
            if pmids:
                count = crud.articles_with_nctids(pmids)
                print 'cochrane excluded articles with links = ' + str(count)
                if count and len(count) > 0:
                    for trialpub in count:
                        crud.review_publication(review_id, trialpub, 17)
                        linked_ncts = crud.linked_nctids(trialpub)
                        for nct in linked_ncts:
                            crud.review_trial(review_id, nct, False, 'relevant', user_id=17, nickname='cochranebot',
                                              vote_type='down')
                            if sess_id:
                                socketio.emit('cochranebot_update',
                                              {'msg': 'cochranebot found excluded trials with IDs ' + ', '.join(
                                                  linked_ncts)},
                                              room=sess_id)
            nct_ids = list(set(nct_ids))
            print 'excluded: ' + ', '.join(nct_ids)
            for id in nct_ids:
                # if included by crossrefbot, move it
                crud.review_trial(review_id, id, False, 'relevant', 'cochranebot', 17, vote_type='down')
        ongoing_studies = soup.find_all("div", {"class": "references_ongoingStudies"})
        if ongoing_studies:
            relevant_nct = []
            for b in ongoing_studies:
                for x in re.finditer(r"(NCT|nct)[0-9]{8}", str(b)):
                    relevant_nct.append(x.group().upper())
                    if sess_id:
                        socketio.emit('cochranebot_update', {'msg': 'found nct ID ' + relevant_nct[-1]}, room=sess_id)
            relevant_nct = list(set(relevant_nct))
            print relevant_nct
            for nct in relevant_nct:
                # TODO ensure that already included gets moved to relevant
                crud.review_trial(review_id, nct, False, 'relevant', 'cochranebot', 17)
        awaiting_studies = soup.find_all("div", {"class": "references_awaitingAssessmentStudies"})
        if awaiting_studies:
            relevant_nct = []
            for b in awaiting_studies:
                for x in re.finditer(r"(NCT|nct)[0-9]{8}", str(b)):
                    relevant_nct.append(x.group().upper())
                    if sess_id:
                        socketio.emit('cochranebot_update', {'msg': 'found nct ID ' + relevant_nct[-1]},
                                      room=sess_id)
            relevant_nct = list(set(relevant_nct))
            print relevant_nct
            for nct in relevant_nct:
                crud.review_trial(review_id, nct, False, 'relevant', 'cochranebot', 17)
        if not excluded_studies and not awaiting_studies and not ongoing_studies:
            if sess_id:
                socketio.emit('cochranebot_update', {'msg': 'nothing found by cochranebot'}, room=sess_id)
                socketio.sleep(0)
                socketio.emit('cochranebot_update', {'msg': 'cochranebot complete'}, room=sess_id)
            return
        if sess_id:
            socketio.emit('cochranebot_update', {'msg': 'cochranebot complete', 'refresh_both': True}, room=sess_id)
            socketio.sleep(0)


@celery_inst.task()
def cochranebot(doi, review_id, sess_id=None):
    """
       extract & save included trial IDs for a review from Cochrane Library website text
       @param doi: DOI of review
       @param review_id: PMID of review
       @param sess_id: session ID if transitting progress via websocket
       """
    if sess_id:
        socketio = SocketIO(message_queue='amqp://localhost')
        socketio.emit('cochranebot_update', {'msg': 'searching cochrane for included studies'}, room=sess_id)
        socketio.sleep(0)
    base_url = "https://www.cochranelibrary.com/cdsr/doi/{}/references".format(doi)
    try:
        r = requests.get(base_url)
    except requests.exceptions.TooManyRedirects:
        if sess_id:
            socketio.emit('cochranebot_update', {'msg': 'nothing found by cochranebot'}, room=sess_id)
            socketio.sleep(0)
            socketio.emit('cochranebot_update', {'msg': 'cochranebot complete'}, room=sess_id)
        return
    if r.status_code == 200:
        soup = bs4.BeautifulSoup(r.content, 'html.parser')
        spl_doi = doi.split('.')[2]
        if 'CD' not in spl_doi:
            if sess_id:
                socketio.emit('cochranebot_update', {'msg': 'nothing found by cochranebot'}, room=sess_id)
                socketio.sleep(0)
                socketio.emit('cochranebot_update', {'msg': 'cochranebot complete'}, room=sess_id)
            return
        included_studies = soup.find_all("div", {"class": "references_includedStudies"})
        if included_studies:
            nct_ids = []
            pmids = []
            for b in included_studies:
                for x in re.finditer(r"(NCT|nct)[0-9]{8}", str(b)):
                    nct_ids.append(x.group().upper())
                    if sess_id:
                        socketio.emit('cochranebot_update', {'msg': 'found nct ID ' + nct_ids[-1]}, room=sess_id)
                        socketio.sleep(0)
                for x in re.finditer(r"pubmed/[0-9]{8}", str(b)):
                    pmids.append(x.group().split('/')[1])
                    if sess_id:
                        socketio.emit('cochranebot_update', {'msg': 'found PMID ' + pmids[-1]}, room=sess_id)
                        socketio.sleep(0)
                for x in re.finditer(r"PUBMED: [0-9]{8}", str(b)):
                    pmids.append(x.group().split(' ')[1])
                    if sess_id:
                        socketio.emit('cochranebot_update', {'msg': 'found PMID ' + pmids[-1]}, room=sess_id)
                        socketio.sleep(0)
            if sess_id:
                socketio.emit('cochranebot_update', {'msg': 'trying to resolve automatic links from PubMed IDs'},
                              room=sess_id)
                socketio.sleep(0)
            if pmids:
                count = crud.articles_with_nctids(pmids)
                print 'cochrane included articles with links = ' + str(count)
                if count and len(count) > 0:
                    for trialpub in count:
                        crud.review_publication(review_id, trialpub, 17)
                        linked_ncts = crud.linked_nctids(trialpub)
                        for nct in linked_ncts:
                            crud.review_trial(review_id, nct, False, 'included', user_id=17, nickname='cochranebot',
                                              vote_type='up')
                            if sess_id:
                                socketio.emit('cochranebot_update',
                                              {'msg': 'cochranebot found included trials with IDs ' + ', '.join(
                                                  linked_ncts)},
                                              room=sess_id)
            nct_ids = list(set(nct_ids))
            print 'cochrane nct_ids ' + str(nct_ids)

            for id in nct_ids:
                crud.review_trial(review_id, id, False, 'included', 'cochranebot', 17)
        if not included_studies:
            if sess_id:
                socketio.emit('cochranebot_update', {'msg': 'nothing found by cochranebot'}, room=sess_id)
                socketio.sleep(0)
                socketio.emit('cochranebot_update', {'msg': 'cochranebot complete'}, room=sess_id)
            return
    if sess_id:
        socketio.emit('cochranebot_update', {'msg': 'cochranebot complete'}, room=sess_id)
        socketio.sleep(0)
