import numpy
from app import celery_inst
from flask_socketio import SocketIO
from bokeh.plotting import figure
from bokeh.models import Range1d
from bokeh.embed import components
from celery.task.control import inspect
import utils

from app import cache


@celery_inst.task()
def plot_trials(trials, page, review_id=None, title=None, sess_id=None):
    """
    Resolve  nct_ids to their coordinates in saved TSNE matrix and emit the resulting HTML plot to the client
    @param trials: lists of nct_ids corresponding to trials
    @return: HTML for generated plot
    """
    socketio = SocketIO(message_queue='amqp://localhost')
    tsne_plot = numpy.load(utils.most_recent_tsne())
    tsne_labels = numpy.load(utils.most_recent_tfidf_labels())
    clusters = []
    for trial_list in trials:
        socketio.sleep(0)
        ix = numpy.isin(tsne_labels, trial_list['ids'])
        ids_indices = numpy.where(ix)[0]
        for i, v in enumerate(trial_list['ids']):
            if v not in tsne_labels and (len(ids_indices) < len(trial_list['score'])):
                del trial_list['score'][i]
        ids_vectors = tsne_plot[ids_indices, :]
        clusters.append({'vectors': ids_vectors, 'score': trial_list['score']})
    if page == 'reviewdetail':
        socketio.emit('search_update', {'msg': 'Displaying cool plots...'}, room=sess_id)
        socketio.sleep(0)
    socketio.emit('page_content',
                  {'section': 'plot', 'data': generate_plot_html(clusters), 'page': page, 'review_id': review_id,
                   'title': title}, room=sess_id)
    socketio.sleep(0)
    return


def check_plottrials_running(sess_id):
    """ check if there is already an identical task running in the current session """
    i = inspect()
    active_tasks = i.active()
    if active_tasks:
        for task in active_tasks['worker@ip-172-31-14-248.ap-southeast-2.compute.internal']:
            if task['name'] == 'tsne.plot_trials':
                print 'found running plot trials'
                if 'sess_id' in task['kwargs'] and str(sess_id) in task['kwargs']:
                    print 'found plot trials with matching SID'
                    return True
    return False


@cache.memoize(timeout=86400)
def generate_plot_html(matrices):
    """ generate & return an HTML plot of the data contained in matrices """
    p = figure(plot_width=550, plot_height=550)
    xlim = (-69.551894338989271, 64.381507070922851)
    ylim = (-70.038440855407714, 70.644477995300306)
    p.axis.visible = False
    p.border_fill_color = None
    p.outline_line_color = None
    p.grid.visible = None
    p.toolbar.logo = None
    p.toolbar_location = None
    p.x_range = Range1d(start=xlim[0], end=xlim[1])
    p.y_range = Range1d(start=ylim[0], end=ylim[1])
    p.image_url(url=[utils.most_recent_tsne_img()[18:]], x=xlim[0] - 2.0, y=ylim[1], w=ylim[1] - ylim[0] - 2.7,
                h=(xlim[1] - xlim[0]) + 6.7, anchor="top_left")

    for i, matrix in enumerate(matrices):
        if len(matrix['score']) > 0:
            p.scatter(matrix['vectors'][:, 0], matrix['vectors'][:, 1],
                      fill_color='#fc6e2d', fill_alpha=0.8,
                      line_color=None, size=2)
        else:
            p.scatter(matrix['vectors'][:, 0], matrix['vectors'][:, 1],
                      fill_color='#5f4af9', fill_alpha=0.8,
                      line_color=None, size=2.5)
    comp = components(p)
    return comp[0] + comp[1]
