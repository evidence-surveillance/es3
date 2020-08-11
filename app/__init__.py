from eventlet import monkey_patch

monkey_patch()
from flask import Flask
from celery import Celery
import config
from flask_socketio import SocketIO
from flask_bootstrap import Bootstrap
from flask_mail import Mail
from flask_bootstrap import WebCDN
from flask_caching import Cache

app = Flask(__name__)  # init Flask

Bootstrap(app)  # init Bootstrap
app.extensions['bootstrap']['cdns']['jquery'] = WebCDN(
    '//cdnjs.cloudflare.com/ajax/libs/jquery/3.3.1/'
)

cache = Cache(app, config={'CACHE_TYPE': 'simple'})

app.config['MAIL_SERVER'] = config.MAIL_SERVER
app.config['MAIL_PORT'] = config.MAIL_PORT
app.config['MAIL_USERNAME'] = config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = config.MAIL_PASSWORD
app.config['MAIL_USE_TLS'] = config.MAIL_USE_TLS
app.config['MAIL_USE_SSL'] = config.MAIL_USE_SSL
mail = Mail(app)  # for sending password reset emails

celery_inst = Celery(app.name, broker=config.CELERY_BROKER_URL, backend=config.CELERY_RESULT_BACKEND)
celery_inst.conf.update(app.config)
celery_inst.autodiscover_tasks()

app.secret_key = config.APP_SECRET_KEY

socketio = SocketIO(app, message_queue='amqp://localhost')

from . import views
