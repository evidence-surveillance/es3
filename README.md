# trial2rev

## Synopsis

[A shared space for humans and machines to capture links between systematic reviews and clinical trials](http://surveillance-chi.mq.edu.au/)

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

## Development Environment

At the bare minimum you'll need the following for your development environment:

1. [Python](http://www.python.org/)
2. [PostgreSQL](https://www.postgresql.org)
3. [virtualenv](https://python-guide.readthedocs.org/en/latest/dev/virtualenvs/#virtualenv)

### Local Setup

The following assumes you have all of the recommended tools listed above installed.

#### 1. Clone the project:

    $ git clone git@git.aihi.mq.edu.au:paige_newman/srss.git
    $ cd srss

#### 2. Create and initialize virtualenv for the project:

    $ mkvirtualenv srss
    $ pip install -r requirements.txt

#### 3. Run the app on your local machine:
    
    $ python run.py
