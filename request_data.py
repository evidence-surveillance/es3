# -*- coding: utf-8 -*-
import json
import config
import utils
import crud

eutils_key = config.EUTILS_KEY
eutils_email = config.EUTILS_EMAIL
eutils_tool = config.EUTILS_TOOL


def advanced_search(search_str):
    """ search pubmed for a review or meta-analysis containing search_str in the title or abstract & return matching
    PMIDs """
    base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
    r = utils.requests_retry_session().get(base_url,
                                           params={'db': 'pubmed',
                                                   'term': '(systematic review[ti] OR meta analysis[ti]) AND ' + search_str + '[tiab]',
                                                   'format': 'json',
                                                   'retmax': 300000,
                                                   'email': eutils_email,
                                                   'tool': eutils_tool, 'api_key': eutils_key})
    json = r.json()
    pmids = json['esearchresult']['idlist']
    if pmids:
        matches = crud.get_reviews_with_ids(pmids)
        print matches
        return matches if matches else None
    return None


def pubmed_convert_id(known_id, desired_id):
    """
    convert from PMID to DOI or vice versa
    @param known_id: ID we have
    @param desired_id: type of ID we desire (PMID or DOI)
    @return: desired ID or None
    """
    base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
    r = utils.requests_retry_session().get(base_url,
                                           params={'ids': known_id, 'format': 'json', 'email': eutils_email,
                                                   'tool': eutils_tool, 'api_key': eutils_key})
    if r.status_code == 200:
        r = json.loads(r.text)
        if desired_id in r['records'][0]:
            return r['records'][0][desired_id]
        else:
            return None
    else:
        return None


def batch_pmids_for_citation(citations, debug=False):
    """
    returns list of pmids for batch of citations. requires at least 3/5 of these keyword arguments:
        jtitle or journal (journal title)
        year or date
        volume
        spage or first_page (starting page / first page)
        aulast (first author's last name) or author1_first_lastfm (as produced by PubMedArticle class)
    (Note that these arguments were made to match the tokens that arise from CrossRef's result['slugs'].)
    Strings submitted for journal/jtitle will be run through utils.remove_chars to deal with HTML-
    encoded characters and to remove punctuation.
    @param citations: list of citation objects obtained from Crossref 'references'
    @param debug:
    @return: list of resolved PMIDs
    """
    base_uri = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/ecitmatch.cgi?'
    params = {'db': 'pubmed', 'retmode': 'xml', 'bdata': ''}
    joined = []
    for citation in citations:
        citation = utils.lowercase_keys(citation)
        # accept 'journal-title' key from CrossRef
        journal_title = utils.remove_chars(
            utils.kpick(citation, options=['jtitle', 'journal', 'journal_title', 'journal-title'], default=''),
            urldecode=True)
        author_name = utils._reduce_author_string(utils.kpick(citation,
                                                              options=['aulast', 'author1_last_fm', 'author',
                                                                       'authors'],
                                                              default=''))
        # accept 'first-page' key from CrossRef 'references' list items
        first_page = utils.kpick(citation, options=['spage', 'first_page', 'first-page'], default='')
        year = utils.kpick(citation, options=['year', 'date', 'pdat'], default='')
        volume = utils.kpick(citation, options=['volume'], default='')
        if '(' in volume:
            volume = ''

        inp_dict = {'journal_title': journal_title.encode('utf-8', 'ignore').decode('utf-8'),
                    'year': str(year),
                    'volume': str(volume),
                    'first_page': str(first_page),
                    'author_name': author_name.encode('utf-8', 'ignore').decode('utf-8'),
                    }
        if debug:
            print('Submitted to pmids_for_citation: %r' % inp_dict)

        # clean up any "n/a" values.  eutils doesn't understand them.
        for k in inp_dict:
            if inp_dict[k].lower() == 'n/a':
                inp_dict[k] = ''
        joined.append('{journal_title}|{year}|{volume}|{first_page}|{author_name}|'.format(**inp_dict))
    if debug:
        for j in joined:
            print(j)
    pmids = []
    while True:
        params['bdata'] = ''
        while len(params['bdata']) < 1900 and len(joined) > 0:
            params['bdata'] += joined[-1] + '\r'
            joined.pop()
        req = utils.retry_get(base_uri, params=params)
        if not req:
            return None
        if req.status_code == 200:
            content = req.text
            if debug:
                print(content)
            for item in content.split('\n'):
                if item.strip():
                    pmid = item.split('|')[-1]
                    pmids.append(pmid.strip())
        if len(joined) == 0:
            break
    return pmids
