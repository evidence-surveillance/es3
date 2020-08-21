from app import app as application
from app import socketio as socketio

if __name__ == "__main__":
    application.jinja_env.cache = {}
    socketio.run(application,debug=True,log_output=True)
