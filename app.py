import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_sqlalchemy import session
from flask import send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func





app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///youtube_clone.db'
app.config['SECRET_KEY'] = 'S11528GDFNIS2'


app.config['UPLOAD_FOLDER_VIDEOS'] = 'static/uploads'
app.config['UPLOAD_FOLDER_PROFILES'] = 'static/profile_pics'


os.makedirs(app.config['UPLOAD_FOLDER_VIDEOS'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_PROFILES'], exist_ok=True)






app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    profile_picture = db.Column(db.String(300), nullable=False, default="static/profile_pics/default.png")



class Video(db.Model):
    __tablename__ = 'video'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    thumbnail = db.Column(db.String(300), nullable=False, default='static/thumbnails/default.png')
    likes = db.relationship('Like', backref='video', lazy=True)
    comments = db.relationship('Comment', back_populates='video', lazy=True, cascade="all, delete-orphan")


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)


    __table_args__ = (db.UniqueConstraint('user_id', 'video_id', name='unique_like'),)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.relationship('CommentLike', backref='comment', lazy=True, cascade="all, delete-orphan")

    user = db.relationship('User', backref=db.backref('comments', lazy=True))
    video = db.relationship('Video', back_populates='comments')





@app.route('/delete_video/<int:video_id>', methods=['POST'])
@login_required
def delete_video(video_id):
    video = Video.query.get(video_id)

    if not video:
        flash("Video not found.", "error")
        return redirect(url_for('profile'))

    if video.uploader_id != current_user.id:
        flash("You are not authorized to delete this video.", "error")
        return redirect(url_for('profile'))


    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)


    if os.path.exists(video_path):
        os.remove(video_path)


    db.session.delete(video)
    db.session.commit()

    flash("Video deleted successfully.", "success")
    return redirect(url_for('profile'))




@app.route('/update_username', methods=['POST'])
@login_required
def update_username():
    new_username = request.form.get('new_username')
    if new_username:
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user:
            flash("This username is already taken!", "error")
        else:
            current_user.username = new_username
            db.session.commit()
            flash("Username updated successfully. Please log in again.", "success")
            logout_user()
            return redirect(url_for('login'))
    return redirect(url_for('profile'))



@app.route('/update_profile_picture', methods=['POST'])
@login_required
def update_profile_picture():
    if 'profile_picture' not in request.files:
        flash("No file uploaded!", "error")
        return redirect(url_for('profile'))

    file = request.files['profile_picture']
    if file.filename == '':
        flash("No selected file!", "error")
        return redirect(url_for('profile'))


    filename = secure_filename(f"{current_user.id}.png")
    filepath = os.path.join(app.config['UPLOAD_FOLDER_PROFILES'], filename)

    print(f"Saving file to: {filepath}")

    file.save(filepath)


    current_user.profile_picture = f"{app.config['UPLOAD_FOLDER_PROFILES']}/{filename}"
    db.session.commit()
    flash("Profile picture updated successfully!", "success")

    return redirect(url_for('profile'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            error = "Passwords do not match!"
            return render_template('register.html', error=error)

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/profile')
@login_required
def profile():
    user_videos = Video.query.filter_by(uploader_id=current_user.id).all()
    return render_template('profile.html', videos=user_videos)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if not user:
            error = "Invalid username."
            return render_template('login.html', error=error)

        if not check_password_hash(user.password, password):
            error = "Invalid password."
            return render_template('login.html', error=error)

        login_user(user)
        return redirect(url_for('index'))

    return render_template('login.html')
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/')
def index():
    videos = Video.query.outerjoin(Like).group_by(Video.id).order_by(db.func.count(Like.id).desc()).all()
    return render_template('index.html', videos=videos)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
@login_required
def upload_video():
    if 'video' not in request.files:
        return "No file part", 400
    file = request.files['video']
    if file.filename == '':
        return "No selected file", 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    thumbnail_path = 'static/thumbnails/czarnetlominiaturkayt.png'
    new_video = Video(filename=filename, uploader_id=current_user.id, thumbnail=thumbnail_path)
    db.session.add(new_video)
    db.session.commit()
    return redirect(url_for('watch_video', filename=filename))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, mimetype='video/mp4')
@app.route('/watch/<filename>')
def watch_video(filename):
    video = Video.query.filter_by(filename=filename).first()
    if not video:
        return "Video not found", 404
    comments = (
        db.session.query(Comment)
        .filter_by(video_id=video.id)
        .outerjoin(CommentLike)
        .group_by(Comment.id)
        .order_by(func.count(CommentLike.id).desc())
        .all()
    )
    return render_template("video.html", video=video, comments=comments)


@app.route('/change_thumbnail/<int:video_id>', methods=['POST'])
@login_required
def change_thumbnail(video_id):
    video = Video.query.get(video_id)

    if not video or video.uploader_id != current_user.id:
        flash("Unauthorized action!", "error")
        return redirect(url_for('profile'))

    if 'thumbnail' not in request.files:
        flash("No file uploaded!", "error")
        return redirect(url_for('profile'))

    file = request.files['thumbnail']
    if file.filename == '':
        flash("No selected file!", "error")
        return redirect(url_for('profile'))

    filename = secure_filename(f"thumbnail_{video_id}.png")
    filepath = os.path.join("static/thumbnails", filename)
    file.save(filepath)

    video.thumbnail = f"static/thumbnails/{filename}"
    db.session.commit()

    flash("Thumbnail updated successfully!", "success")
    return redirect(url_for('profile'))


@app.route('/change_title/<int:video_id>', methods=['POST'])
@login_required
def change_title(video_id):
    video = Video.query.get(video_id)

    if not video or video.uploader_id != current_user.id:
        flash("Unauthorized action!", "error")
        return redirect(url_for('profile'))

    new_title = request.form.get('new_title')

    if new_title:
        old_filename = video.filename
        new_filename = secure_filename(new_title) + ".mp4"  # Zmiana na poprawny format


        old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_filename)
        new_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)


        if os.path.exists(old_path):
            os.rename(old_path, new_path)


        video.filename = new_filename
        db.session.commit()
        flash("Title updated successfully!", "success")

    return redirect(url_for('profile'))



@app.route('/like/<int:video_id>', methods=['POST'])
@login_required
def like_video(video_id):
    video = Video.query.get_or_404(video_id)

    existing_like = Like.query.filter_by(user_id=current_user.id, video_id=video_id).first()

    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        flash("Like removed!", "info")
    else:
        new_like = Like(user_id=current_user.id, video_id=video_id)
        db.session.add(new_like)
        db.session.commit()
        flash("You liked this video!", "success")

    return redirect(url_for('watch_video', filename=video.filename))

@app.route('/add_comment/<int:video_id>', methods=['POST'])
@login_required
def add_comment(video_id):
    text = request.form.get('comment_text')

    if text:
        new_comment = Comment(text=text, user_id=current_user.id, video_id=video_id)
        db.session.add(new_comment)
        db.session.commit()

    return redirect(url_for('watch_video', filename=Video.query.get(video_id).filename))


class CommentLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'comment_id', name='unique_comment_like'),)


@app.route('/like_comment/<int:comment_id>', methods=['POST'])
@login_required
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    existing_like = CommentLike.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()

    if existing_like:
        db.session.delete(existing_like)
    else:
        new_like = CommentLike(user_id=current_user.id, comment_id=comment_id)
        db.session.add(new_like)

    db.session.commit()
    return redirect(request.referrer)



admin = Admin(app)
admin.add_view(ModelView(User, db.session))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5001, debug=True)


