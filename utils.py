import re
from urllib2 import unquote
import httplib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import glob
import os
import config
import dblib
import csv

res_path = config.RESOURCES_PATH

PUNCS_WE_DONT_LIKE = "[],.()<>'/?;:\"&"


def is_doi(str):
    """
    check if a string is a valid DOI
    @param str: str to check
    @type str: str
    @return: True if DOI
    @rtype: bool
    """
    doi_regex = re.compile('\\b(10[.][0-9]{4,}(?:[.][0-9]+)*\/(?:(?!["&\'<>])\S)+)\\b')
    return True if doi_regex.match(str) else False


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i + n]


def RepresentsInt(s):
    """
    check if s represents an int
    @param s: str
    @type s: str
    @return: bool
    @rtype: bool
    """
    try:
        int(s)
        return True
    except ValueError:
        return False


def patch_http_response_read(func):
    """
    fix broken file download
    @param func:
    @return:
    """

    def inner(*args):
        try:
            return func(*args)
        except httplib.IncompleteRead, e:
            return e.partial

    return inner


def requests_retry_session(
        retries=3,
        backoff_factor=0.3,
        session=None,
):
    """ used to retry requests upon failure """
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def retry_get(base_url, params):
    """ wrapper for requests.get() that retries upon error, and catches thrown errors after 3 failed retries """
    try:
        r = requests_retry_session().get(base_url, params=params)
        r.raise_for_status()
    except requests.exceptions.HTTPError as errh:
        print ("Http Error:", errh)
        return None
    except requests.exceptions.ConnectionError as errc:
        print ("Error Connecting:", errc)
        return None
    except requests.exceptions.Timeout as errt:
        print ("Timeout Error:", errt)
        return None
    except requests.exceptions.RequestException as err:
        print ("OOps: Something Else", err)
        return None
    return r


def most_recent_tfidf():
    list_of_files = glob.glob(
        res_path + '/models/tfidf/tfidf_matrix_*.npz')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def most_recent_tsne():
    list_of_files = glob.glob(
        res_path + '/models/tsne/tsne_matrix_*.npy')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def most_recent_tsne_img():
    list_of_files = glob.glob(
        res_path + '/app/static/images/tsne*.png')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def most_recent_tfidf_labels():
    list_of_files = glob.glob(
        res_path + '/models/tfidf/nct_ids*.pickle')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def most_recent_tfidf_vec():
    list_of_files = glob.glob(
        res_path + '/models/tfidf/vectorizer*.pickle')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def most_recent_trialsxreviews():
    list_of_files = glob.glob(
        res_path + '/models/matfac/trials_x_reviews*.npz')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def most_recent_matfac():
    list_of_files = glob.glob(
        res_path + '/models/matfac/matfac_results_*.npy')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def most_recent_matfac_pmids():
    list_of_files = glob.glob(
        res_path + '/models/matfac/pmid_cols_*.pickle')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def most_recent_matfac_nctids():
    list_of_files = glob.glob(
        res_path + '/models/matfac/nct_rows_*.pickle')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file

def export_rt_links():
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("SELECT review_id, nct_id, upvotes-downvotes, relationship, verified from review_rtrial;")
    trials = cur.fetchall()
    with open('complete_review_matrix.csv','w') as complete, open('review_trial_matrix.csv','w') as all:
        writer1 = csv.writer(complete)
        writer2 = csv.writer(all)
        writer1.writerow(['review_id','nct_id','net_votes','relationship'])
        writer2.writerow(['review_id','nct_id','net_votes','relationship'])
        for row in trials:
            writer2.writerow(list(row)[:4])
            if row[4]:
                writer1.writerow(list(row)[:4])

