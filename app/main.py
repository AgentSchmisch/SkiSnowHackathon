import uuid
import random
import time
from flask import Flask, jsonify, request, abort
from sqlalchemy.exc import OperationalError
from app.models import db, init_db, Game, Player, Track

def create_app():
    app = Flask(__name__)
    init_db(app)
    with app.app_context():
        retries = 5
        while retries > 0:
            try:
                db.create_all()
                break
            except OperationalError:
                retries -= 1
                print(f"Waiting for database... {retries} retries left")
                time.sleep(2)
    return app

app = create_app()

# Constants
SHAPES = ["Star", "Heart", "Circle", "Square", "Triangle", "ZigZag"]
PHASES = ["lobby", "recording", "guessing", "results"]
ADJECTIVES = ["Speedy", "Frosty", "Gnarly", "Zesty", "Powder"]
NOUNS = ["Skier", "Yeti", "Penguin", "Carver", "Avalanche"]

def generate_fun_name():
    return f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)} {random.randint(10, 99)}"

def generate_join_code():
    return ''.join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=6))

# --- LOBBY & UTILITIES ---

@app.route('/games/resolve/<join_code>', methods=['GET'])
def resolve_join_code(join_code):
    """Spec 1: Resolve a joinCode to a gameId."""
    game = Game.query.filter_by(join_code=join_code.upper()).first_or_404()
    return jsonify({"gameId": game.id})

@app.route('/games', methods=['POST'])
def create_game():
    data = request.json or {}
    new_game = Game(
        id=str(uuid.uuid4()),
        join_code=generate_join_code(),
        mode=data.get("gameMode", "drawing"),
        status="lobby"
    )
    # The creator is automatically the host (assigned on first join)
    db.session.add(new_game)
    db.session.commit()
    return jsonify({"gameId": new_game.id, "joinCode": new_game.join_code}), 201

@app.route('/games/<game_id>', methods=['GET'])
def get_game_status(game_id):
    """Spec 3 & 7: Include metadata and fix Serialization error."""
    game = Game.query.get_or_404(game_id)
    
    # We'll treat the first player as the host for simplicity
    players = Player.query.filter_by(game_id=game_id).order_by(Player.created_at).all()
    host_id = players[0].id if players else None

    return jsonify({
        "gameId": game.id,
        "joinCode": game.join_code,
        "hostPlayerId": host_id,
        "status": game.status, # lobby/started/finished
        "phase": getattr(game, 'phase', 'lobby'), # Spec 4
        "mode": game.mode,
        "players": [
            {
                "playerId": p.id,
                "playerName": p.name,
                "score": p.score,
                "hasSubmittedTrack": p.track is not None
            } for p in players
        ]
    })

@app.route('/games/<game_id>', methods=['PATCH'])
def update_game(game_id):
    """Spec 2: Update game mode/phase before or during play."""
    game = Game.query.get_or_404(game_id)
    data = request.json or {}
    
    if "gameMode" in data:
        game.mode = data["gameMode"]
    if "phase" in data:
        game.status = data["phase"] # Mapping phase to status for now
        
    db.session.commit()
    return jsonify({"status": "updated", "mode": game.mode})

# --- PLAYER ACTIONS ---

@app.route('/games/<game_id>/join', methods=['POST'])
def join_game(game_id):
    game = Game.query.get_or_404(game_id)
    new_player = Player(
        id=str(uuid.uuid4()),
        game_id=game.id,
        name=generate_fun_name(),
        score=0
    )
    db.session.add(new_player)
    db.session.commit()
    return jsonify({"playerId": new_player.id, "playerName": new_player.name})

@app.route('/games/<game_id>/leave', methods=['POST'])
def leave_game(game_id):
    """Spec 5: Player leaves the game."""
    data = request.json or {}
    player_id = data.get("playerId")
    player = Player.query.filter_by(id=player_id, game_id=game_id).first_or_404()
    
    db.session.delete(player)
    db.session.commit()
    return jsonify({"status": "left_game"})

# --- GAME LIFECYCLE ---

@app.route('/games/<game_id>/start', methods=['POST'])
def start_game(game_id):
    game = Game.query.get_or_404(game_id)
    data = request.json or {}
    
    game.status = "started"
    game.mode = data.get("gameMode", game.mode)
    
    if game.mode == "drawing":
        for player in game.players:
            player.challenges = [{"shape": random.choice(SHAPES), "points": 10}]
            
    db.session.commit()
    return jsonify({"status": "started", "mode": game.mode})

@app.route('/games/<game_id>/end', methods=['POST'])
def end_game(game_id):
    """Spec 5: Host ends the game for everyone."""
    game = Game.query.get_or_404(game_id)
    game.status = "finished"
    db.session.commit()
    return jsonify({"status": "game_ended"})

# --- TRACKS ---

@app.route('/games/<game_id>/tracks', methods=['POST', 'GET'])
def handle_tracks(game_id):
    """Spec 6: Standardized response for track retrieval."""
    game = Game.query.get_or_404(game_id)
    
    if request.method == 'POST':
        data = request.json
        p_id = data.get("playerId")
        existing_track = Track.query.filter_by(player_id=p_id).first()
        
        if existing_track:
            existing_track.coordinates = data.get("coordinates")
        else:
            new_track = Track(player_id=p_id, coordinates=data.get("coordinates"))
            db.session.add(new_track)
        
        db.session.commit()
        return jsonify({"status": "track_received"})
    
    # GET: Return all tracks in the requested shape
    all_tracks = []
    for p in game.players:
        if p.track:
            all_tracks.append({
                "playerId": p.id,
                "playerName": p.name,
                "coordinates": p.track.coordinates
            })
    return jsonify(all_tracks)

# --- SCORING ---

@app.route('/games/<game_id>/guesses', methods=['POST'])
def submit_guesses(game_id):
    game = Game.query.get_or_404(game_id)
    data = request.json
    guesser = Player.query.get(data.get("playerId"))
    
    for guess in data.get("guesses", []):
        target = Player.query.get(guess.get("targetPlayerId"))
        text = guess.get("text", "").lower()
        if target and target.challenges:
            if any(c['shape'].lower() == text for c in target.challenges):
                guesser.score += 5
                target.score += 2
                
    db.session.commit()
    return jsonify({"status": "guesses_processed"})

@app.route('/games/<game_id>/score', methods=['GET'])
def get_score(game_id):
    players = Player.query.filter_by(game_id=game_id).order_by(Player.score.desc()).all()
    return jsonify([{"playerId": p.id, "playerName": p.name, "score": p.score} for p in players])

if __name__ == '__main__':
    app.run(debug=True, port=8000, host='0.0.0.0')