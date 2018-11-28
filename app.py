# SI 364 - F18 - HW4
# matthew wolfgram
# repositories/sources consulted: Sample-Login-App (app.py), User-Authentication(solution.py), Migrations (main_app.py)

import os
import requests
import json
from giphy_api_key import api_key
from flask import Flask, render_template, session, redirect, request, url_for, flash
from flask_script import Manager, Shell
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FileField, PasswordField, BooleanField, SelectMultipleField, ValidationError
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from werkzeug.security import generate_password_hash, check_password_hash

# Imports for login management
from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Application configurations
app = Flask(__name__)
app.debug = True
app.use_reloader = True
app.config['SECRET_KEY'] = 'hardtoguessstring'
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE_URL') or "postgresql://localhost/mrwwolfhw4db" #edit the database URL further if computer requires password to run?
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# App addition setups
manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)

# Login configurations setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app) # set up login manager

########################
######## Models ########
########################

search_gifs = db.Table('search_gifs',db.Column('search_id',db.Integer, db.ForeignKey('SearchTerm.id')),db.Column('gif_id',db.Integer, db.ForeignKey('Gif.id')))

user_collection = db.Table('user_collection',db.Column('gif_id',db.Integer, db.ForeignKey('Gif.id')),db.Column('collection_id',db.Integer, db.ForeignKey('PersonalGifCollection.id')))

## User-related Models

# Special model for users to log in
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    collection = db.relationship("PersonalGifCollection", backref = "User") # *** #

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

## DB load function
## Necessary for behind the scenes login manager that comes with flask_login capabilities! Won't run without this.
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) # returns User object or None

# TODO 364: Read through all the models tasks before beginning them so you have an understanding of what the database structure should be like. Consider thinking about it as a whole and drawing it out before you write this code.

# Model to store gifs
class Gif(db.Model):

    __tablename__ = "Gif"
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(128))
    url = db.Column(db.String(256))

    def __repr__(self):
        return " title: {} // url: {} ".format(self.title, self.url)

# Model to store a personal gif collection

class PersonalGifCollection(db.Model):

    __tablename__ = "PersonalGifCollection"
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(255))
    userid = db.Column(db.Integer, db.ForeignKey("users.id"))
    gifs = db.relationship("Gif", secondary = user_collection, backref = db.backref("PersonalGifCollection", lazy = "dynamic"), lazy = "dynamic") #capitalization of "Gif" here??


class SearchTerm(db.Model):
    __tablename__ = "SearchTerm"
    id = db.Column(db.Integer, primary_key = True)
    term = db.Column(db.String(32), unique = True)
    gifs = db.relationship("Gif", secondary = search_gifs, backref = db.backref("SearchTerm", lazy = "dynamic"), lazy = "dynamic")
    def __repr__(self):
        return 'term: {}'.format(self.term)

########################
######## Forms #########
########################

# Provided
class RegistrationForm(FlaskForm):
    email = StringField('Email:', validators=[Required(),Length(1,64),Email()])
    username = StringField('Username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Usernames must have only letters, numbers, dots or underscores')])
    password = PasswordField('Password:',validators=[Required(),EqualTo('password2',message="Passwords must match")])
    password2 = PasswordField("Confirm Password:",validators=[Required()])
    submit = SubmitField('Register User')

    #Additional checking methods for the form
    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')

# Provided
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')

# TODO 364: The following forms for searching for gifs and creating collections are provided and should not be edited. You SHOULD examine them so you understand what data they pass along and can investigate as you build your view functions in TODOs below.
class GifSearchForm(FlaskForm):
    search = StringField("Enter a term to search GIFs", validators=[Required()])
    submit = SubmitField('Submit')

class CollectionCreateForm(FlaskForm):
    name = StringField('Collection Name',validators=[Required()])
    gif_picks = SelectMultipleField('GIFs to include')
    submit = SubmitField("Create Collection")

########################
### Helper functions ###
########################

def get_gifs_from_giphy(search_string):
    """ Returns data from Giphy API with up to 5 gifs corresponding to the search input"""
    url = "https://api.giphy.com/v1/gifs/search"
    params = {}
    term = search_string
    params["api_key"] = api_key
    params["q"] = term
    params["limit"]  = "5"

    response = requests.get(url, params)
    result = response.text
    data = json.loads(result)['data']
    return data

# Provided
def get_gif_by_id(id):
    """Should return gif object or None"""
    g = Gif.query.filter_by(id=id).first()
    return g

def get_or_create_gif(title, url):
    """Always returns a Gif instance"""
    gifford = Gif.query.filter_by(title = title).first()

    if gifford:
        return gifford

    else:
        fresh_gif = Gif(title = title, url = url)
        db.session.add(fresh_gif)
        db.session.commit() #db.session.close? where should it go?
        return fresh_gif

def get_or_create_search_term(term):
    """Always returns a SearchTerm instance"""
    instance = SearchTerm.query.filter_by(term = term).first()

    if instance:
        return instance

    else:
        new_instance = SearchTerm(term = term)
        these_data = get_gifs_from_giphy(term)
        for gif in these_data:
            title = gif['title']
            url = gif['url']
            invoke = get_or_create_gif(title, url)
            # instance.gifs.append(gif) # *** ???
        db.session.add(new_instance)
        db.session.commit()
        return new_instance

def get_or_create_collection(name, current_user, gif_list=[]):
    """Always returns a PersonalGifCollection instance"""
    instance = PersonalGifCollection.query.filter_by(title = name, userid = current_user.id).first()

    if instance:
        return instance

    else:
        new_instance = PersonalGifCollection(title = name, userid = current_user.id, gifs = gif_list)
        for gif in gif_list:
            new_instance.gifs.append(gif)

        db.session.add(new_instance)
        db.session.commit()
        return new_instance


########################
#### View functions ####
########################

## Error handling routes
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


## Login-related routes - provided
@app.route('/login',methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html',form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('index'))

@app.route('/register',methods=["GET","POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,username=form.username.data,password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You can now log in!')
        return redirect(url_for('login'))
    # *** ??? if form.errors: flash([error for errors in form.errors.values() for error in errors])
    return render_template('register.html',form=form)

@app.route('/secret')
@login_required
def secret():
    return "Only authenticated users can do this! Try to log in or contact the site admin."

## Other routes
@app.route('/', methods=['GET', 'POST'])
def index():
    form = GifSearchForm()
    if form.validate_on_submit():
        term = form.search.data
        initialize = get_or_create_search_term(term)
        return redirect(url_for('search_results', search_term = term))
    # *** ??? if form.errors: flash([error for errors in form.errors.values() for error in errors])
    return render_template('index.html',form = form)

# Provided
@app.route('/gifs_searched/<search_term>')
def search_results(search_term):
    term = SearchTerm.query.filter_by(term=search_term).first()
    relevant_gifs = term.gifs.all()
    return render_template('searched_gifs.html',gifs=relevant_gifs,term=term)

@app.route('/search_terms')
def search_terms():
    each_term = SearchTerm.query.all()
    return render_template('search_terms.html', all_terms = each_term)

# Provided
@app.route('/all_gifs')
def all_gifs():
    gifs = Gif.query.all()
    return render_template('all_gifs.html',all_gifs=gifs)

@app.route('/create_collection',methods=["GET","POST"])
@login_required
def create_collection():
    form = CollectionCreateForm()
    gifs = Gif.query.all()
    choices = [(g.id, g.title) for g in gifs]
    form.gif_picks.choices = choices

    if request.method == "POST":
        data = form.gif_picks.data
        name = form.name.data
        objects = [get_gif_by_id(int(x)) for x in data]
        collect = get_or_create_collection(name = data, current_user = current_user, gif_list = objects)
        return redirect(url_for("collections"))
    return render_template("create_collection.html", form = form)

@app.route('/collections',methods=["GET","POST"])
@login_required
def collections():
    the_collect = PersonalGifCollection.query.filter_by(userid = current_user.id).all()
    return render_template("collections.html", collections = the_collect)

# Provided
@app.route('/collection/<id_num>')
def single_collection(id_num):
    id_num = int(id_num)
    collection = PersonalGifCollection.query.filter_by(id=id_num).first()
    gifs = collection.gifs.all()
    return render_template('collection.html',collection=collection, gifs=gifs)

if __name__ == '__main__':
    db.create_all()
    manager.run()
