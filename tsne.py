import matplotlib
matplotlib.use('Agg')
from sklearn.decomposition import TruncatedSVD
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import numpy
import mpld3
from mpld3 import plugins
import scipy.sparse
from datetime import datetime
import umap
from app import celery_inst
from flask_socketio import SocketIO
from bokeh.plotting import figure, show, output_file, save
from bokeh.models import Range1d
from bokeh.io import export_png
from bokeh.embed import  components
import json
from celery.task.control import inspect

LATEST_DATE='2018-05-05'


@celery_inst.task(ignore_result=True)
def regenerate(tfidf_matrix, date):
    _tsne(tfidf_matrix, date)
    new_tsne = numpy.load('models/tsne/tsne_matrix_' + date + '.npy')
    # generate new _tsne background plot
    _new_tsne_img(new_tsne, date)



def _tsne(input_matrix, date):
    """
    Generate and save TSNE visualisation of input matrix

    @param input_matrix: 2D sparse CSR matrix
    @return: None
    """
    transformer = TruncatedSVD(n_components=50, random_state=0)
    X_reduced = transformer.fit_transform(input_matrix)
    X_embedded = TSNE(n_components=2, perplexity=50, verbose=2, init='pca', learning_rate=1000).fit_transform(X_reduced)
    numpy.save('models/tsne/tsne_matrix_'+date, X_embedded)


def _new_tsne_img(matrix, date):
    fig = plt.figure(figsize=(5, 5))
    ax = plt.axes(frameon=False)
    plt.setp(ax, xticks=(), yticks=())
    plt.subplots_adjust(left=0.0, bottom=0.0, right=1.0, top=1.0,
                        wspace=0.0, hspace=0.0)
    xlim = (-71.551894338989271, 66.381507070922851)
    ylim = (-70.038440855407714, 70.644477995300306)
    ax.set_ylim(ylim)
    ax.set_xlim(xlim)
    plt.scatter(matrix[:, 0], matrix[:, 1],
                c='0.85',edgecolors='none', alpha=0.8,
                marker='.', s=1)
    plt.savefig('app/static/images/tsne'+date+'_sml.png', format='png', dpi=400)


def _truncate_colormap(cmap, minval=0.0, maxval=1.0, n=100):
    """
    Truncate a colormap to the specified min & max values between 0.0 and 1.0

    @param cmap: name of cmap
    @param minval: minimum cmap value
    @param maxval: max cmap value
    @param n: number of colormap samples to use
    @return: truncated colormap
    """
    new_cmap = colors.LinearSegmentedColormap.from_list(
        'trunc({n},{a:.2f},{b:.2f})'.format(n=cmap.name, a=minval, b=maxval),
        cmap(numpy.linspace(minval, maxval, n)))
    return new_cmap

@celery_inst.task()
def plot_trials(trials, page,review_id=None,title=None, sess_id=None):
    """
    Resolve the nct_ids in trials to their coordinates in saved TSNE matrix, and
    generate an HTML plot for these points

    @param trials: lists of nct_ids corresponding to trials that we want to plot
    @return: HTML for generated plot
    """

    print len(trials[0]['ids'])
    print len(trials[0]['score'])
    socketio = SocketIO(message_queue='amqp://localhost')
    tsne_plot = numpy.load('models/tsne/tsne_matrix_'+LATEST_DATE+'.npy')
    tsne_labels = numpy.load('models/tfidf/nct_ids_'+LATEST_DATE+'.pickle')
    clusters = []
    for trial_list in trials:
        socketio.sleep(0)

        ix = numpy.isin(tsne_labels, trial_list['ids'])
        ids_indices = numpy.where(ix)[0]
        for i, v in enumerate(trial_list['ids']):
            if v not in tsne_labels and (len(ids_indices) < len(trial_list['score'])):
                del trial_list['score'][i]
        print len(ids_indices)
        ids_vectors = tsne_plot[ids_indices, :]
        clusters.append({'vectors':ids_vectors, 'score':trial_list['score']})
    if page =='reviewdetail':
        socketio.emit('search_update', {'msg': 'Displaying cool plots...'}, room=sess_id)
        socketio.sleep(0)
    socketio.emit('page_content', {'section': 'plot', 'data': test_bokeh(clusters),'page':page, 'review_id':review_id,'title':title}, room=sess_id)
    socketio.sleep(0)
    return


def check_plottrials_running(sess_id):
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


def trials_data(trials, sess_id=None):
    """
    Resolve the nct_ids in trials to their coordinates in saved TSNE matrix, and
    generate an HTML plot for these points

    @param trials: lists of nct_ids corresponding to trials that we want to plot
    @return: HTML for generated plot
    """
    print len(trials[0]['ids'])
    print len(trials[0]['score'])
    # socketio = SocketIO(message_queue='amqp://localhost')
    tsne_plot = numpy.load('models/tsne/tsne_matrix_'+LATEST_DATE+'.npy')
    tsne_labels = numpy.load('models/tfidf/nct_ids_'+LATEST_DATE+'.pickle')
    clusters = []
    for trial_list in trials:
        # socketio.sleep(0)

        ix = numpy.isin(tsne_labels, trial_list['ids'])
        ids_indices = numpy.where(ix)[0]
        for i, v in enumerate(trial_list['ids']):
            if v not in tsne_labels and (len(ids_indices) < len(trial_list['score'])):
                del trial_list['score'][i]
        print len(ids_indices)
        ids_vectors = tsne_plot[ids_indices, :]
        clusters.append({'vectors':ids_vectors, 'score':trial_list['score']})
    # socketio.emit('search_update', {'msg': 'Displaying cool plots...'}, room=sess_id)
    # socketio.sleep(0)
    # socketio.emit('page_content', {'section': 'plot', 'data': _plot_mpld3(clusters)}, room=sess_id)
    # socketio.sleep(0)
    return

def get_tsne_points():
    tsne_plot = numpy.load('models/tsne/tsne_matrix_'+LATEST_DATE+'.npy')
    tsne_dict = tsne_plot.tolist()
    return tsne_dict


def test_bokeh(matrices):


    # TOOLS = "hover,crosshair,pan,wheel_zoom,zoom_in,zoom_out,box_zoom,undo,redo,reset,tap,save,box_select,poly_select,lasso_select,"

    p = figure(plot_width=550, plot_height=550)
    xlim = (-69.551894338989271, 64.381507070922851)
    ylim = (-70.038440855407714, 70.644477995300306)
    p.axis.visible = False
    p.border_fill_color = None
    p.outline_line_color = None
    p.grid.visible = None
    p.toolbar.logo = None
    p.toolbar_location = None
    p.x_range = Range1d(start=xlim[0],end =xlim[1])
    p.y_range = Range1d(start=ylim[0],end =ylim[1])

    # p.image_url(url=['color_scatter.png'], x=0, y=0, w=None, h=None, anchor="center")
    p.image_url(url=['static/images/tsne'+LATEST_DATE+'_sml.png'], x=xlim[0]-2.0, y=ylim[1], w=ylim[1]-ylim[0]-2.7, h=(xlim[1]-xlim[0])+6.7, anchor="top_left")

    for i, matrix in enumerate(matrices):
        if len(matrix['score']) > 0:
            p.scatter(matrix['vectors'][:, 0], matrix['vectors'][:, 1],
                      fill_color='#fc6e2d', fill_alpha=0.8,
                      line_color=None, size=2)
        else:
            p.scatter(matrix['vectors'][:, 0], matrix['vectors'][:, 1],
                      fill_color='#5f4af9', fill_alpha=0.8,
                      line_color=None, size=2.5)

    # export_png(p, filename='color_scatter.png')

    # output_file("color_scatter.html", title="color_scatter.py example")
    comp = components(p)
    return comp[0]+comp[1]
    # return file_html(p, CDN)
    # save(p)



if __name__ == "__main__":
    test_bokeh(get_tsne_points())

    # new_tsne = numpy.load('models/tsne/tsne_matrix_2018-03-31.npy')
    # generate new _tsne background plot
    # _new_tsne_img(new_tsne, '2018-03-31')
    # html = _plot_mpld3([])
    # with open('graph_html.html','w+') as file:
    #     file.write(html)




