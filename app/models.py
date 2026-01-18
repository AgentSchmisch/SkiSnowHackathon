import os
from flask_sqlalchemy import SQLAlchemy
import uuid

db = SQLAlchemy()

def init_db(app):
    # Use environment variable for the connection string
    # Defaulting to sqlite for local dev without docker, but docker will override this
    database_url = os.getenv('DATABASE_URL', 'sqlite:///skigame.db')
    
    # Fix for SQLAlchemy 1.4+ which requires "postgresql://" not "postgres://"
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

class Game(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    join_code = db.Column(db.String(6), unique=True, nullable=False)
    mode = db.Column(db.String(20)) # "drawing" or "conquer"
    status = db.Column(db.String(20), default="lobby")
    players = db.relationship('Player', backref='game', lazy=True)

class Player(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, default=db.func.now())
    game_id = db.Column(db.String(36), db.ForeignKey('game.id'), nullable=False)
    name = db.Column(db.String(100))
    score = db.Column(db.Integer, default=0)
    challenges = db.Column(db.JSON) # Store assigned shapes
    track = db.relationship('Track', backref='player', uselist=False)

class Track(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.String(36), db.ForeignKey('player.id'), nullable=False)
    coordinates = db.Column(db.JSON) # [[lat, lon], ...]
    start_time = db.Column(db.String(50))
    end_time = db.Column(db.String(50))
