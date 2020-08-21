#!/usr/bin/python
# -*- coding: UTF-8 -*-
import json
import psycopg2.extras
from flask import render_template, request, url_for, redirect, flash, send_file, abort
from flask_login import login_required, LoginManager, login_user, logout_user, current_user
#from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
import bot
import config
import dblib
import plot
import crud
from app import app, mail, socketio, cache
from .forms import EmailPasswordForm, NewUserForm, ChangePasswordForm, ForgotPasswordForm, PasswordForm, \
    RequestRegisterForm, ContactForm
from .user import User
from celery import chord
import random
import utils
import request_data
import eventlet
from flask_socketio import emit
from eutils import Client
from collections import OrderedDict
from timeit import default_timer as time

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

ts = URLSafeTimedSerializer(app.secret_key)

eutils_key = config.EUTILS_KEY


@socketio.on('connect')
def test_connect():
    emit('my_response', {'data': 'Connected'})


@socketio.on('trigger_basicbot2')
def trigger_basicbot2(json):
    """
    add basicbot2 task to celery queue
    @param json: JSON object specifying review_id
    """
    review = json['review_id']
    if not bot.check_basicbot2_running(review):
        bot.basicbot2.delay(review_id=review, sess_id=request.sid)


@app.route('/plot', methods=['POST'])
def get_plot():
    """ generate new random TSNE plot for homepage """
    ids = crud.get_locked()
    test_id = random.choice(ids)
    review_data = crud.review_medtadata_db(test_id)
    trials = crud.get_review_trials_fast(test_id, usr=current_user if current_user.is_authenticated else None)
    return json.dumps(
        {'success': True, 'data': {'section': 'plot', 'data': plot.get_tsne_data(trials['reg_trials']), 'page': 'home',
                                   'review_id': test_id,
                                   'title': review_data['title']}
         }), 200, {
               'ContentType': 'application/json'}


@socketio.on('refresh_related')
def refresh_related(data):
    trials = data['trials']
    related = crud.related_reviews_from_trials(trials)

    socketio.emit('page_content', {
        'section': 'related_reviews_update',
        'data': render_template('related_review_item.html', related_reviews=related)
    }, room=request.sid)


@socketio.on('freetext_trials')
def freetext_trials(data):
    start = time()
    freetext = ''
    if 'abstract' in data:
        freetext = data['abstract']
        crud.update_ftext_review(data['review_id'], current_user.db_id, freetext)
    else:
        freetext = crud.get_ftext_review(data['review_id'], current_user.db_id)['abstract']

    bp1 = time()
    print('1 Time since last breakpoint: ', bp1 - start)
    print('Total time: ', bp1 - start)

    emit('blank_update', {'msg': 'finding similar trials'}, room=request.sid)
    trial_ids = list(
        OrderedDict.fromkeys(
            bot.basicbot2_freetext(data['review_id']) + bot.docsim_freetext(freetext)
        ).keys()
    )

    bp2 = time()
    print('2 Time since last breakpoint: ', bp2 - bp1)
    print('Total time: ', bp2 - start)

    emit('blank_update', {'msg': 'retrieving related reviews'}, room=request.sid)
    related = crud.related_reviews_from_trials(trial_ids, True)
    recommended_trials = crud.get_trials_by_id(trial_ids, True) if trial_ids else []
    flagged_trials = crud.get_ftext_trials_fast(data['review_id'])['reg_trials']
    flagged_ids = [flagged_trial['nct_id'] for flagged_trial in flagged_trials]
    # Remove flagged trials from recommended trials
    recommended_trials = [trial for trial in recommended_trials if trial['nct_id'] not in flagged_ids]

    plot_trials = []

    for t in (recommended_trials + flagged_trials):
        t = dict(t)
        t['sum'] = 2
        t['verified'] = False
        t['relationship'] = 'included' if t['nct_id'] in flagged_ids else 'relevant'
        plot_trials.append(t)
    emit('blank_update', {'msg': 'loading plots'}, room=request.sid)
    formatted = utils.trials_to_plotdata(plot_trials)
    socketio.emit('page_content',
                  {'section': 'plot', 'data': formatted, 'page': 'blank',
                   }, room=request.sid)

    emit('blank_update', {'msg': 'rendering page'}, room=request.sid)

    bp3 = time()
    print('3 Time since last breakpoint: ', bp3 - bp2)
    print('Total time: ', bp3 - start)

    bp4 = time()
    print('4 Time since last breakpoint: ', bp4 - bp3)
    print('Total time: ', bp4 - start)

    emit('page_content', {
        'section': 'recommended_trials',
        'data': render_template('recommended_trials.html', reg_trials=recommended_trials),
    }, room=request.sid)

    emit('page_content', {
        'section': 'related_reviews',
        'data': render_template('related_reviews.html', related_reviews=related)
    }, room=request.sid)

    emit('page_content',
         {'section': 'incl_trials',
          'data': render_template('ftext_incl_trials.html', reg_trials=flagged_trials)
          }, room=request.sid)

    emit('blank_update', {'msg': 'loading complete'}, room=request.sid)

    bp5 = time()
    print('5 Time since last breakpoint: ', bp5 - bp4)
    print('Total time: ', bp5 - start)
    # plot.plot_trials.delay(relevant=trial_ids, page='reviewdetail',
    #                        sess_id=request.sid)


@socketio.on('refresh_trials')
def refresh_trials(json):
    """
    reload & render HTML for trials
    @param json: JSON object specifying review_id, which 'type' of trials to refresh, and whether to generate a new plot
    """
    id = json['review_id']
    type = json['type']
    plot_bool = json['plot']
    ftext_bool = json.get('ftext', False)

    sort = json['sort'] if 'sort' in json else 'total_votes'

    if ftext_bool:
        trials = crud.get_ftext_trials_fast(id)['reg_trials']
        emit('page_content',
             {'section': 'incl_trials',
              'sort': sort,
              'data': render_template('ftext_incl_trials.html', reg_trials=trials)
              }, room=request.sid)
        if plot_bool:
            recommended_trials = crud.get_trials_by_id(json['rec_trials'])
            flagged_ids = [trial['nct_id'] for trial in trials]
            recommended_trials = [trial for trial in recommended_trials if trial['nct_id'] not in flagged_ids]
            plot_trials = []
            for t in (recommended_trials + trials):
                t = dict(t)
                t['sum'] = 2
                t['verified'] = False
                t['relationship'] = 'included' if t['nct_id'] in flagged_ids else 'relevant'
                plot_trials.append(t)
            formatted = utils.trials_to_plotdata(plot_trials)
            socketio.emit('page_content',
                          {'section': 'plot', 'data': formatted, 'page': 'reviewdetail',
                           'review_id': id
                           }, room=request.sid)

    else:
        trials = crud.get_review_trials_fast(id, order=sort,
                                             usr=current_user if current_user.is_authenticated else None)
        locked = crud.review_lock_status(id)

        relevant = [trial['nct_id'] for trial in trials['reg_trials'] if trial['relationship'] == 'relevant']
        verified = [trial['nct_id'] for trial in trials['reg_trials'] if trial['relationship'] == 'included']
        if (type == 'rel' and relevant) or (type == 'incl' and verified):
            emit('page_content',
                 {'section': 'rel_trials' if type == 'rel' else 'incl_trials', 'sort': sort,
                  'data': render_template('rel_trials.html' if type == 'rel' else 'incl_trials.html',
                                          reg_trials=trials['reg_trials'],
                                          locked=locked)}, room=request.sid)
            if plot_bool:
                formatted = utils.trials_to_plotdata(trials['reg_trials'])
                socketio.emit('page_content',
                              {'section': 'plot', 'data': formatted, 'page': 'reviewdetail',
                               'review_id': id
                               }, room=request.sid)

        elif type == 'incl' and not verified['ids']:
            emit('page_content',
                 {'section': 'incl_trials', 'sort': sort,
                  'data': render_template('incl_trials.html',
                                          reg_trials=[],
                                          locked=False)}, room=request.sid)


@socketio.on('search')
def search(json):
    """
    conduct a search
    @param json: JSON object specifying serch keywords
    """
    id = json['review_id']
    emit('search_update', {'msg': 'Searching...'}, room=request.sid)
    eventlet.sleep(0)
    if not id:
        emit('page_content', {'section': 'no_results', 'data': render_template('noresults.html', id=id)},
             room=request.sid)
        return
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # try to retrieve review with matching PMID if id is int
    review = ''
    found = True
    if (utils.RepresentsInt(id)):
        review = crud.review_medtadata_db(id)
    # try to retrieve review with matching DOI if id is DOI
    elif utils.is_doi(id):
        cur.execute("SELECT * FROM systematic_reviews WHERE doi = %s;", (id,))
        review = cur.fetchone()
        conn.close()
    # if not int or DOI, return no results page
    else:
        conn.close()
        emit('search_update', {'msg': 'Searching for keyword matches in our database'}, room=request.sid)
        search_result = request_data.advanced_search(id)
        if not search_result:
            emit('page_content', {'section': 'no_results', 'data': render_template('noresults.html', id=id)},
                 room=request.sid)
            return
        emit('page_content', {'section': 'search_results',
                              'data': render_template('searchresult.html', reviews=search_result, searchterm=id)},
             room=request.sid)
        return
    # if there is no match in our DB
    if review is None:
        found = False
        if not current_user.is_authenticated:
            conn.close()
            emit('page_content', {'section': 'no_results', 'data': render_template('noresults.html', id=id)},
                 room=request.sid)
            return
        emit('search_update', {'msg': 'Not found in local database. Searching PubMed for article'}, room=request.sid)
        eventlet.sleep(0)
        if utils.is_doi(id):
            # try to retrieve PMID if DOI
            convert = crud.convert_id(id, 'pmid')
            if convert:
                id = convert
            # return no result if no results
            else:
                emit('search_update', {'msg': 'Not found in Pubmed :('},
                     room=request.sid)
                emit('page_content', {'section': 'no_results', 'data': render_template('noresults.html', id=id)},
                     room=request.sid)
                return
        # try to retrieve the review from pubmed
        ec = Client(api_key=eutils_key)
        article = ec.efetch(db='pubmed', id=id)
        found_review = None
        for art in article:
            if art and str(art.pmid) == id:
                found_review = art
                break
        if found_review:
            result = found_review.pmid
            if not result:
                flash('Unable to retrieve metadata for this article. Please try again later')
                abort(404)
            emit('search_update', {'msg': 'Found article on PubMed. Downloading metadata...'}, room=request.sid)
            eventlet.sleep(0)
            crud.pubmedarticle_to_db(found_review, 'systematic_reviews')
            review = crud.review_medtadata_db(id)
            emit('page_content', {'data': render_template('review_data.html', review=review), 'section': 'review_data'},
                 room=request.sid)
            eventlet.sleep(0)
            emit('search_update', {'msg': 'Saved metadata... triggering bots'}, room=request.sid)
            bot.docsim.delay(id, sess_id=request.sid)
            eventlet.sleep(0)
            if 'cochrane' in review['source'].lower() and 'doi' in review:
                cb_bb = bot.cochrane_ongoing_excluded.si(review['doi'], id, sess_id=request.sid)
                cb_bb.link(bot.basicbot2.si(review_id=id, sess_id=request.sid))
                chord((bot.cochranebot.s(review['doi'], id, sess_id=request.sid),
                       bot.check_citations.s(id, sess_id=request.sid)),
                      cb_bb).delay()
            else:
                chord((bot.check_citations.s(id, sess_id=request.sid)),
                      bot.basicbot2.si(review_id=id, sess_id=request.sid)).delay()
        else:
            print
            'no result'
            emit('page_content', {'section': 'no_results', 'data': render_template('noresults.html', id=id)},
                 room=request.sid)
            return
    # if there IS a match in our DB
    if found:
        print
        'emitting found review'
        eventlet.sleep(0)
        emit('search_update', {'msg': 'Found review in our database! Retrieving data..'}, room=request.sid)
        eventlet.sleep(0)
        print
        'emitting review content'
        emit('page_content', {'data': render_template('review_data.html', review=review,
                                                      starred=crud.is_starred(review['review_id'],
                                                                              current_user.db_id) if current_user.is_authenticated else False),
                              'section': 'review_data',
                              'related_reviews': render_template('related_reviews.html',
                                                                 related_reviews=crud.related_reviews(
                                                                     review['review_id']))},
             room=request.sid)
        eventlet.sleep(0)
        trials = crud.get_review_trials_fast(review[0], usr=current_user if current_user.is_authenticated else None)
        relevant = [trial['nct_id'] for trial in trials['reg_trials'] if trial['relationship'] == 'relevant']
        verified = [trial['nct_id'] for trial in trials['reg_trials'] if trial['relationship'] == 'included']
        emit('search_update', {'msg': 'Generating cool plots...'}, room=request.sid)
        eventlet.sleep(0)
        formatted = utils.trials_to_plotdata(trials['reg_trials'])
        socketio.emit('page_content',
                      {'section': 'plot', 'data': formatted, 'page': 'reviewdetail',
                       'review_id': review[0]
                       }, room=request.sid)
        emit('page_content',
             {'section': 'rel_trials', 'data': render_template('rel_trials.html', reg_trials=trials['reg_trials'],
                                                               locked=review['included_complete'])}, room=request.sid)
        eventlet.sleep(0)
        if verified:
            emit('page_content',
                 {'section': 'incl_trials', 'data': render_template('incl_trials.html', reg_trials=trials['reg_trials'],
                                                                    locked=review['included_complete'])},
                 room=request.sid)
            eventlet.sleep(0)
        else:
            emit('page_content',
                 {'section': 'incl_trials', 'data': render_template('incl_trials.html', reg_trials=[],
                                                                    locked=False)}, room=request.sid)


@login_manager.user_loader
def load_user(id):
    """
    retrieve a User instance with the given id
    @param id: id of desired User
    @return: User instance
    """
    obj = User.get(id)
    if obj is not None:
        return obj
    else:
        return None


@cache.cached(timeout=60)
@app.route('/')
def index():
    """ load home page  """
    return render_template('index.html')


@cache.cached(timeout=60)
@app.route('/data_summary', methods=['GET'])
def unique_reviews_trials():
    """ get summary of data for front page """
    return json.dumps({'success': True, 'data': crud.data_summary()
                       }, default=str), 200, {
               'ContentType': 'application/json'}


@cache.cached(timeout=60)
@app.route('/browse')
def browse():
    """ load browse page  """
    return render_template('browse.html', categories=crud.get_categories())


@cache.cached(timeout=86400)
@app.route('/category/<category>')
def browse_category(category):
    """
    browse reviews in specific category
    @param category: id of desired category
    @return: rendered page content
    """
    return render_template('category.html', conditions=crud.get_conditions(category), category_id=category,
                           category_name=crud.category_name(category))


@app.route('/condition_counts', methods=['POST'])
def condition_counts():
    """ get counts for each condition in the specified category """
    data = request.json
    try:
        only_verified = bool(int(data['onlyVerified']))
    except ValueError as e:
        return json.dumps({'success': False, 'msg': 'bad value for onlyVerified'
                           }), 400, {
                   'ContentType': 'application/json'}

    return json.dumps({'success': True, 'data': crud.condition_counts(data['category'], only_verified)
                       }), 200, {
               'ContentType': 'application/json'}


@app.route('/category_counts', methods=['GET'])
def category_counts():
    """ get review counts for every category """
    try:
        only_verified = bool(int(request.args.get('onlyVerified')))
    except ValueError as e:
        return json.dumps({'success': False, 'msg': 'bad value for onlyVerified'
                           }), 400, {
                   'ContentType': 'application/json'}
    return json.dumps({'success': True, 'data': crud.category_counts(only_verified)
                       }), 200, {
               'ContentType': 'application/json'}


@cache.cached(timeout=60)
@app.route('/condition/<condition>')
def review_conditions(condition):
    """
    get a list of reviews for the specified condition
    @param condition: id of desired condition
    @return: rendered page content
    """
    return render_template('reviews_by_condition.html', reviews=crud.reviews_for_condition(condition))


@app.route('/information')
def information():
    """ load info page """
    return render_template('information.html')


@app.route("/logout")
@login_required
def logout():
    """ log out current user & redirect to login page """
    logout_user()
    return redirect(url_for('login'))


@app.route('/login', methods=['GET'])
def login():
    """ load the login page """
    return render_template('login.html', loginform=EmailPasswordForm(), forgotpw=ForgotPasswordForm(),
                           accessform=RequestRegisterForm())


@app.route('/login', methods=['POST'])
def submit_login():
    """
    attempt to log in
    @return: requested page or home page
    """
    if request.form['submit'] == "Login":
        login_form = EmailPasswordForm(request.form)
        if login_form.validate_on_submit():
            registered_user = User.get(login_form.login_email.data)
            if registered_user is None or registered_user.password is None:
                flash('Username is invalid', 'error')
                return render_template('login.html', loginform=login_form, forgotpw=ForgotPasswordForm(),
                                       accessform=RequestRegisterForm())
            if not registered_user.check_password(login_form.password.data):
                flash('Password is invalid', 'error')
                return render_template('login.html', loginform=login_form, forgotpw=ForgotPasswordForm(),
                                       accessform=RequestRegisterForm())
            login_user(registered_user)
            return redirect(request.args.get('next') or url_for('index'))
        else:
            return render_template('login.html', loginform=login_form, forgotpw=ForgotPasswordForm(),
                                   accessform=RequestRegisterForm())


@app.route('/search', methods=['GET'])
def search():
    """ load search page """
    return render_template('reviewdetail.html')


@app.route('/blank', methods=['GET'])
@login_required
def blank():
    """ load ftext review page """
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 401, {
            'ContentType': 'application/json'}

    review_id = request.args.get('id')

    if not review_id:
        review_id = crud.get_most_recent_ftext_review(current_user.db_id)
        return redirect('/blank?id=%s' % review_id)

    review = crud.get_ftext_review(review_id, current_user.db_id)
    if not review:
        return "That resource does not exist.", 404, {
            'ContentType': 'application/json'}

    if current_user.db_id != review['user_id']:
        return "Sorry! You do not have access to view this.", 403, {
            'ContentType': 'application/json'}
    return render_template('blank.html', review_id=review_id, abstract=review['abstract'], title=review['title'])


@app.route('/recent_ftext_review', methods=['GET'])
def recent_ftext_review():
    """Get most recent ftext review, otherwise create one and return that"""
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 401, {
            'ContentType': 'application/json'}

    user_id = current_user.db_id
    idx = crud.get_most_recent_ftext_review(user_id)
    return json.dumps({'success': True, 'message': 'Review retrieved successfully', 'idx': idx}), 200, {
        'ContentType': 'application/json'}


@app.route('/createftext', methods=['POST'])
def create_ftext_review():
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 401, {
            'ContentType': 'application/json'}

    idx = crud.create_ftext_review(current_user.db_id)
    return json.dumps({'success': True, 'message': 'Review created successfully', 'idx': idx}), 201, {
        'ContentType': 'application/json'}


@app.route('/deleteftext', methods=['POST'])
def delete_ftext_review():
    """Delete freetext review"""
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 401, {
            'ContentType': 'application/json'}

    data = request.json
    review_id = data['review_id']
    user_id = current_user.db_id
    idx = crud.delete_ftext_review(review_id, user_id)
    if idx:
        return json.dumps({'success': True, 'message': 'Review deleted successfully', 'idx': review_id}), 200, {
            'ContentType': 'application/json'}
    else:
        return json.dumps({'success': False, 'message': 'Review not found', 'idx': review_id}), 404, {
            'ContentType': 'application/json'}


@app.route('/updateftexttitle', methods=['POST'])
def update_ftext_title():
    """Update freetext review title"""
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 401, {
            'ContentType': 'application/json'}

    data = request.json
    review_id = data['review_id']
    user_id = current_user.db_id
    title = data['title']
    idx = crud.update_ftext_title(review_id, title, user_id)
    if idx:
        return json.dumps({'success': True, 'message': 'Review deleted successfully', 'idx': review_id}), 200, {
            'ContentType': 'application/json'}
    else:
        return json.dumps({'success': False, 'message': 'Review not found', 'idx': review_id}), 404, {
            'ContentType': 'application/json'}


@app.route('/saved', methods=['GET'])
@login_required
def saved():
    """ load saved reviews page """
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 401, {
            'ContentType': 'application/json'}

    reviews = crud.get_saved_reviews(current_user.db_id)
    ftext_reviews = crud.get_ftext_reviews(current_user.db_id)
    return render_template('saved.html', reviews=reviews, ftext_reviews=ftext_reviews)


@app.route('/save_review', methods=['POST'])
def save_review():
    """
    save review for user
    @return: json indicating success
    """
    data = request.json
    crud.save_review(data['review_id'], current_user.db_id, data['value'])
    return json.dumps({'success': True, 'message': 'Review saved successfully'}), 200, {
        'ContentType': 'application/json'}


@app.route('/included_relevant', methods=['POST'])
def incl_rel():
    """
    Move the trial specified in the JSON data from 'included' to 'relevant'
    @return: json string indicating success or failure
    """
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 400, {
            'ContentType': 'application/json'}
    data = request.json
    if utils.is_doi(data['review']):
        # retrieve PMID if DOI
        data['review'] = crud.convert_id(data['review'], 'pmid')
    link_id = crud.get_link_id(data['nct_id'], data['review'])
    crud.change_relationship(link_id, 'relevant')
    return json.dumps({'success': True, 'message': 'Trial moved successfully'}), 200, {
        'ContentType': 'application/json'}


@app.route('/download/<detail>', methods=['GET'])
@login_required
def download_matrix(detail):
    """
    download matrices
    @param detail: JSON object specifying desired matrix
    @param detail: JSON object specifying desired matrix
    @return: CSV file with matrix
    """
    try:
        if detail == 'all':
            return send_file('../review_trial_matrix.csv', as_attachment=True)
        if detail == 'complete':
            return send_file('../complete_review_matrix.csv', as_attachment=True)
    except Exception as e:
        abort(404)


@app.route('/download', methods=['GET'])
@login_required
def download():
    """ load download page """
    return render_template('download.html')


@app.route('/relevant_included', methods=['POST'])
def rel_incl():
    """
    Move the trial specified in the JSON data from 'relevant' to 'included'
    @return: success/failure message
    """
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 400, {
            'ContentType': 'application/json'}
    data = request.json
    if utils.is_doi(data['review']):
        # try to retrieve PMID if potenially DOI
        data['review'] = crud.convert_id(data['review'], 'pmid')
    link_id = crud.get_link_id(data['nct_id'], data['review'])
    crud.change_relationship(link_id, 'included')
    return json.dumps({'success': True, 'message': 'Trial moved successfully'}), 200, {
        'ContentType': 'application/json'}


@app.route('/included_complete', methods=['POST'])
def included_complete():
    """
    mark the current review as having a complete list of included trials
    @return: success/failure message
    """
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 400, {
            'ContentType': 'application/json'}
    data = request.json
    review = data['review_id']
    complete = data['value']
    crud.complete_studies(review, complete)
    return json.dumps({'success': True, 'message': 'Thanks for verifying!'}), 200, {
        'ContentType': 'application/json'}


@app.route('/vote', methods=['POST'])
def vote():
    """
    vote for a specified trial
    @return: success message & updated list of voters for specified trial
    """
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 400, {
            'ContentType': 'application/json'}
    current_userid = current_user.db_id
    data = request.json
    if utils.is_doi(data['review']):
        # try to retrieve PMID if potenially DOI
        data['review'] = crud.convert_id(data['review'], 'pmid')
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # check if user has already voted for this trial
    link_id = crud.get_link_id(data['id'], data['review'])
    cur.execute(
        "SELECT * FROM votes WHERE link_id = %s AND user_id = %s;",
        (link_id, current_userid))
    current = cur.fetchone()
    if data['up'] and (not current or (current and current['vote_type'] == 'down')):
        crud.vote(link_id, 'up', current_userid)
    if data['down'] and (not current or (current and current['vote_type'] == 'up')):
        crud.vote(link_id, 'down', current_userid)
    if current and (data['up'] is False and data['down'] is False) or (data['up'] is False and data['down'] == 0) or (
            data['down'] is False and data['up'] == 0):
        cur.execute("DELETE FROM votes WHERE vote_id = %s;", (current['vote_id'],))
    conn.commit()
    conn.close()
    return json.dumps({'success': True, 'voters': update_voters(data['review'], data['id'])}), 200, {
        'ContentType': 'application/json'}


@app.route('/removeftexttrial', methods=['POST'])
def remove_ftext_trial():
    """
    remove a trial link from a ftext review
    :return:
    """
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 401, {
            'ContentType': 'application/json'}
    data = request.json

    if data['nct_id'] and data['review_id']:
        crud.remove_ftext_trial(data['review_id'], data['nct_id'])
        return json.dumps({'success': True, 'message': 'Trial removed successfully'}), 200, {
            'ContentType': 'application/json'}
    else:
        return json.dumps(
            {'success': False, 'message': 'Request requires nct_id and review_id parameters', 'move': True}), 400, {
                   'ContentType': 'application/json'}


@app.route('/submitftexttrial', methods=['POST'])
def submit_ftext_trial():
    """
    link a trial to a ftext review
    :return:
    """
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 401, {
            'ContentType': 'application/json'}
    data = request.json

    if data['nct_id'] and data['review']:
        crud.link_ftext_trial(data['review'], data['nct_id'])
        return json.dumps({'success': True, 'message': 'Added trial successfully'}), 201, {
            'ContentType': 'application/json'}
    else:
        return json.dumps(
            {'success': False, 'message': 'Request requires nct_id and review_id parameters', 'move': True}), 400, {
                   'ContentType': 'application/json'}


@app.route('/submittrial', methods=['POST'])
def submit_trial():
    """
    submit a relevant or included trial for the current article
    @return: success/failure message
    """
    if not current_user.is_authenticated:
        return "Sorry! This action is only available to logged-in users", 400, {
            'ContentType': 'application/json'}
    data = request.json
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if data['nct_id'] and data['review']:
        # check if the trial exists already
        cur.execute("SELECT * FROM tregistry_entries WHERE nct_id =%s;", (data['nct_id'],))
        trial_reg_data = cur.fetchone()
        # if not exists
        conn.close()
        if not trial_reg_data:
            missing = crud.add_missing_trial(data['nct_id'])
            if not missing:
                conn.close()
                return json.dumps({'success': False, 'message': 'Unable to retrieve trial'}), 200, {
                    'ContentType': 'application/json'}
            if utils.is_doi(data['review']):
                data['review'] = crud.convert_id(data['review'], 'review_id')
        result = crud.check_existing_review_trial(data['review'], data['nct_id'])
        if not result:
            crud.review_trial(data['review'], data['nct_id'], False, data['relationship'], current_user.nickname,
                              current_user.db_id)
            return json.dumps({'success': True, 'message': 'Added trial successfully', 'data': str(data)}), 200, {
                'ContentType': 'application/json'}
        elif data['relationship'] == result['relationship']:
            return json.dumps({'success': False, 'message': 'Trial already exists', 'move': False}), 200, {
                'ContentType': 'application/json'}
        elif data['relationship'] == 'relevant' and result['relationship'] == 'included':
            return json.dumps(
                {'success': False, 'message': 'Trial is already listed as included', 'move': True}), 200, {
                       'ContentType': 'application/json'}
        else:
            return json.dumps(
                {'success': False, 'message': 'Trial already in list of relevant trials', 'move': True}), 200, {
                       'ContentType': 'application/json'}


@app.route("/admin", methods=['GET'])
@login_required
def admin_panel():
    """
    load the admin page if user has appropriate permissions
    @return: admin page content
    """
    if not current_user.is_admin:
        abort(404)
    new_user_form = NewUserForm()
    return render_template('adminpanel.html', users=User.get_all(), new_user=new_user_form)


@app.route('/profile', methods=['GET'])
@login_required
def profile():
    """
    load the profile page for the current user (currently just a 'change password' form)
    @return: profile page content
    """
    changepw_form = ChangePasswordForm()
    return render_template('profile.html', changepw_form=changepw_form)


@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """
    change password of current user
    @return: refreshed page content indicating success or failure
    """
    changepw_form = ChangePasswordForm(request.form)
    user = User.get(current_user.id)
    if changepw_form.validate_on_submit() and user:
        if user.check_password(changepw_form.current_password.data):
            User.change_password(user, User.set_password(user, changepw_form.new_password.data))
            flash("Password Changed")
        else:
            flash("Current password invalid")
    else:
        flash("Email address invalid")
        return render_template('profile.html', changepw_form=changepw_form)
    return render_template('profile.html', changepw_form=changepw_form)


@app.route("/admin", methods=['POST'])
@login_required
def alter_users():
    """
    add new user or delete exiting user
    @return: refreshed page indicating success or failure
    """
    if request.form['submit'] == "Create User":
        form = NewUserForm(request.form)
        if form.validate_on_submit():
            if User.get(form.new_email.data) is None:
                User(form.new_email.data, form.nickname.data, form.password.data, form.type.data)

                #msg = Message('ES3 Access Request', sender=config.MAIL_USERNAME,
                #              recipients=[form.new_email.data])
                #msg.html = render_template('registration_email.html', user=form.new_email.data, pw=form.password.data)
                data = {
                   'Messages': [
                        {"From": {"Email": config.MAIL_USERNAME, "Name": config.MAIL_SENDER_NAME},
                         "To": [{"Email": form.new_email.data}],
                         "Subject": "ES3 Access Request",
                         "HTMLPart": render_template('registration_email.html', user=form.new_email.data, pw=form.password.data)
                    }]
                }
                mail.send.create(data=data)

                flash('New user ' + form.new_email.data + ' created successfully')
            else:
                flash('User already exists')
            return redirect(url_for('admin_panel'))
        else:
            return render_template('adminpanel.html', new_user=form, users=User.get_all())
    elif request.form['submit'] == "Delete Selected":
        for x in request.form:
            if len(request.form) == 1:
                flash('Error - no user selected')
                break
            if x == current_user.id:
                flash('Error - cannot delete own account')
                break
            if request.form[x] == "on":
                User.delete(x)
                flash('User ' + x + ' deleted successfully')
            return redirect(url_for('admin_panel'))
    return render_template('adminpanel.html', new_user=NewUserForm(), users=User.get_all())


@app.route('/contact', methods=["GET", "POST"])
def contact():
    """
    Conctact page
    :return:
    """
    if request.method == 'POST':
        form = ContactForm()
        if form.validate_on_submit():
            #msg = Message('ES3 Message', sender=config.MAIL_USERNAME, bcc=config.REQUEST_EMAIL_RECIPIENTS,
            #              reply_to=form.email.data)
            #msg.body = '%s (%s) has sent a message via the contact form on ES3:' % (
            #    form.nickname.data, form.email.data,)
            #msg.body += '\n \n' + form.content.data
            #mail.send(msg)
            data = {
                   'Messages': [
                        {"From": {"Email": config.MAIL_USERNAME, "Name": config.MAIL_SENDER_NAME},
                         "To": [{"Email": config.REQUEST_EMAIL_RECIPIENT}],
                         "Subject": "ES3 Message",
                         "ReplyTo": form.email.data,
                         "TextPart": '%s (%s) has sent a message via the contact form on ES3: \n \n %s' % (form.nickname.data, form.email.data, form.content.data,)
                    }]
                }
            mail.send.create(data=data)
            flash('Message sent')
        else:
            flash(', '.join(form.email.errors + form.nickname.errors + form.content.errors))
        return redirect(url_for('contact'))

    elif request.method == 'GET':
        return render_template('contact.html', contact_form=ContactForm())


@app.route('/register', methods=['POST'])
def register():
    """
    Registration of account
    :return:
    """
    form = RequestRegisterForm()
    if form.validate_on_submit():
        #msg = Message('ES3 Access Request', sender=config.MAIL_USERNAME, bcc=config.REQUEST_EMAIL_RECIPIENTS,
        #              reply_to=form.email.data)
        #msg.body = '%s (%s) is requesting access to ES3.' % (
        #    form.nickname.data, form.email.data,)
        #mail.send(msg)
        data = {
            'Messages': [
            {"From": {"Email": config.MAIL_USERNAME, "Name": config.MAIL_SENDER_NAME},
            "To": [{"Email": form.new_email.data}],
            "Subject": "ES3 Access Request",
            "ReplyTo": form.email.data,
            "TextPart": "%s (%s) is requesting access to ES3." % (form.nickname.data, form.email.data,)
            }]
        }
        mail.send.create(data=data)

        flash('Access requested successfully.')
    else:
        flash('Please enter a valid email address')
    return redirect(url_for('login'))


@app.route('/reset', methods=["GET", "POST"])
def reset():
    """
    send reset password email to specified user email
    @return: refreshed page indicating success or failure
    """
    print(url_for('login'))
    print(url_for('login', _external=True))
    print(url_for('index'))
    print(url_for('index', _external=True))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.get(form.forgot_email.data)
        subject = "Password reset requested"
        token = ts.dumps(user.id, salt='recover-key')
        recover_url = url_for(
            'reset_with_token',
            token=token,
            _external=True)
        html = render_template(
            'recover.html',
            recover_url=recover_url)
        #msg = Message(subject, sender=config.MAIL_USERNAME, recipients=[user.id])
        #msg.body = html
        #mail.send(msg)

        data = {
            'Messages': [
            {"From": {"Email": config.MAIL_USERNAME, "Name": config.MAIL_SENDER_NAME},
            "To": [{"Email": user.id}],
            "Subject": "Password reset requested",
            "HTMLPart": html
            }]
        }
        mail.send.create(data=data)
        flash('Password reset email sent to ' + user.id)
        return redirect(url_for('login', _external=True))
    return render_template('login.html', loginform=EmailPasswordForm(), forgotpw=ForgotPasswordForm(),
                           accessform=RequestRegisterForm())


@app.route('/reset/<token>', methods=["GET", "POST"])
def reset_with_token(token):
    """
    reset password with email token
    @param token: unique token
    @type token: str
    @return: refreshed page indicating success or failure
    """
    try:
        email = ts.loads(token, salt="recover-key", max_age=86400)
    except:
        abort(404)
    form = PasswordForm()
    if form.validate_on_submit():
        user = User.get(email)
        password = form.password.data
        user.change_password(user.set_password(password))
        login_user(user)
        flash('Password changed successfully!')
        return redirect(url_for('index'))
    return render_template('reset_with_token.html', form=form, token=token)


def update_voters(review_id, nct_id):
    """
    update the list of users who have upvoted the specified trial registry entry
    @param review_id: pmid of review
    @param nct_id: id of trial registry entry
    @return: users who have voted
    """
    conn = dblib.create_con(VERBOSE=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT DISTINCT nickname, id FROM users INNER JOIN votes ON users.id = votes.user_id WHERE link_id = (SELECT id "
        "FROM review_rtrial WHERE review_id = %s AND nct_id = %s) AND vote_type = 'up';",
        (review_id, nct_id))
    voters = cur.fetchall()
    nicknames = []
    usr = current_user.db_id
    for voter in voters:
        if voter['id'] == usr:
            voter['nickname'] = 'you'
        nicknames.append(voter['nickname'])
    return ', '.join(nicknames)
