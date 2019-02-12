import numpy
import utils


def get_tsne_data(trials):
    """
    Resolve  nct_ids to their coordinates in saved TSNE matrix and return them along
    with the color of each data point, and the path to the background image
    @param trials: lists of nct_ids corresponding to trials
    @return: data to plot
    """
    tsne_plot = numpy.load(utils.most_recent_tsne())
    tsne_labels = numpy.load(utils.most_recent_tfidf_labels())
    rel_ids = [trial['nct_id'] for trial in trials if trial['relationship']=='relevant']
    incl_ids = [trial['nct_id'] for trial in trials if trial['relationship']=='included']
    ix = numpy.isin(tsne_labels, rel_ids)
    ids_indices = numpy.where(ix)[0]
    vectors = tsne_plot[ids_indices, :]
    colours = ['#fc6e2d' for x in range(vectors.shape[0])]
    if incl_ids:
        ix = numpy.isin(tsne_labels, incl_ids)
        ids_indices = numpy.where(ix)[0]
        incl_vectors = tsne_plot[ids_indices, :]
        colours = colours + ['#5f4af9' for x in range(incl_vectors.shape[0])]
        vectors = numpy.concatenate((vectors, incl_vectors), axis=0)
    rel_path = utils.most_recent_tsne_img()
    rel_path = rel_path[rel_path.index('static'):]
    return {'x':vectors[:, 0].tolist(), 'y':vectors[:, 1].tolist(),'img':rel_path, 'colours':colours}


