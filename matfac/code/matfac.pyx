import numpy as np
import cython
cimport numpy as np
cimport cython
from cython import boundscheck, wraparound
from libc.stdio cimport printf
from libc.math cimport sqrt, pow

ctypedef np.float64_t DTYPE_t

@cython.boundscheck(False)
@cython.wraparound(False)
@cython.nonecheck(False)
@cython.cdivision(True)
cpdef DTYPE_t[:,:] run(np.ndarray[np.float64_t, ndim=2, mode='c', negative_indices=False] R,
          np.ndarray[np.float64_t, ndim=2, mode='c', negative_indices=False] T,
          np.ndarray[np.float64_t, ndim=2, mode='c', negative_indices=False] estP,
          np.ndarray[np.float64_t, ndim=2, mode='c', negative_indices=False] estQ,
          np.ndarray[np.float64_t, ndim=2, mode='c', negative_indices=False] estW,
          np.ndarray[np.float64_t, ndim=1, mode='c', negative_indices=False] PS_K,
          double numNonZeroT,
          int K, int numRow, int numCol1, int numCol2, int numIter,
          double alpha_par, double lambda_par, double lambda_t_par,
          np.ndarray[np.float64_t, ndim=2, mode='c', negative_indices=False] T_est,
          int VERBOSE):

    cdef DTYPE_t[:,::1] cR = R
    cdef DTYPE_t[:,::1] cT = T
    cdef DTYPE_t[:,::1] cT_est = T_est
    cdef DTYPE_t[:,::1] cestP = estP
    cdef DTYPE_t[:,::1] cestQ = estQ
    cdef DTYPE_t[:,::1] cestW = estW
    cdef DTYPE_t[::1] cPS_K = PS_K
    cdef double calpha_par = alpha_par
    cdef double clambda_par = lambda_par
    cdef double clambda_t_par = lambda_t_par
    cdef int cK = K
    cdef int cNumRow = numRow
    cdef int cNumCol1 = numCol1
    cdef int cNumCol2 = numCol2
    cdef int cNumIter = numIter
    cdef double cNumNonZeroT = numNonZeroT
    cdef Py_ssize_t ite, u, k, j, v

    cdef double pred = 0.0
    cdef double euj = 0.0
    cdef double euv = 0.0
    cdef double rmse = 0.0
    cdef int cVERBOSE = VERBOSE
    cdef int cBestIter = 0
    cdef double cBestRMSE = 1000.0

    for ite from 0 <= ite < cNumIter by 1:
        for u from 0 <= u < cNumRow by 1:

            for k from 0 <= k < cK by 1:
                cPS_K[k] = 0.0

            for j from 0 <= j < cNumCol1 by 1:
                pred = 0.0
                for k from 0 <= k < cK by 1:
                    pred += cestP[u, k] * cestQ[j, k]
                euj = pred - cR[u, j]

                for k from 0 <= k < cK by 1:
                    cestQ[j, k] -= calpha_par * (euj * cestP[u, k] + clambda_par * cestQ[j, k])
                    cPS_K[k] += euj * cestQ[j, k] + clambda_par * cestP[u, k]

            for v from 0 <= v < cNumCol2 by 1:
                if cT[u, v] > 0.0:
                    pred = 0.0
                    for k from 0 <= k < cK by 1:
                        pred += cestP[u, k] * cestW[v, k]
                    euv = pred - cT[u, v]

                    for k from 0 <= k < cK by 1:
                        cestW[v, k] -= calpha_par * (clambda_t_par * euv * cestP[u, k] + clambda_par * cestW[v, k])
                        cPS_K[k] +=  clambda_t_par * euv * cestW[v, k]

            for k from 0 <= k < cK by 1:
                cestP[u, k] -= calpha_par * cPS_K[k]


        rmse = 0.0
        for u from 0 <= u < cNumRow by 1:
            for v from 0 <= v < cNumCol2 by 1:
                pred = 0.0
                for k from 0 <= k < cK by 1:
                    pred += cestP[u, k] * cestW[v, k]

                if cT[u, v] > 0.0:
                    rmse += pow(pred - cT[u, v], 2)

        rmse = sqrt(rmse / cNumNonZeroT)

        if rmse < cBestRMSE:
            for u from 0 <= u < cNumRow by 1:
                for v from 0 <= v < cNumCol2 by 1:
                    pred = 0.0
                    for k from 0 <= k < cK by 1:
                        pred += cestP[u, k] * cestW[v, k]
                    cT_est[u, v] = pred

            cBestIter = ite
            cBestRMSE = rmse

        if cVERBOSE == 1:
            printf("  Iter: %d  RMSE: %f. Best iter: %d\n", ite, rmse, cBestIter)

    if cVERBOSE == 1:
        printf("Best iter: %d, Best RMSE T: %f\n", cBestIter, cBestRMSE)

    return cT_est
