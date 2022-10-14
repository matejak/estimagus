import flask

from app import app
# import app.forms
from app.forms import LoginForm, PointEstimationForm, NumberEstimationForm

@app.route('/')
@app.route('/index')
def index():
    return "Hello, World!"


@app.route('/login')
def login():
    form = LoginForm()
    return flask.render_template('login.html', title='Sign In', form=form)


@app.route('/estimate')
def estimate():
    form = NumberEstimationForm() 
    return flask.render_template('issue_view.html', title='Estimate Issue', form=form)