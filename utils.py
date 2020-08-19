import re
from urllib.parse import unquote
from http import client as httplib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import glob
import os
import config
import dblib
import csv
from dateutil.parser import parse
import math
import random
import numpy

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
    for i in range(0, len(l), n):
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
        except httplib.IncompleteRead as e:
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


def sample_floats(low, high, k=1):
    """ Return a k-length list of unique random floats
        in the range of low <= x <= high
    """
    result = []
    seen = set()
    for i in range(k):
        x = random.uniform(low, high)
        while x in seen:
            x = random.uniform(low, high)
        seen.add(x)
        result.append(x)
    return result


def get_sorted(args, list):
    return numpy.array(list)[args].tolist()


def trials_to_plotdata(trials):
    dates = []
    colours = []
    normalised_enrollment = []
    verified = []
    alpha_vals = []
    ids = []
    enrollment = []
    enrolls = [x['enrollment'] for x in trials if x['completion_date'] and x['enrollment'] and (
            x['sum'] > 1 or x['verified'] or x['relationship'] == 'included')]
    max_enrollment = max(enrolls) if len(enrolls) else 0
    for x in trials:
        if x['completion_date'] and x['enrollment'] and (
                x['sum'] > 1 or x['verified'] or x['relationship'] == 'included'):
            date = parse(x['completion_date'], fuzzy=True)
            dates.append(date.strftime('%Y-%m-%d'))
            if x['relationship'] == 'included':
                colours.append([125, 0, 255])
                alpha_vals.append(0.6)
            elif x['overall_status'] in ('Completed', 'Available'):
                colours.append([0, 255, 0])
                alpha_vals.append(0.6)
            elif x['overall_status'] in ('Suspended', 'Terminated', 'Withheld', 'Withdrawn'):
                colours.append([255, 0, 0])
                alpha_vals.append(0.4)
            elif x['overall_status'] in ('Unknown status', 'No longer available', 'Temporarily not available'):
                colours.append([240, 173, 78])
                alpha_vals.append(0.4)
            elif x['overall_status'] in (
                    'Not yet recruiting', 'Approved for marketing', 'Enrolling by invitation', 'Active, not recruiting',
                    'Enrolling',
                    'Recruiting'):
                colours.append([143, 248, 255])
                alpha_vals.append(0.4)
            normalised_enrollment.append(math.sqrt(float(x['enrollment']) / float(max_enrollment)) * 1999999999999)
            enrollment.append(x['enrollment'])
            verified.append(x['verified'])
            ids.append(x['nct_id'])
    sorted_enrollment = numpy.argsort(normalised_enrollment)[::-1]
    res = {'dates': get_sorted(sorted_enrollment, dates), 'colours': get_sorted(sorted_enrollment, colours),
           'enrollment': get_sorted(sorted_enrollment, normalised_enrollment),
           'verified': get_sorted(sorted_enrollment, verified),
           'y_vals': sample_floats(2000000000000, 6000000000000, len(dates)),
           'alpha': get_sorted(sorted_enrollment, alpha_vals),
           'titles': get_sorted(sorted_enrollment, ids), 'real_enrollment': get_sorted(sorted_enrollment, enrollment)}
    return res


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
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file


def most_recent_tsne():
    list_of_files = glob.glob(
        res_path + '/models/tsne/tsne_matrix_*.npy')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file


def most_recent_tsne_img():
    list_of_files = glob.glob(
        res_path + '/app/static/images/tsne*.png')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file


def most_recent_tfidf_labels():
    list_of_files = glob.glob(
        res_path + '/models/tfidf/nct_ids*.pickle')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file


def most_recent_tfidf_vec():
    list_of_files = glob.glob(
        res_path + '/models/tfidf/vectorizer*.pickle')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file


def most_recent_trialsxreviews():
    list_of_files = glob.glob(
        res_path + '/models/matfac/trials_x_reviews*.npz')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file


def most_recent_matfac():
    list_of_files = glob.glob(
        res_path + '/models/matfac/matfac_results_*.npy')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file


def most_recent_matfac_pmids():
    list_of_files = glob.glob(
        res_path + '/models/matfac/pmid_cols_*.pickle')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file


def most_recent_matfac_nctids():
    list_of_files = glob.glob(
        res_path + '/models/matfac/nct_rows_*.pickle')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file


def export_rt_links():
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("SELECT review_id, nct_id, upvotes-downvotes, relationship, verified from review_rtrial;")
    trials = cur.fetchall()
    with open('complete_review_matrix.csv', 'w') as complete, open('review_trial_matrix.csv', 'w') as all:
        writer1 = csv.writer(complete)
        writer2 = csv.writer(all)
        writer1.writerow(['review_id', 'nct_id', 'net_votes', 'relationship'])
        writer2.writerow(['review_id', 'nct_id', 'net_votes', 'relationship'])
        for row in trials:
            writer2.writerow(list(row)[:4])
            if row[4]:
                writer1.writerow(list(row)[:4])
