#!/usr/bin/python
# -*- coding: utf-8 -*-
import config
import psycopg2
import psycopg2.extensions
import time

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

USER_DB = config.USER_DB
DB_NAME = config.DB_NAME
USER_DB_PASS = config.USER_DB_PASS
DB_HOST = config.DB_HOST
DB_PORT = config.DB_PORT


def create_con(VERBOSE):
    """
    connect to the database
    @param VERBOSE: True/False
    @raise: DatabaseError if connection fails 3 times
    @return: connection to db
    """
    retries = 3
    while True:
        retries -= 1
        try:
            con = psycopg2.connect(database=DB_NAME, user=USER_DB, host=DB_HOST, password=USER_DB_PASS, port=DB_PORT)
        except (psycopg2.DatabaseError, psycopg2.OperationalError), exc:
            if VERBOSE:
                print 'Error connecting to database. Trying again.'
                print '  Error %s' % exc
            if exc.args != (u'timeout expired\n',):
                raise
            if retries <= 0:
                raise
            time.sleep(5)
            continue
        if con:
            return con
        else:
            continue
