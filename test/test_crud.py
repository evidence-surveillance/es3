import sys
import unittest
import testing.postgresql
import psycopg2
import mock
from mock import patch
from eutils import Client

sys.path.append("..")
import crud
import dblib


def handler(postgresql):
    with open('data/srss.sql', 'r') as myfile:
        data = myfile.read().replace('\n', '')
    conn = psycopg2.connect(**postgresql.dsn())
    cursor = conn.cursor()
    cursor.execute(data)
    conn.commit()
    for user in ['testuser_1', 'testuser_2']:
        cursor.execute("INSERT INTO users(user_name, nickname) VALUES (%s,%s);", (user, user))
    conn.commit()
    cursor.execute("INSERT INTO USERS(user_name, nickname, id) VALUES (%s, %s, %s);",
                   ('cochranebot', 'cochranebot', 17))
    conn.commit()
    conn.close()


Postgresql = testing.postgresql.PostgresqlFactory(cache_initialized_db=True,
                                                  on_initialized=handler)


class TestCrud(unittest.TestCase):

    def mock_conn(self, VERBOSE):
        return psycopg2.connect(**self.postgresql.dsn())

    def setUp(self):
        self.postgresql = Postgresql()
        self.patcher1 = patch.object(dblib, 'create_con', self.mock_conn)
        self.MockClass1 = self.patcher1.start()

    def test_pubmedarticle_to_db(self):
        ec = Client()
        ids = [28616955,28800192,28797191]
        for id in ids:
            self.assertIsNone(crud.review_medtadata_db(id))
        article = ec.efetch(db='pubmed',id=ids)
        for i,a in enumerate(article):
            crud.pubmedarticle_to_db(a,'systematic_reviews')
            self.assertIsNotNone(crud.review_medtadata_db(ids[i]))
            self.assertEqual(crud.review_medtadata_db(ids[i])['title'], a.title)
            self.assertEqual(crud.review_medtadata_db(ids[i])['review_id'], int(a.pmid))
            self.assertEqual(crud.review_medtadata_db(ids[i])['abstract'], a.abstract)
            self.assertEqual(crud.review_medtadata_db(ids[i])['source'], a.jrnl)
            self.assertEqual(crud.review_medtadata_db(ids[i])['doi'], a.doi)
            self.assertEqual(crud.review_medtadata_db(ids[i])['publish_date'], int(a.year))
            self.assertEqual(crud.review_medtadata_db(ids[i])['authors'], ', '.join(a.authors))
            self.assertEqual(crud.review_medtadata_db(ids[i])['included_complete'], False)
            self.assertEqual(crud.review_medtadata_db(ids[i])['verified_review'], None)

    def test_review_lock_status(self):
        ec = Client()
        ids = [28616955,28800192,28797191]
        for id in ids:
            self.assertIsNone(crud.review_medtadata_db(id))
        article = ec.efetch(db='pubmed', id=ids)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
            self.assertEqual(crud.review_lock_status(ids[i]), False)
            crud.complete_studies(ids[i],True)
            self.assertEqual(crud.review_lock_status(ids[i]), True)
            crud.complete_studies(ids[i],False)
            self.assertEqual(crud.review_lock_status(ids[i]), False)

    def test_get_locked(self):
        ec = Client()
        ids = [28569363,29202845,28933578]
        for id in ids:
            self.assertIsNone(crud.review_medtadata_db(id))
        article = ec.efetch(db='pubmed', id=ids)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        self.assertIsNone(crud.get_locked())
        crud.complete_studies(ids[0],True)
        self.assertEqual(crud.get_locked(),[ids[0]])
        crud.complete_studies(ids[1], True)
        self.assertEqual(crud.get_locked(), [ids[0],ids[1]])
        crud.complete_studies(ids[2], True)
        self.assertEqual(crud.get_locked(), [ids[0],ids[1],ids[2]])
        crud.complete_studies(ids[1], False)
        self.assertEqual(crud.get_locked(), [ids[0],ids[2]])

    def test_review_publication(self):
        ec = Client()
        trialpub_ids = [29871025,29859785,29866619]
        review_ids= [28775712,28549125,29929949]
        trialpubs = ec.efetch(db='pubmed', id=trialpub_ids)
        reviews = ec.efetch(db='pubmed', id=review_ids)
        for i, a in enumerate(trialpubs):
            crud.pubmedarticle_to_db(a, 'trial_publications')
        for i, a in enumerate(reviews):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
            crud.review_publication(a.pmid,trialpub_ids[i],1)
            conn= self.mock_conn(True)
            cur = conn.cursor()
            cur.execute("SELECT trialpub_id from review_trialpubs where review_id = %s;",(a.pmid,))
            trialpub = cur.fetchone()
            self.assertEqual(trialpub[0], trialpub_ids[i])
            conn.close()

    def test_update_record(self):
        nct_ids=['NCT02317328','NCT02317874','NCT02317887','NCT02330055']
        for id in nct_ids:
            xml = crud.get_trial_xml(id)
            crud.update_record(xml)
        conn = self.mock_conn(True)
        cur = conn.cursor()
        cur.execute("SELECT nct_id from tregistry_entries where nct_id in %s;",(tuple(nct_ids),))
        res = cur.fetchall()
        self.assertEqual([nct[0] for nct in res], nct_ids)
        conn.close()

    def test_pulication_trial(self):
        ec = Client()
        trialpub_ids = [29871025, 29859785, 29866619]
        nct_ids=['NCT02317328','NCT02317874','NCT02317887','NCT02330055']
        trialpubs = ec.efetch(db='pubmed', id=trialpub_ids)
        for i, a in enumerate(trialpubs):
            crud.pubmedarticle_to_db(a, 'trial_publications')
            self.assertIsNone(crud.linked_nctids(a.pmid))
            for nct_id in nct_ids:
                crud.publication_trial(a.pmid,nct_id,2)
            self.assertEqual(crud.linked_nctids(a.pmid), nct_ids)



    def test_add_trial_to_locked(self):
        ec = Client()
        ids = [28616955, 28800192, 28797191]
        nct_ids=['NCT00195624','NCT00200889','NCT00207688']
        test_nct = 'NCT00695409'
        for id in ids:
            self.assertIsNone(crud.review_medtadata_db(id))
        article = ec.efetch(db='pubmed', id=ids)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
            crud.review_trial(ids[i],nct_ids[i],False, 'included','testuser_1',1,'up')
            crud.complete_studies(ids[i],True)
            crud.review_trial(ids[i],test_nct,False, 'included','testuser_1',1,'up')
            self.assertIsNone(crud.check_existing_review_trial(ids[i],test_nct))
            crud.complete_studies(ids[i],False)
            crud.review_trial(ids[i],test_nct,False, 'included','testuser_1',1,'up')
            self.assertIsNotNone(crud.check_existing_review_trial(ids[i],test_nct))

    def test_review_trial(self):
        ec = Client()
        id = 28616955
        nct_ids=['NCT00195624','NCT00200889','NCT00207688']
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        self.assertEqual(len(crud.get_review_trials_fast(id)['reg_trials']), 0)
        # trial is inserted with correct values
        crud.review_trial(id, nct_ids[0],False,'relevant','testuser_1',1)
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] == nct_ids[0]:
                self.assertEqual(trials[i]['nct_id'], nct_ids[0])
                self.assertEqual(trials[i]['upvotes'], 1)
                self.assertEqual(trials[i]['downvotes'], 0)
                self.assertEqual(trials[i]['voters'], 'testuser_1')
                self.assertEqual(trials[i]['verified'], False)
                self.assertEqual(trials[i]['relationship'], 'relevant')
        # when the trial is added again by another user, it should recieve an upvote
        crud.review_trial(id, nct_ids[0],False,'relevant','testuser_2',2)
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] == nct_ids[0]:
                self.assertEqual(trials[i]['nct_id'], nct_ids[0])
                self.assertEqual(trials[i]['upvotes'], 2)
                self.assertEqual(set(trials[i]['voters'].split(', ')), {'testuser_1', 'testuser_2'})
                self.assertEqual(trials[i]['downvotes'], 0)
                self.assertEqual(trials[i]['verified'], False)
                self.assertEqual(trials[i]['relationship'], 'relevant')
        # adding an existing trial from the relevant column as included will move it
        crud.review_trial(id, nct_ids[0], False, 'included', 'testuser_2', 2)
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] == nct_ids[0]:
                self.assertEqual(trials[i]['nct_id'], nct_ids[0])
                self.assertEqual(trials[i]['upvotes'], 2)
                self.assertEqual(set(trials[i]['voters'].split(', ')), {'testuser_1', 'testuser_2'})
                self.assertEqual(trials[i]['downvotes'], 0)
                self.assertEqual(trials[i]['verified'], False)
                self.assertEqual(trials[i]['relationship'], 'included')
        # test included trial
        crud.review_trial(id, nct_ids[1],False,'included','testuser_2',2)
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] == nct_ids[1]:
                self.assertEqual(trials[i]['nct_id'], nct_ids[1])
                self.assertEqual(trials[i]['upvotes'], 1)
                self.assertEqual(trials[i]['voters'], 'testuser_2')
                self.assertEqual(trials[i]['downvotes'], 0)
                self.assertEqual(trials[i]['verified'], False)
                self.assertEqual(trials[i]['relationship'], 'included')
        # trying to insert a relevant trial when it's already included will give a vote but not move the trial
        crud.review_trial(id, nct_ids[1],False,'relevant','testuser_1',1)
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] == nct_ids[1]:
                self.assertEqual(trials[i]['nct_id'], nct_ids[1])
                self.assertEqual(trials[i]['upvotes'], 2)
                self.assertEqual(set(trials[i]['voters'].split(', ')), {'testuser_1', 'testuser_2'})
                self.assertEqual(trials[i]['downvotes'], 0)
                self.assertEqual(trials[i]['verified'], False)
                self.assertEqual(trials[i]['relationship'], 'included')
        # except for user_id 17 which can move included to relevant
        crud.review_trial(id, nct_ids[1],False,'relevant','cochranebot',17, vote_type='down')
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] == nct_ids[1]:
                self.assertEqual(trials[i]['nct_id'], nct_ids[1])
                self.assertEqual(trials[i]['upvotes'], 2)
                self.assertEqual(set(trials[i]['voters'].split(', ')), {'cochranebot', 'testuser_1', 'testuser_2'})
                self.assertEqual(trials[i]['downvotes'], 1)
                self.assertEqual(trials[i]['verified'], False)
                self.assertEqual(trials[i]['relationship'], 'relevant')
        # if the review is locked and the trial is included, allow a vote
        crud.review_trial(id, nct_ids[2],False,'included','testuser_1',1)
        crud.complete_studies(id,True)
        crud.review_trial(id, nct_ids[2],False,'included','testuser_2',2)
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] == nct_ids[2]:
                self.assertEqual(trials[i]['nct_id'], nct_ids[2])
                self.assertEqual(trials[i]['upvotes'], 2)
                self.assertEqual(set(trials[i]['voters'].split(', ')), {'testuser_1', 'testuser_2'})
                self.assertEqual(trials[i]['downvotes'], 0)
                self.assertEqual(trials[i]['verified'], True)
                self.assertEqual(trials[i]['relationship'], 'included')

    def test_change_relationship(self):
        ec = Client()
        id = 28934560
        nct_id = 'NCT00678431'
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        crud.review_trial(id, nct_id, False,'relevant','testuser_2',2)
        link_id = crud.check_existing_review_trial(id,nct_id)
        crud.change_relationship(link_id[0],'included')
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] == nct_id:
                self.assertEqual(trials[i]['nct_id'], nct_id)
                self.assertEqual(trials[i]['upvotes'], 1)
                self.assertEqual(set(trials[i]['voters'].split(', ')), {'testuser_2'})
                self.assertEqual(trials[i]['downvotes'], 0)
                self.assertEqual(trials[i]['verified'], False)
                self.assertEqual(trials[i]['relationship'], 'included')

    def test_check_existing_review_trial(self):
        ec = Client()
        id = 28934560
        nct_id = 'NCT00678431'
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        crud.review_trial(id, nct_id, False, 'relevant', 'testuser_2', 2)
        link = crud.check_existing_review_trial(id, nct_id)
        self.assertIsNotNone(link)
        no_link = crud.check_existing_review_trial(5464824, 'NCT00000000')
        self.assertIsNone(no_link)

    def test_get_link_id(self):
        ec = Client()
        id = 28934560
        nct_id = 'NCT00678431'
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        crud.review_trial(id, nct_id, False, 'relevant', 'testuser_2', 2)
        link_id = crud.get_link_id(nct_id,id)
        self.assertIsNotNone(link_id)
        no_link = crud.get_link_id('NCT02064179',28931939)
        self.assertIsNone(no_link)

    def test_vote(self):
        ec = Client()
        id = 28934560
        nct_id = 'NCT00678431'
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        crud.review_trial(id, nct_id, False, 'relevant', 'testuser_2', 2)
        link_id = crud.get_link_id(nct_id,id)
        crud.vote(link_id,'up',1)
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] == nct_id:
                self.assertEqual(trials[i]['nct_id'], nct_id)
                self.assertEqual(trials[i]['upvotes'], 2)
                self.assertEqual(set(trials[i]['voters'].split(', ')), {'testuser_2','testuser_1'})
                self.assertEqual(trials[i]['downvotes'], 0)
                self.assertEqual(trials[i]['verified'], False)
                self.assertEqual(trials[i]['relationship'], 'relevant')

    def test_convert_id(self):
        ec = Client()
        id = 28795402
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        self.assertEqual(crud.convert_id(id,'doi'),'10.1002/ijc.30922')
        self.assertEqual(crud.convert_id('10.1002/ijc.30922','pmid'),id)
        article = ec.efetch(db='pubmed', id=24829965)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        self.assertEqual(crud.convert_id(24829965, 'doi'), None)

    def test_complete_studies(self):
        ec = Client()
        id = 28795402
        ncts = ['NCT00031265', 'NCT02199847', 'NCT00902980', 'NCT01266824', 'NCT03418909']
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        for n in ncts[:3]:
            crud.review_trial(id, n, False, 'included', 'testuser_1', 1)
        for n in ncts[3:]:
            crud.review_trial(id, n, False, 'relevant', 'testuser_1', 1)
        crud.complete_studies(id, True)
        metadata = crud.review_medtadata_db(id)
        self.assertEqual(metadata['included_complete'], True)
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] in ncts[:3]:
                self.assertEqual(trials[i]['verified'], True)
                self.assertEqual(trials[i]['relationship'], 'included')
            if t['nct_id'] in ncts[3:]:
                self.assertEqual(trials[i]['verified'], False)
                self.assertEqual(trials[i]['relationship'], 'relevant')
        crud.complete_studies(id, False)
        trials = crud.get_review_trials_fast(id)['reg_trials']
        for i, t in enumerate(trials):
            if t['nct_id'] in ncts[:3]:
                self.assertEqual(trials[i]['verified'], False)
                self.assertEqual(trials[i]['relationship'], 'included')

    def test_get_review_trials_fast(self):
        ec = Client()
        id = 28795402
        ncts = ['NCT00031265', 'NCT02199847', 'NCT00902980', 'NCT01266824', 'NCT03418909']
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        for n in ncts:
            crud.review_trial(id, n, False, 'included', 'testuser_1', 1)
        trials = crud.get_review_trials_fast(id)['reg_trials']
        retrieved_ncts = [t['nct_id'] for t in trials]
        for n in ncts:
            self.assertTrue(n in retrieved_ncts)



    def tearDown(self):
        self.patcher1.stop()
        self.postgresql.stop()


if __name__ == '__main__':
    unittest.main()
