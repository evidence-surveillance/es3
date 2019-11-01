import webAPIs
import glob
from urllib.request import urlopen
import zipfile
import os
import httplib
from datetime import  datetime
import bot
import scipy.sparse
import tsne
import matfac_impl as mf

def patch_http_response_read(func):
    def inner(*args):
        try:
            return func(*args)
        except httplib.IncompleteRead, e:
            return e.partial
    return inner
httplib.HTTPResponse.read = patch_http_response_read(httplib.HTTPResponse.read)


response = urlopen("https://clinicaltrials.gov/AllPublicXML.zip")
local_filename = "test_folder.zip"
CHUNK = 16 * 1024
with open(local_filename, 'wb') as f:
    while True:
        chunk = response.read(CHUNK)
        if not chunk:
            break
        f.write(chunk)


with zipfile.ZipFile("test_folder.zip","r") as zip_ref:
    zip_ref.extractall("nct_xml/")

path = "nct_xml/NCT*/NCT*.xml"
for fname in glob.glob(path):
    webAPIs.update_record(fname)
    os.remove(fname)

os.remove('test_folder.zip')
#
# date = '2018-04-17'
date = str(datetime.now().date())
bot.DATE = date
#
bot.update_tfidf()
# # load new tfidf matrix
tfidf_matrix = scipy.sparse.load_npz('models/tfidf/tfidf_matrix_' + date + '.npz')
# # generate new TSNE plot
tsne.regenerate(tfidf_matrix, date)
# generate newest matfac suggestions

# do other bots
bot.update_others()

#THEN basicbot 2 & matfacbot
bot.update_basicbot2.delay()

mf.update_results(date)

#TODO: run basicbot1, basicbot2 again, epistemonikos & crossref?



