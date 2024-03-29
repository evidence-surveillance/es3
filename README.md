# ES3 (Formerly known as trial2rev)
[![DOI](https://zenodo.org/badge/147290127.svg)](https://zenodo.org/badge/latestdoi/147290127)
## Synopsis

[A shared space for humans and machines to capture links between systematic reviews and clinical trials](http://es3-bidh.sydney.edu.au/)


## Getting Started

*(Please note that there are a number of steps involved in getting the system up and running, and this guide is
 fairly minimal, assumes familiarity with the es3 website and experience working with the tools listed below, and is **not intended for use in production**. We may consider Dockerizing the system or providing a more comprehensive step-by-step guide
 in future if there is demand for this)*


 At the bare minimum you'll need the following for your development environment:

1. [Python](http://www.python.org/)
2. [PostgreSQL](https://www.postgresql.org)
3. [virtualenv](https://python-guide.readthedocs.org/en/latest/dev/virtualenvs/#virtualenv)
4. [RabbitMQ](https://www.rabbitmq.com/)
5. [Git](https://git-scm.com/downloads)

### Initialisation

The following assumes you have all of the recommended tools listed above installed. Note that this has only been tested on `Centos 7` and `Amazon Linux 2`.

#### 1. Clone the project:

    $ git clone username@github.com:evidence-surveillance/trial2rev.git trial2rev

#### 2. Create and initialize virtualenv for the project:

    $ virtualenv venv
    $ source venv/bin/activate
    $ (venv) pip install -r requirements.txt

#### 3. Create `config.py` file for your local setup based on `config.py.example`:
Being sure to include all of the config values listed, including your PostgreSQL username & password, the name of the database you'll be creating (`trial2rev` in this example),
flask secret key, EUtils API key, mail server details, etc.


#### 4. Connect to PostgreSQL and create the database:
    $ (venv) psql postgres
    $ postgres=> CREATE DATABASE trial2rev;
    $ postgres=> \q

#### 5. Create tables for the database:
    $  psql -f test/data/srss.sql trial2rev

#### 6. Populate the database:
You can populate the database with systematic reviews, trial registry
entries, and trial publications by executing the relevant methods in
`remote_tasks.py`. It is recommended that you first pull trial registry entries from
ClinicalTrials.gov using

    $ (venv) python
    $ >>> import remote_tasks as rt
    $ >>> rt.update_tregistry_entries(5000)

which will pull all registered trials added or updated in the last
 `5000` days.
 Then, you may pull PubMed articles with automatic links to ClinicalTrials.gov:

    $ >>> rt.update_trial_publications(5000)

 and finally, pull systematic reviews that reference trial publications with links, or
 ClinicalTrials.gov directly:

    $ >>> rt.populate_reviews(5000)

this will also automatically retrieve linked trials for each review found via CrossRef or CDSR

#### 7. Make predictions:
First, you'll need to generate the tfidf matrix of trial registry text

    $ >>> rt.update_tfidf()

then, you can trigger `basicbot1` and `basicbot2` which predict relevant trials based on document similarity

    $ >>> rt.update_basicbot()
    $ >>> rt.update_basicbot2()

once you have a number of reviews with a few included trials each, you can try
running matrix factorization to predict addidional relevant trials for these reviews. Credit to [@dsurian](https://github.com/dsurian) for the code, repo can be found [here](https://github.com/dsurian/matfac).

    $ >>> import matfac_impl as mi
    $ >>> mi.update_results()

#### 8. Generate TSNE:
You'll recieve errors if you attempt to access the website without generating a TSNE
plot of the trial registry tfidf scores. You can do this by calling the method:

    $ >>> rt.regenerate_tsne()

### Web server
Now, everything should be ready for you to start the webserver and browse your local
version of ES3!

#### 1. Run the app on your local machine:

    $ (venv) python run.py

#### 2. Start the celery worker:
    $ (venv) celery -A app.celery_inst worker --loglevel=info


#### 3. Log in:
   The site should now be visible on http://127.0.0.1:5000

   You can log in using the default user:
   * username: admin@admin.com
   * password: admin

   Once logged in, you can create new users here: http://127.0.0.1:5000/admin


## Acknowledgements

This project is supported by supported by the AWS Cloud Credits for Research program.   
I have incorporated modified and original code from the [metapub](https://bitbucket.org/metapub/metapub) library into
`ecitmatch_tools.py`, which is licensed under the Apache 2.0 license.
I have also used my own fork of the [eutils](https://github.com/biocommons/eutils) library, to which I have added functionality to extract additional metadata from PubMed articles.
I cannot be grateful enough to all contributors of both of these libraries, which have been absolutely instrumental in the development of this project.
