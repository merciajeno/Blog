from functools import wraps

import flask
from flask import Flask, render_template, redirect, url_for, request
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Text, ForeignKey
from flask_wtf import FlaskForm
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor, CKEditorField
from datetime import date
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_login import LoginManager, login_user, UserMixin, login_required, logout_user,current_user
from flask import abort,flash
from typing import List


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
Bootstrap5(app)
app.config['CKEDITOR_PKG_TYPE'] = 'basic'
ckeditor = CKEditor(app)



# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

def admin_only(f):
    @wraps(f)
    def decorated_function(*args,**kwargs):
        if current_user.id!=1:
            return abort(403)
        return f(*args,**kwargs)
    return decorated_function

# CONFIGURE TABLE
class BlogPost(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped["User"] =  relationship(back_populates="blogs")
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    author_id :Mapped[int] = mapped_column(ForeignKey("user.id"))
    comments :Mapped[List["Comment"]] = relationship(back_populates="blog")


class User(UserMixin,db.Model):
    __tablename__='user'
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    name :Mapped[str] = mapped_column(String(250),unique=False,nullable=False)
    email :Mapped[str]=mapped_column(String(250),unique=True,nullable=False)
    password: Mapped[str] =mapped_column(String(250),unique=False,nullable=False)
    blogs : Mapped[List["BlogPost"]] = relationship(back_populates="author")
    comments : Mapped[List["Comment"]] = relationship(back_populates="user")

class Comment(db.Model):
    __tablename__ ='comment'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    text:Mapped[str]=mapped_column(String(1000),unique=False,nullable=False)
    blog :Mapped["BlogPost"] = relationship(back_populates="comments")
    blog_id :Mapped[int] = mapped_column(ForeignKey("blog_post.id"))
    user :Mapped["User"]=relationship(back_populates="comments")
    user_id :Mapped[int] = mapped_column(ForeignKey("user.id"))



with app.app_context():
    db.create_all()




@app.route('/')
def get_all_posts():
    # TODO: Query the database for all the posts. Convert the data to a python list.
    posts = db.session.query(BlogPost).all()
    return render_template("index.html", all_posts=posts)

# TODO: Add a route so that you can click on individual posts.

@app.route('/posts/<int:post_id>')
def show_post(post_id):
    # TODO: Retrieve a BlogPost from the database based on the post_id
    requested_post = db.session.get(BlogPost,post_id)
    comment_form = CommentForm()
    similar_posts = get_similar_posts(post_id)
    print(similar_posts)
    return render_template("post.html", post=requested_post,form=comment_form,similar_posts=similar_posts)



# Below is the code from previous lessons. No changes needed.
@app.route("/about")
def about():
    return render_template("about.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        # Get data from form
        email = form.email.data
        password = form.password.data

        # Look up user by email
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()

        if user and check_password_hash(user.password, password):
            # Login successful
            login_user(user)
            return redirect(url_for('get_all_posts'))
        else:
            # Invalid login
            flash("Invalid email or password, please try again.")

    # GET or failed POST → show login page again
    return render_template("login.html", form=form)


@app.route('/register',methods=['GET','POST'])
def register():
    register_form = RegisterForm()
    if request.method=='POST':
        print('Registered')
        hashed_password=generate_password_hash(
            register_form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        if db.session.execute(db.select(User).where(User.email == register_form.email.data)).scalar():

            return redirect(url_for('login'))

        user = User(
            name=register_form.name.data,
            email=register_form.email.data,
            password = hashed_password
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('get_all_posts'))
    return render_template('register.html',form=register_form
                           )

@app.route("/contact",methods=['GET','POST'])
def contact():
    if request.method=='POST':
        form = request.form
        print(form)
        return render_template('contact.html',msg_sent=True)
    return render_template("contact.html",msg_sent=False)


@app.route('/new_post',methods=['GET','POST'])
@admin_only
def add_post():

    form = CreatePostForm()
    print(current_user.name)
    if request.method=='POST':
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_user.id,
            date=date.today().strftime("%B %d, %Y")
        )
        print('Added new post')
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form,edit=False)

@app.route('/edit_post/<int:id>', methods=['GET', 'POST'])
@admin_only
def edit_post(id):
    # Step 1: Get the existing post
    post = db.session.get(BlogPost, id)
    if not post:
        return "Post not found", 404

    # Step 2: Create the form, pre-fill with post data
    form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )

    # Step 3: On submit, update post and save
    if request.method=='POST':
        print('Edited the form')
        post.title = form.title.data
        post.subtitle = form.subtitle.data
        post.img_url = form.img_url.data
        post.body = form.body.data

        db.session.commit()
        return redirect(url_for('get_all_posts'))

    # Step 4: Render template for GET request
    return render_template(
        'make-post.html',
        form=form,
        edit=True,   # so you see "Edit Post" in template
        existing_post=post
    )

@app.route('/delete_post/<int:id>')
@admin_only
def delete_post(id):
    post = db.session.get(BlogPost,id)
    if post:
        print('Post deleted')
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('get_all_posts'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def get_similar_posts(current_post_id, limit=3):
    posts = BlogPost.query.all()

    # Get list of post ids and combined text (title + subtitle)
    ids = [post.id for post in posts]
    documents = [f"{post.title} {post.subtitle}" for post in posts]

    # TF-IDF vectorization
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(documents)

    # Find index of the current post
    try:
        index = ids.index(current_post_id)
    except ValueError:
        return []

    # Compute cosine similarity
    cosine_sim = cosine_similarity(tfidf_matrix[index:index + 1], tfidf_matrix).flatten()

    # Get indices of top similar posts excluding the current one
    similar_indices = cosine_sim.argsort()[::-1]

    # Filter out current post and low similarity scores
    filtered = [
        i for i in similar_indices
        if i != index and cosine_sim[i] > 0.2
    ][:limit]  # Limit to top N

    similar_posts = [posts[i] for i in filtered]
    return similar_posts



@app.route('/posts/<int:id>',methods=['POST','GET'])
def comment(id):
    form = CommentForm()
    if request.method=='POST':
        new_comment = Comment(
            text=form.comment_text.data,
            user_id=current_user.id,
            blog_id=id
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('get_all_posts', post_id=id))

        # If GET → show the post + comments
    post = db.session.get(BlogPost, id)

    return render_template("post.html", post=post, form=form)

if __name__ == "__main__":
    app.run(debug=True, port=5003)
