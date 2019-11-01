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

mail = Mail(app)  # for sending password reset emails

celery_inst = Celery(app.name, broker=config.CELERY_BROKER_URL, backend=config.CELERY_RESULT_BACKEND)
# print(celery_inst)
celery_inst.conf.update(app.config)
# celery_inst.autodiscover_tasks()

app.secret_key = config.APP_SECRET_KEY

socketio = SocketIO(app, message_queue='amqp://localhost')

import views
