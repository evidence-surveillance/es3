#!/usr/bin/python
from matfac import matfac
import numpy as np
import scipy.sparse
from sklearn.decomposition import TruncatedSVD
from datetime import datetime
import dblib
import crud
import utils
import remote_tasks


def update_results():
    """ run matric factorization and insert predictions """
    date = datetime.now().date().strftime('%d-%m-%Y')
    _gen_T_v2(date)
    _matfac_results(date)
    _matfac_trials()


def _gen_T_v2(date):
    con = dblib.create_con(VERBOSE=True)
    cur = con.cursor()
    cur.execute("SELECT nct_id, review_id from review_rtrial where relationship = 'included';")
    links = cur.fetchall()
    con.close()
    ar = np.array(links)
    rows = np.load(utils.most_recent_tfidf_labels())
    ix = np.isin(ar[:, 0], rows)
    row_idx = np.where(ix)
    new_ar = ar[row_idx]
    r_pos = np.array([np.where(rows == x)[0][0] for x in new_ar[:, 0]])
    cols, c_pos = np.unique(new_ar[:, 1], return_inverse=True)
    pivot_table = np.zeros((len(rows), len(cols)))
    pivot_table[r_pos, c_pos] = 1
    s = scipy.sparse.csr_matrix(pivot_table)
    scipy.sparse.save_npz('models/matfac/trials_x_reviews_' + date + '.npz', s)
    np.save(open('models/matfac/nct_rows_' + date + ".pickle", "wb"), rows)
    np.save(open('models/matfac/pmid_cols_' + date + ".pickle", "wb"), cols)


def _matfac_results(date):
    K = 50
    sparse_R = scipy.sparse.load_npz(utils.most_recent_tfidf())
    svd = TruncatedSVD(n_components=200)
    R = svd.fit_transform(sparse_R)
    np.save('models/matfac/truncated_r_' + date, R)
    # R = np.load('models/matfac/truncated_r_'+date+'.npy').astype('float64')
    T = scipy.sparse.load_npz(utils.most_recent_trialsxreviews())
    numNonZeroT = T.count_nonzero()
    T = T.todense().astype('float64')
    estP = np.random.random_sample([R.shape[0], K]) / 10
    estQ = np.random.random_sample([R.shape[1], K]) / 10
    estW = np.random.random_sample([T.shape[1], K]) / 10
    PS_K = np.zeros(K, dtype='float64')
    numRow = R.shape[0]
    numCol1 = R.shape[1]
    numCol2 = T.shape[1]
    numIter = 5000
    alpha_par = 0.01
    lambda_par = 0.001
    lambda_t_par = 0.1
    T_est = np.zeros((numRow, numCol2), dtype='float64')
    VERBOSE = 1
    T_est = np.asarray(
        matfac.run(R, T, estP, estQ, estW, PS_K, numNonZeroT, K, numRow, numCol1, numCol2, numIter, alpha_par,
                   lambda_par, lambda_t_par, T_est, VERBOSE))

    np.save('models/matfac/matfac_results_' + date + '.npy', T_est)


def _matfac_trials():
    print(utils.most_recent_matfac())
    print(utils.most_recent_matfac_pmids())
    print(utils.most_recent_matfac_nctids())
    remote_tasks.remove_bot_votes(11)
    results = np.load(utils.most_recent_matfac())
    pmid_arr = np.load(utils.most_recent_matfac_pmids())
    nct_ids = np.load(utils.most_recent_matfac_nctids())
    con = dblib.create_con(VERBOSE=True)
    cur = con.cursor()
    for c, col in enumerate(results.T):
        cur.execute("SELECT nct_id from review_rtrial where relationship = 'included' and review_id = %s;",
                    (pmid_arr[c],))
        incl = cur.fetchall()
        if not incl:
            continue
        incl = [nct[0] for nct in incl]
        if len(incl) > 2:
            sorted = col.argsort()[::-1][:100]
            top_trials = nct_ids[sorted].flatten()
            if len(set(top_trials) & set(incl)) >= len(incl) / 2:
                for i, trial in enumerate(set(top_trials[:100]) - set(incl)):
                    print(pmid_arr[c], trial)
                    crud.review_trial(pmid_arr[c], trial, False, 'relevant', 'matfacbot', 11)
    con.close()
