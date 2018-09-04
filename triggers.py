import webAPIs
import bot
import dblib
import config
import scipy.sparse
import tsne
from datetime import datetime
import matfac_impl as mf


USER_DB = config.USER_DB
DB_NAME = config.DB_NAME
USER_DB_PASS =config.USER_DB_PASS

# weekly
def check_included():
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor()
    cur.execute("select review_id from review_rtrial where relationship = 'included' GROUP BY review_id HAVING count(*) > 4;")
    reviews = cur.fetchall()
    conn.close()
    bot.remove_bot_votes(10)
    for review in reviews:
        bot.basicbot2(review[0])




# do this after we download the latest ct.gov data
def weekly_update(date):
    # update tfidf
    bot.update_tfidf(date)
    # load new tfidf matrix
    tfidf_matrix = scipy.sparse.load_npz('models/tfidf/tfidf_matrix_'+date+'.npz')
    # generate new TSNE plot
    tsne.regenerate.delay(tfidf_matrix, date)
    # generate newest reviews x trials matrix
    mf.update_results.delay(date)


