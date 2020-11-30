from eventlet import monkey_patch

monkey_patch()

from sklearn.feature_extraction.text import TfidfVectorizer
import crud
import scipy
import numpy as np
from scipy.sparse import csr_matrix
import pickle
import psycopg2.extras

import dblib
from datetime import timedelta
import config
import psycopg2.extras
from urllib.request import urlopen
from urllib.error import HTTPError
import zipfile
import glob
import bot
from eutils import Client
import os
from threading import Thread
import time
import matplotlib

matplotlib.use('Agg')
from sklearn.decomposition import TruncatedSVD
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import numpy
import scipy.sparse
from datetime import datetime
import utils
import eutils
from subprocess import call
import matfac as mf
import requests

eutils_key = config.EUTILS_KEY


def _gen_tfidf_matrix(docs, labels):
    """
    generate & save a TFIDF matrix for all documents in the specified corpus
    @param corpus: list of document texts
    @param labels: document labels
    """
    date = datetime.now().date().strftime('%d-%m-%Y')
    tfidf_vectorizer = TfidfVectorizer(use_idf=True)
    tfidf_matrix = tfidf_vectorizer.fit_transform(docs)
    pickle.dump(tfidf_vectorizer, open('models/tfidf/vectorizer_' + date + '.pickle', 'wb'))
    scipy.sparse.save_npz('models/tfidf/tfidf_matrix_' + date + '.npz', tfidf_matrix)
    np.save(open('models/tfidf/nct_ids_' + date + '.pickle', "wb"), np.array(labels))


def update_tfidf():
    """ retrieve all trial docs from database and generate a tfidf matrix """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        'SELECT nct_id, brief_title, official_title, brief_summary, detailed_description, condition FROM tregistry_entries;')
    trials = cur.fetchall()
    conn.close()
    labels = []
    text = []
    for x in trials:
        x = dict(x)
        labels.append(x['nct_id'])
        del x['nct_id']
        text.append(""" """.join(y for y in x.values() if y is not None))
    _gen_tfidf_matrix(text, labels)


def matfac_results(fname):
    """  interpret matrix factorization results & insert trial recommendations """
    results = np.load(fname)
    vec = pickle.load(open('models/matfac/countvectorizer.pickle'))
    vocab = vec.vocabulary_
    inverse_vocab = {v: k for k, v in vocab.items()}
    nct_ids = np.load('models/matfac/feature_ids.pickle')
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    for c, col in enumerate(results.T):
        sorted = col.argsort()[::-1][0:100]
        top_trials = nct_ids[sorted]
        for trial in top_trials:
            print(inverse_vocab[c], trial)
            cur.execute("SELECT * FROM systematic_reviews WHERE  review_id = %s;", (inverse_vocab[c],))
            review = cur.fetchall()
            if review:
                crud.review_trial(inverse_vocab[c], trial, False, 'relevant', 'matfacbot', 11)
    conn.close()


def update_basicbot():
    """ fetch all reviews and re-run basicbot """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("SELECT review_id, doi, source FROM systematic_reviews ORDER BY review_id desc;")
    reviews = cur.fetchall()
    conn.close()
    remove_bot_votes(3)
    for i, review in enumerate(reviews):
        print('%s/%s update_basicbot' % (i, len(reviews)))
        bot.docsim(review[0])


def update_basicbot2():
    """ fetch all reviews and re-run basicbot2 """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute(
        "SELECT review_id FROM review_rtrial WHERE relationship = 'included' GROUP BY review_id HAVING count(*) > 4;")
    reviews = cur.fetchall()
    conn.close()
    remove_bot_votes(10)
    for i, review in enumerate(reviews):
        print('%s/%s update_basicbot2' % (i, len(reviews)))
        bot.basicbot2(review[0])


def remove_bot_votes(bot_id):
    """ remove all votes from the specified bot"""
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("DELETE FROM es3.public.votes WHERE es3.public.votes.user_id = %s;", (bot_id,))
    conn.commit()
    conn.close()


def populate_reviews(period):
    """ download all new reviews made available on pubmed in the last <period> # days & save to db if they have trials in
    CrossRef or Cochrane """

    ec = Client(api_key=eutils_key)

    pmids = []
    page = 0
    print('populate_reviews, gathering pmids')
    base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'

    while True:
        r = utils.requests_retry_session().get(base_url, params={
            'db': 'pubmed',
            'term': 'systematic review[ti] OR meta analysis[ti] OR cochrane database of systematic reviews[ta]',
            'format': 'json',
            'retmax': 50000,
            'retstart': page * 50000,
            'email': crud.eutils_email,
            'tool': crud.eutils_tool,
            'api_key': eutils_key,
            'date_type': 'edat',
            'mindate': (datetime.now().date() - timedelta(days=period)).strftime(
                '%Y/%m/%d'),
            'maxdate': '3000'
        })
        if not r:
            break
        json = r.json()
        current_pmids = json['esearchresult']['idlist']
        if not current_pmids or len(current_pmids) == 0:
            break
        pmids = pmids + current_pmids
        print('page %s, pmid count: %s' % (page, len(pmids)))
        page += 1

    segments = utils.chunks(pmids, 100)
    for s in segments:
        while True:
            try:
                articles = ec.efetch(db='pubmed', id=s)
                break
            except (eutils.EutilsNCBIError, eutils.EutilsRequestError,
                    requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError) as e:
                print(e)
                time.sleep(5)
        a_iter = iter(articles)
        while True:
            try:
                article = next(a_iter)
            except StopIteration:
                break
            print('-----------------' + article.pmid + '-------------------------')
            # if crud.review_medtadata_db(article.pmid):
            #     print('Already exists in db, skipping', article.pmid)
            #     continue
            if article.doi is not None:
                ids = bot.check_trialpubs_nctids(article.pmid, article.doi)
            else:
                ids = bot.check_trialpubs_nctids(article.pmid)
            if ids:
                if ids.pmids:
                    print(ids.pmids)
                    count = crud.articles_with_nctids(tuple(x for x in ids.pmids))
                    print(count)
                    if count and len(count) > 0:
                        print('articles with links: %s' % len(count))
                        print('inserting %s' % article.pmid)
                        crud.pubmedarticle_to_db(article, 'systematic_reviews')
                        for trialpub in count:
                            crud.review_publication(article.pmid, trialpub, 9)
                            linked_ncts = crud.linked_nctids(trialpub)
                            for nct in linked_ncts:
                                crud.review_trial(article.pmid, nct, False, 'included', user_id=9,
                                                  nickname='crossrefbot')
                if ids.nctids:
                    crud.pubmedarticle_to_db(article, 'systematic_reviews')
                    print('nct ids in crossref: %s ' % len(ids.nctids))
                    for nct_id in ids.nctids:
                        crud.review_trial(article.pmid, nct_id, False, 'included', 'crossrefbot', 9)
                if not ids.nctids and not ids.pmids:
                    print('found nothing')
            else:
                print('nothing')
            if 'Cochrane' in article.jrnl:
                print('Cochrane')
                crud.pubmedarticle_to_db(article, 'systematic_reviews')
                bot.cochranebot(article.doi, article.pmid)
                bot.cochrane_ongoing_excluded(article.doi, article.pmid)
                conn = dblib.create_con(VERBOSE=True)
                cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cur.execute("select rt.review_id, json_agg(distinct v.user_id) as users from review_rtrial rt"
                            " inner join votes v on rt.id = v.link_id where rt.review_id = %s group by"
                            " rt.review_id;", (article.pmid,))
                new_users = cur.fetchone()
                if not new_users:
                    new_users = {'users': []}
                if not {17, 9} & set(new_users['users']):
                    print('deleting ' + str(new_users['users']), article.pmid)
                    cur.execute(
                        "delete from votes where link_id in (select id from review_rtrial where review_id = %s);",
                        (article.pmid,))
                    conn.commit()
                    cur.execute("delete from review_trialpubs where review_id = %s;", (article.pmid,))
                    conn.commit()
                    cur.execute("delete from review_rtrial where review_id = %s;", (article.pmid,))
                    conn.commit()
                    cur.execute("delete from systematic_reviews where review_id = %s;", (article.pmid,))
                    conn.commit()
                conn.close()
            else:
                print('not cochrane')


def fill_missing_bots():
    """ run bots on any reviews that are missing predictions from that bot """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("select rt.review_id, sr.source, sr.doi, json_agg(distinct v.user_id) as users from review_rtrial rt "
                "inner join votes v on rt.id = v.link_id inner join systematic_reviews sr on rt.review_id = sr.review_id "
                "group by rt.review_id, sr.source, sr.doi;")
    res = cur.fetchall()
    for r in res:
        if 'Cochrane' in r['source']:
            if len({17, 9} & set(r['users'])) < 2:
                print(r['users'])
                cb1 = Thread(target=bot.cochranebot, args=(r['doi'], r['review_id']))
                cb1.start()
                xrb = Thread(target=bot.check_citations, args=(r['review_id'],))
                xrb.start()
                cb1.join()
                xrb.join()
                cb2 = Thread(target=bot.cochrane_ongoing_excluded, args=(r['doi'], r['review_id']))
                cb2.start()
                cb2.join()
        else:
            if not {9} & set(r['users']):
                print(r['users'])
                bot.check_citations(r['review_id'])
        cur.execute("select rt.review_id, json_agg(distinct v.user_id) as users from review_rtrial rt"
                    " inner join votes v on rt.id = v.link_id where rt.review_id = %s group by"
                    " rt.review_id;", (r['review_id'],))
        new_users = cur.fetchone()
        if not new_users:
            new_users = {'users': []}
        if not {17, 9} & set(new_users['users']):
            print('deleting ' + str(new_users['users']), r['review_id'])
            cur.execute("delete from votes where link_id in (select id from review_rtrial where review_id = %s);",
                        (r['review_id'],))
            conn.commit()
            cur.execute("delete from review_trialpubs where review_id = %s;", (r['review_id'],))
            conn.commit()
            cur.execute("delete from review_rtrial where review_id = %s;", (r['review_id'],))
            conn.commit()
            cur.execute("delete from systematic_reviews where review_id = %s;", (r['review_id'],))
            conn.commit()

        if 3 not in new_users['users'] and 10 not in new_users['users']:
            bb1 = Thread(target=bot.docsim, args=(r['review_id'],))
            bb1.start()
            bb2 = Thread(target=bot.basicbot2, args=(r['review_id'],))
            bb2.start()
            bb1.join()
            bb2.join()
        elif 10 not in new_users['users']:
            bb2 = Thread(target=bot.basicbot2, args=(r['review_id'],))
            bb2.start()
            bb2.join()
    conn.close()



def update_trial_publications(period):
    """
    Pull the newest pubmed articles that reference ct.gov IDs and save them to the database
    Should be run every period number of days
    @param period: number of days back to start search
    @return: None
    """
    # edge cases
    # 32601120 NCT0282152 -- nct given with missing digit
    # 31899823 NCT00020085 -- nct is an alias for NCT00004635

    ec = Client(api_key=eutils_key)

    pmids = []
    page = 0
    print('update_trial_publications, gathering pmids')
    base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'

    while True:
        r = utils.retry_get(base_url, params={
            'db': 'pubmed',
            'term': 'clinicaltrials.gov[si]',
            'format': 'json',
            'retmax': 10000,
            'retstart': page * 10000,
            'email': crud.eutils_email,
            'tool': crud.eutils_tool,
            'api_key': eutils_key,
            'date_type': 'edat',
            'mindate': (datetime.now() - timedelta(days=period)).strftime(
                '%Y/%m/%d'),
            'maxdate': 3000
        })
        if not r:
            break
        json = r.json()
        current_pmids = json['esearchresult']['idlist']
        if not current_pmids or len(current_pmids) == 0:
            break
        pmids = pmids + current_pmids
        print('page %s, pmid count: %s' % (page, len(pmids)))
        page += 1


    segments = utils.chunks(pmids, 100)
    for s in segments:
        while True:
            try:
                articles = ec.efetch(db='pubmed', id=s)
                # articles = ec.efetch(db='pubmed', id=[31335881])
                break
            except (
                    eutils.EutilsNCBIError, eutils.EutilsRequestError,
                    requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError) as e:
                print(e)
                time.sleep(5)
        for a in articles:
            xpath = 'MedlineCitation/Article/DataBankList/DataBank[DataBankName = "ClinicalTrials.gov"]/AccessionNumberList/AccessionNumber/text()'
            nct_ids = a._xml_root.xpath(xpath)
            print('nct_ids found for pmid %s = [%s]' % (a.pmid, ', '.join(nct_ids)))
            if len(nct_ids) > 0:
                crud.pubmedarticle_to_db(a, 'trial_publications')
                for nct_id in nct_ids:
                    if len(nct_id) != 11:
                        print('##WARNING!: ignoring %s (%s) - not the expected 11 chars long, possible missing digit' %
                              (nct_id, a.pmid))
                        continue
                    crud.publication_trial(a.pmid, nct_id, 9)


def update_tregistry_entries(period):
    """
    Pull tregistry entries
    @return:
    """
    print('update_tregistry_entries')
    down_chunk = 1
    while True:
        template = 'https://clinicaltrials.gov/ct2/results/download_studies?lupd_s={}&lupd_e={}&down_fmt=xml&down_count=10000&down_chunk={}'
        end = datetime.now()
        start = end - timedelta(days=period)
        base_url = template.format(start.strftime('%m/%d/%Y'), end.strftime('%m/%d/%Y'), down_chunk)
        print(base_url)
        try:
            response = urlopen(base_url)
        except HTTPError as e:
            print('downloaded all available trials in timeframe', e)
            break
        local_filename = "test_folder.zip"
        CHUNK = 16 * 1024
        with open(local_filename, 'wb') as f:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                f.write(chunk)
        with zipfile.ZipFile("test_folder.zip", "r") as zip_ref:
            zip_ref.extractall("nct_xml/")
        path = "nct_xml/NCT*.xml"
        for i, fname in enumerate(glob.glob(path)):
            if i % 100 == 0:
                print('chunk %s, %sk/10k: %s' % (down_chunk, i / 1000, fname[8:19]))  # 8:19 trying to return just nctid
            crud.update_record(fname)
            os.remove(fname)

        down_chunk += 1


def update_bots(period=None):
    """ run bots on newly added reviews """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "select distinct on (sr.review_id) sr.review_id, sr.doi, sr.source from systematic_reviews sr where "
        "not exists(select 1 from review_rtrial rt where rt.review_id = sr.review_id and rt.user_id != 9 and rt.user_id != 17) and "
        " date_added < %s::TIMESTAMP;", (datetime.utcnow() - timedelta(minutes=10),))
    reviews = cur.fetchall()
    conn.close()
    for rev in reviews:
        print(rev['review_id'])
        bb1 = Thread(target=bot.docsim, args=(rev['review_id'],))
        bb1.start()
        bb2 = Thread(target=bot.basicbot2, args=(rev['review_id'],))
        bb2.start()
        bb1.join()
        bb2.join()


def regenerate_tsne():
    """ regen the TSNE matrix & plot image with the latest trial data """
    date = datetime.now().date().strftime('%d-%m-%Y')
    tfidf_matrix = scipy.sparse.load_npz(utils.most_recent_tfidf())
    _tsne(tfidf_matrix, date)
    new_tsne = numpy.load('models/tsne/tsne_matrix_' + date + '.npy')
    # generate new _tsne background plot
    _new_tsne_img(new_tsne, date)
    # uncomment this if uploading to a remote server
    upload_models()


def _tsne(input_matrix, date):
    """
    Generate and save TSNE visualisation of input matrix
    @param input_matrix: 2D sparse CSR matrix
    @return: None
    """
    transformer = TruncatedSVD(n_components=50, random_state=0)
    X_reduced = transformer.fit_transform(input_matrix)
    X_embedded = TSNE(n_components=2, perplexity=50, verbose=2, init='pca', learning_rate=1000).fit_transform(X_reduced)
    numpy.save('models/tsne/tsne_matrix_' + date, X_embedded)


def _new_tsne_img(matrix, date):
    """ generate a PNG plot of the specified tsne image"""
    fig = plt.figure(figsize=(5, 5))
    ax = plt.axes(frameon=False)
    plt.setp(ax, xticks=(), yticks=())
    plt.subplots_adjust(left=0.0, bottom=0.0, right=1.0, top=1.0,
                        wspace=0.0, hspace=0.0)
    xlim = (-71.551894338989271, 66.381507070922851)
    ylim = (-70.038440855407714, 70.644477995300306)
    ax.set_ylim(ylim)
    ax.set_xlim(xlim)
    plt.scatter(matrix[:, 0], matrix[:, 1],
                c='0.85', edgecolors='none', alpha=0.8,
                marker='.', s=1)
    plt.savefig('app/static/images/tsne' + date + '_sml.png', format='png', dpi=400)


def upload_models():
    """ upload the latest tfidf and TSNE models to webserver """
    tfidf_matrix = utils.most_recent_tfidf()
    tfidf_vec = utils.most_recent_tfidf_vec()
    tfidf_labels = utils.most_recent_tfidf_labels()
    tsne_matrix = utils.most_recent_tsne()
    tsne_image = utils.most_recent_tsne_img()
    for x in [tfidf_labels, tsne_matrix, tsne_image]:
        print(datetime.fromtimestamp(os.path.getmtime(x)))
        if datetime.fromtimestamp(os.path.getmtime(x)) < datetime.now() - timedelta(days=2):
            print('too old!')
            return
    for x in [tfidf_labels, tsne_matrix, tsne_image, tfidf_matrix, tfidf_vec]:
        cmd = 'scp -i ' + config.SCP_KEYFILE + ' ' + x + ' ' + config.SCP_USER + '@' + config.SCP_HOST + ':' + replace_local_path(
            x)
        print(cmd)
        call(cmd.split())
    for x in [tfidf_labels, tfidf_matrix]:
        cmd = 'scp -i ' + config.SCP2_KEYFILE + ' ' + x + ' ' + config.SCP2_USER + '@' + config.SCP2_HOST + ':' + config.REMOTE_PATH2 + '/models/tfidf/' + \
              x.split('/')[-1]
        print(cmd)
        call(cmd.split())


def replace_local_path(path):
    """ replace local path with remote path """
    new_path = config.REMOTE_PATH + path[len(config.RESOURCES_PATH):]
    return new_path


def update_matfac():
    """ run matrix factorization """
    mf.update_results()
