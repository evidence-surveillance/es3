import re
from urllib2 import unquote
import httplib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import glob
import os
import config

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


# original code from metapub https://bitbucket.org/metapub/metapub/src/2fc6c99c7ce3ebd38a44f4f45fa0bb6e78b4d5c9/metapub/pubmedfetcher.py?at=default&fileviewer=file-view-default
def _reduce_author_string(author_string):
    """ attempt to extract authors from a string"""
    # try splitting by commas
    authors = author_string.split(',')
    if len(authors) < 2:
        # try splitting by semicolons
        authors = author_string.split(';')

    author1 = authors[0]
    # presume last name is at the end of the string
    return author1.split(' ')[-1]


# original code from metapub https://bitbucket.org/metapub/metapub/src/2fc6c99c7ce3ebd38a44f4f45fa0bb6e78b4d5c9/metapub/utils.py?at=default&fileviewer=file-view-default
def remove_chars(inp, chars=PUNCS_WE_DONT_LIKE, urldecode=False):
    """ Remove target characters from input string.
    :param inp: (str)
    :param chars: (str) characters to remove [default: utils.PUNCS_WE_DONT_LIKE]
    :param urldecode: (bool) whether to first urldecode the input string [default: False]
    """
    if urldecode:
        inp = unquote(inp)

    for char in chars:
        inp = inp.replace(char, '')
    return inp


# original code from metapub https://bitbucket.org/metapub/metapub/src/2fc6c99c7ce3ebd38a44f4f45fa0bb6e78b4d5c9/metapub/utils.py?at=default&fileviewer=file-view-default
def lowercase_keys(dct):
    """ Takes an input dictionary, returns dictionary with all keys lowercased. """
    result = {}
    for key, value in list(dct.items()):
        result[key.lower()] = value
    return result


# original code from metapub https://bitbucket.org/metapub/metapub/src/2fc6c99c7ce3ebd38a44f4f45fa0bb6e78b4d5c9/metapub/utils.py?at=default&fileviewer=file-view-default
def kpick(args, options, default=None):
    """ return value in args that matches any of the keys in options """
    for opt in options:
        if args.get(opt, None):
            return args[opt]
    return default


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
