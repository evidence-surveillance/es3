import sys
import unittest
import testing.postgresql
import psycopg2
from mock import patch
from eutils import Client
import collections

sys.path.append("..")
import bot
import dblib
import crud
import csv


def handler(postgresql):
    """ init test database """
    with open('data/srss.sql', 'r') as myfile:
        data = myfile.read().replace('\n', '')
    conn = psycopg2.connect(**postgresql.dsn())
    cursor = conn.cursor()
    cursor.execute(data)
    conn.commit()
    for i, user in enumerate(['testuser_1', 'testuser_2']):
        cursor.execute("INSERT INTO users(user_name, nickname,id) VALUES (%s,%s,%s);", (user, user,i+20))
    conn.commit()
    conn.close()


Postgresql = testing.postgresql.PostgresqlFactory(cache_initialized_db=True,
                                                  on_initialized=handler)


class TestBot(unittest.TestCase):

    def mock_conn(self, VERBOSE):
        """ patch so that all connections are made to test database """
        return psycopg2.connect(**self.postgresql.dsn())

    def setUp(self):
        self.postgresql = Postgresql()
        self.patcher1 = patch.object(dblib, 'create_con', self.mock_conn)
        self.MockClass1 = self.patcher1.start()

    def test_cochranebot(self):
        """ verify that cochranebot is retrieving all included, excluded and relevant trials
        tested against manually gathered data """
        ec = Client()
        with open('data/trialpubs_rtrial.csv', 'rb') as csvfile:
            spamreader = csv.reader(csvfile)
            for row in spamreader:
                article = ec.efetch(db='pubmed', id=row[1])
                for a in article:
                    crud.pubmedarticle_to_db(a, 'trial_publications')
                crud.publication_trial(row[1], row[0], 1)
        ec = Client()
        id = 28453187
        doi = '10.1002/14651858.CD011748.pub2'
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        bot.cochranebot(doi, id)
        conn = psycopg2.connect(**self.postgresql.dsn())
        cursor = conn.cursor()
        cursor.execute("SELECT nct_id from review_rtrial where relationship = 'included' and review_id = %s;", (id,))
        ncts = set(zip(*cursor.fetchall())[0])
        self.assertEqual(ncts,
                         {'NCT01516879', 'NCT01644188', 'NCT01507831', 'NCT01439880', 'NCT01854918', 'NCT01592240',
                          'NCT01644175',
                          'NCT01730040', 'NCT01623115', 'NCT01709500', 'NCT01709513'})
        bot.cochrane_ongoing_excluded(doi, id)
        cursor.execute("SELECT nct_id from review_rtrial where relationship = 'relevant' and review_id = %s;", (id,))
        ncts = set(zip(*cursor.fetchall())[0])
        self.assertEqual(ncts,
                         {'NCT02729025', 'NCT02207634', 'NCT02392559', 'NCT02833844', 'NCT02642159', 'NCT01663402',
                          'NCT01624142'})

    def test_cochranebot_1(self):
        ec = Client()
        with open('data/trialpubs_rtrial_2.csv', 'rb') as csvfile:
            spamreader = csv.reader(csvfile)
            for row in spamreader:
                article = ec.efetch(db='pubmed', id=row[1])
                for a in article:
                    crud.pubmedarticle_to_db(a, 'trial_publications')
                crud.publication_trial(row[1], row[0], 1)
        ec = Client()
        doi = '10.1002/14651858.CD011768.pub2'
        id = 29775501
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        bot.cochranebot(doi, id)
        conn = psycopg2.connect(**self.postgresql.dsn())
        cursor = conn.cursor()
        cursor.execute("SELECT nct_id from review_rtrial where relationship = 'included' and review_id = %s;", (id,))
        ncts = set(zip(*cursor.fetchall())[0])
        self.assertEqual(ncts,
                         {'NCT00910377', 'NCT00629629', 'NCT01925664'})
        bot.cochrane_ongoing_excluded(doi, id)
        cursor.execute("SELECT nct_id from review_rtrial where relationship = 'relevant' and review_id = %s;", (id,))
        ncts = set(zip(*cursor.fetchall())[0])
        self.assertEqual(ncts,
                         {'NCT02249754', 'NCT01825226', 'NCT00892983', 'NCT02052518', 'NCT00892983', 'NCT01824940',
                          'NCT01167270', 'NCT00715936', 'NCT01678716', 'NCT01167270', 'NCT00359242', 'NCT00310726',
                          'NCT01272492', 'NCT02244424'})

    def test_cochranebot_2(self):
        ec = Client()
        with open('data/trialpubs_rtrial_3.csv', 'rb') as csvfile:
            spamreader = csv.reader(csvfile)
            for row in spamreader:
                article = ec.efetch(db='pubmed', id=row[1])
                for a in article:
                    crud.pubmedarticle_to_db(a, 'trial_publications')
                crud.publication_trial(row[1], row[0], 1)
        ec = Client()
        doi = '10.1002/14651858.CD009728.pub4'
        id = 29499084
        article = ec.efetch(db='pubmed', id=id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        bot.cochranebot(doi, id)
        conn = psycopg2.connect(**self.postgresql.dsn())
        cursor = conn.cursor()
        cursor.execute("SELECT nct_id from review_rtrial where relationship = 'included' and review_id = %s;", (id,))
        ncts = set(zip(*cursor.fetchall())[0])
        self.assertEqual(ncts,
                         {'NCT00108901', 'NCT01704768', 'NCT01457794', 'NCT02132494', 'NCT01971827', 'NCT02439827',
                          'NCT01574352', 'NCT02132494'})
        bot.cochrane_ongoing_excluded(doi, id)
        cursor.execute("SELECT nct_id from review_rtrial where relationship = 'relevant' and review_id = %s;", (id,))
        ncts = set(zip(*cursor.fetchall())[0])
        self.assertEqual(ncts,
                         {'NCT00685555', 'NCT00674544', 'NCT00000615', 'NCT00674544', 'NCT01192100', 'NCT01642836',
                          'NCT01334359', 'NCT00994084',
                          'NCT01737658', 'NCT02873715', 'NCT02972164', 'NCT01642836',
                          'NCT01699295', 'NCT01192100', 'NCT02043626', 'NCT02122224'})

    @patch.object(bot, 'check_trialpubs_nctids')
    def test_crossrefbot(self, mock_method):
        ec = Client()
        with open('data/trialpubs_rtrial_4.csv', 'rb') as csvfile:
            spamreader = csv.reader(csvfile)
            for row in spamreader:
                article = ec.efetch(db='pubmed', id=row[1])
                for a in article:
                    crud.pubmedarticle_to_db(a, 'trial_publications')
                crud.publication_trial(row[1], row[0], 1)
        article = ec.efetch(db='pubmed', id=29865058)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        pmids = {29037101, 28735855, 12214118, 28697569, 15380154, 26294005, 21539488, 23680940, 23720230, 24164735,
                 25599006, 25681666, 26086182, 21514250, 19621072, 25961184, 26384466, 24134194, 24495355, 25996285,
                 26265727, 24374288, 25771249, 28359749, 24045855, 24880197, 26640437, 26682691, 27895474, 23796946,
                 25264972, 24507770, 26305649, 25565485, 25891115, 26890759, 26867200, 27529771, 26812512, 24899709,
                 28054939, 27102361, 25344629, 24617349, 25733635, 25733639, 29141041, 25391305, 26135351, 24938711,
                 28319243, 15205295, 20858954, 25352453, 26213339, 25414047, 24334113, 19643207, 28676015, 27570766,
                 17569205, 25002849, 26690214, 18709889, 22232016, 16210710, 22122400, 19204158, 21506929, 22449789,
                 22794138, 27738491, 19641487, 9149659, 28213052, 12663275, 10374811, 17101822, 22371413, 28861684,
                 26652155, 16614482, 27624276, 28925645, 22170358, 25061569, 28980404, 26740832, 26286890, 28448083,
                 29562543, 25928696, 26253520, 26003546, 20810976}
        content = collections.namedtuple('ids', ['pmids', 'nctids'])
        mock_method.return_value = content(list(pmids), None)
        nct_ids = {'NCT01562392', 'NCT00672685', 'NCT01746303', 'NCT00000611', 'NCT00345176', 'NCT01041989',
                   'NCT01312610', 'NCT00385723', 'NCT01672359', 'NCT01109628', 'NCT01110369'}
        bot.check_citations(29865058)
        conn = psycopg2.connect(**self.postgresql.dsn())
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT trialpub_id from review_trialpubs where review_id = %s;", (29865058,))
        db_ids = cursor.fetchall()
        pmids1 = set([int(pmid[0]) for pmid in db_ids])
        self.assertEqual(pmids1,
                         {29141041, 28359749, 26812512, 26384466, 26305649, 25771249, 25733635, 25264972, 24495355,
                          24374288})
        cursor.execute("SELECT DISTINCT nct_id from review_rtrial where review_id = %s;", (29865058,))
        db_ids = cursor.fetchall()
        conn.close()
        nct_ids_1 = set([nct[0] for nct in db_ids])
        self.assertEqual(nct_ids, nct_ids_1)

    @patch.object(bot, 'check_trialpubs_nctids')
    def test_crossrefbot_2(self, mock_method):
        """ verify that crossrefbot is retrieving all trials with automatic links to studies referenced by a review
         tested against manually gathered data """
        r_id = 27634736
        ec = Client()
        with open('data/trialpubs_rtrial_5.csv', 'rb') as csvfile:
            spamreader = csv.reader(csvfile)
            for row in spamreader:
                article = ec.efetch(db='pubmed', id=row[1])
                for a in article:
                    crud.pubmedarticle_to_db(a, 'trial_publications')
                crud.publication_trial(row[1], row[0], 1)
        article = ec.efetch(db='pubmed', id=r_id)
        for i, a in enumerate(article):
            crud.pubmedarticle_to_db(a, 'systematic_reviews')
        pmids = {24491689, 23741057, 15265849, 12409541, 26673558, 23616602, 21080835, 21444883, 21931078, 26984864,
                 26857383, 25131977, 23680885, 21080836, 9921604, 22433752, 21187258, 21315441, 26560249, 25286913,
                 18342224, 12598066, 20176990, 25921522, 21906250, 26874388, 20562255, 18794390, 27207191}
        content = collections.namedtuple('ids', ['pmids', 'nctids'])
        mock_method.return_value = content(list(pmids), None)
        bot.check_citations(r_id)
        conn = psycopg2.connect(**self.postgresql.dsn())
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT trialpub_id from review_trialpubs where review_id = %s;", (r_id,))
        db_ids = cursor.fetchall()
        pmids1 = set([int(pmid[0]) for pmid in db_ids])
        self.assertEqual(pmids1, {21315441, 25131977, 25286913, 26560249, 26857383})
        cursor.execute("SELECT DISTINCT nct_id from review_rtrial where review_id = %s;", (r_id,))
        db_ids = cursor.fetchall()
        conn.close()
        nct_ids_1 = set([nct[0] for nct in db_ids])
        self.assertEqual(nct_ids_1, {'NCT00531661', 'NCT00538356', 'NCT00531661', 'NCT01360203'})

    def test_check_trialpubs_nctids(self):
        """ verify that all studies referenced by a review with links to PubMed are returned """
        pmids = {29037101, 28735855, 12214118, 28697569, 15380154, 26294005, 21539488, 23680940, 23720230, 24164735,
                 25599006, 25681666, 26086182, 21514250, 19621072, 25961184, 26384466, 24134194, 24495355, 25996285,
                 26265727, 24374288, 25771249, 28359749, 24045855, 24880197, 26640437, 26682691, 27895474, 23796946,
                 25264972, 24507770, 26305649, 25565485, 25891115, 26890759, 26867200, 27529771, 26812512, 24899709,
                 28054939, 27102361, 25344629, 24617349, 25733635, 25733639, 29141041, 25391305, 26135351, 24938711,
                 28319243, 15205295, 20858954, 25352453, 26213339, 25414047, 24334113, 19643207, 28676015, 27570766,
                 17569205, 25002849, 26690214, 18709889, 22232016, 16210710, 22122400, 19204158, 21506929, 22449789,
                 22794138, 27738491, 19641487, 9149659, 28213052, 12663275, 10374811, 17101822, 22371413, 28861684,
                 26652155, 16614482, 27624276, 28925645, 22170358, 25061569, 28980404, 26740832, 26286890, 28448083,
                 29562543, 25928696, 26253520, 26003546, 20810976}
        res = bot.check_trialpubs_nctids(29865058, '10.3233/JAD-179940')
        pmids1 = set([int(pmid) for pmid in res.pmids])
        self.assertEqual(pmids1, pmids)
        pmids = {24491689, 23741057, 15265849, 12409541, 26673558, 23616602, 21080835, 21444883, 21931078, 26984864,
                 26857383, 25131977, 23680885, 21080836, 9921604, 22433752, 21187258, 21315441, 26560249, 25286913,
                 18342224, 12598066, 20176990, 25921522, 21906250, 26874388, 20562255, 18794390, 27207191}
        res = bot.check_trialpubs_nctids(27634736, '10.1002/ejhf.638')
        pmids1 = set([int(pmid) for pmid in res.pmids])
        self.assertEqual(pmids1, pmids)

    def tearDown(self):
        self.patcher1.stop()
        self.postgresql.stop()


if __name__ == '__main__':
    unittest.main()
