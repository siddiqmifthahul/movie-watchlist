import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-ganti-nanti")
# Lokal pakai SQLite. Di AWS tinggal set env DATABASE_URL ke endpoint RDS, contoh:
# mysql+pymysql://user:password@endpoint-rds:3306/moviedb
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///movies.db")
db = SQLAlchemy(app)

GENRES = ["Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary",
          "Drama", "Fantasy", "Horror", "Mystery", "Romance", "Sci-Fi",
          "Thriller", "War", "Other"]
STATUSES = {"planned": "Want to watch", "watching": "Watching", "watched": "Watched"}


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    genre = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer)
    status = db.Column(db.String(20), nullable=False, default="planned")
    rating = db.Column(db.Integer)  # 1-10, optional
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()


def read_form():
    """Ambil + validasi data form. Return (data, error)."""
    f = request.form
    title = f.get("title", "").strip()
    genre = f.get("genre", "")
    status = f.get("status", "planned")
    if not title:
        return None, "Title is required."
    if genre not in GENRES:
        return None, "Pick a genre."
    if status not in STATUSES:
        return None, "Invalid status."

    def to_int(name, lo, hi):
        raw = f.get(name, "").strip()
        if not raw:
            return None
        if not raw.isdigit() or not lo <= int(raw) <= hi:
            raise ValueError(f"{name.capitalize()} must be between {lo} and {hi}.")
        return int(raw)

    try:
        year = to_int("year", 1888, datetime.now().year + 5)
        rating = to_int("rating", 1, 10)
    except ValueError as e:
        return None, str(e)

    return dict(title=title, genre=genre, status=status, year=year,
                rating=rating, notes=f.get("notes", "").strip() or None), None


@app.route("/")
def index():
    status = request.args.get("status", "")
    genre = request.args.get("genre", "")
    q = Movie.query
    if status in STATUSES:
        q = q.filter_by(status=status)
    if genre in GENRES:
        q = q.filter_by(genre=genre)
    movies = q.order_by(Movie.created_at.desc()).all()
    counts = {k: Movie.query.filter_by(status=k).count() for k in STATUSES}
    return render_template("index.html", movies=movies, statuses=STATUSES,
                           genres=GENRES, counts=counts,
                           active_status=status, active_genre=genre)


@app.route("/movie/new", methods=["GET", "POST"])
def add_movie():
    if request.method == "POST":
        data, error = read_form()
        if error:
            flash(error)
            return render_template("form.html", movie=request.form, genres=GENRES,
                                   statuses=STATUSES, editing=False)
        db.session.add(Movie(**data))
        db.session.commit()
        flash(f"Added “{data['title']}”.")
        return redirect(url_for("index"))
    return render_template("form.html", movie={}, genres=GENRES,
                           statuses=STATUSES, editing=False)


@app.route("/movie/<int:movie_id>/edit", methods=["GET", "POST"])
def edit_movie(movie_id):
    movie = db.get_or_404(Movie, movie_id)
    if request.method == "POST":
        data, error = read_form()
        if error:
            flash(error)
            return render_template("form.html", movie=request.form, genres=GENRES,
                                   statuses=STATUSES, editing=True, movie_id=movie_id)
        for k, v in data.items():
            setattr(movie, k, v)
        db.session.commit()
        flash(f"Saved “{movie.title}”.")
        return redirect(url_for("index"))
    return render_template("form.html", movie=movie, genres=GENRES,
                           statuses=STATUSES, editing=True, movie_id=movie_id)


@app.route("/movie/<int:movie_id>/status", methods=["POST"])
def set_status(movie_id):
    movie = db.get_or_404(Movie, movie_id)
    new = request.form.get("status")
    if new in STATUSES:
        movie.status = new
        db.session.commit()
    return redirect(request.referrer or url_for("index"))


@app.route("/movie/<int:movie_id>/delete", methods=["POST"])
def delete_movie(movie_id):
    movie = db.get_or_404(Movie, movie_id)
    db.session.delete(movie)
    db.session.commit()
    flash(f"Deleted “{movie.title}”.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    # host 0.0.0.0 biar bisa diakses dari luar (dibutuhkan di EC2)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("DEBUG") == "1")
