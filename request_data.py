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
        print(matches)
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
