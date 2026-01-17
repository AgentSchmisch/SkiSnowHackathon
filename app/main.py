import uuid
import random
from flask import Flask, jsonify, request, abort

app = Flask(__name__)

# In-memory database
GAMES_DB = {}

# Utilities for random generation
ADJECTIVES = ["Speedy", "Frosty", "Gnarly", "Zesty", "Powder"]
NOUNS = ["Skier", "Yeti", "Penguin", "Carver", "Avalanche"]
SHAPES = ["Star", "Heart", "Circle", "Square", "Triangle", "ZigZag"]

def generate_fun_name():
    return f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)} {random.randint(10, 99)}"

def generate_join_code():
    return ''.join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=6))


@app.route('/')
def index():
    return "Ski Snow Hackathon Game API"

# --- LOBBY MANAGEMENT ---

@app.route('/games', methods=['POST'])
def create_game():
    data = request.json or {}
    game_id = str(uuid.uuid4())
    join_code = generate_join_code()
    
    GAMES_DB[game_id] = {
        "id": game_id,
        "joinCode": join_code,
        "mode": data.get("gameMode", "drawing"),
        "status": "lobby",
        "players": {}, # {playerId: {name: str, score: int}}
        "challenges": {}, # {playerId: [shapes]}
        "tracks": {}, # {playerId: {coordinates: [], ...}}
        "guesses": []
    }
    return jsonify({"gameId": game_id, "joinCode": join_code}), 201

@app.route('/games/<game_id>', methods=['GET'])
def get_game_status(game_id):
    game = GAMES_DB.get(game_id)
    
    # Construct a response that tells the frontend everything
    return jsonify({
        "gameId": game.id,
        "status": game.status, # "lobby", "started", or "finished"
        "mode": game.mode,
        "players": [
            {
                "playerId": p.id,
                "playerName": p.name,
                "score": p.score,
                "hasSubmittedTrack": (p.track is not None)
            } for p in game.players
        ]
    })

# --- PLAYER JOIN/LEAVE ---

@app.route('/games/<game_id>/join', methods=['POST'])
def join_game(game_id):
    game = GAMES_DB.get(game_id)
    if not game: abort(404)
    
    player_id = str(uuid.uuid4())
    player_name = generate_fun_name()
    
    game["players"][player_id] = {
        "id": player_id,
        "name": player_name,
        "score": 0
    }
    return jsonify({"playerId": player_id, "playerName": player_name})

# --- GAME START & CHALLENGES ---

@app.route('/games/<game_id>/start', methods=['POST'])
def start_game(game_id):
    game = GAMES_DB.get(game_id)
    if not game: abort(404)
    
    data = request.json or {}
    game["status"] = "started"
    game["mode"] = data.get("gameMode", game["mode"])
    
    # Generate challenges if in drawing mode
    if game["mode"] == "drawing":
        for p_id in game["players"]:
            game["challenges"][p_id] = [
                {"shape": random.choice(SHAPES), "points": 10}
            ]
            
    return jsonify({"status": "started", "mode": game["mode"]})

@app.route('/games/<game_id>/challenges', methods=['GET'])
def get_challenges(game_id):
    game = GAMES_DB.get(game_id)
    if not game: abort(404)
    return jsonify(game["challenges"])

# --- TRACK SUBMISSION ---

@app.route('/games/<game_id>/tracks', methods=['POST', 'GET'])
def handle_tracks(game_id):
    game = GAMES_DB.get(game_id)
    if not game: abort(404)
    
    if request.method == 'POST':
        data = request.json
        p_id = data.get("playerId")
        game["tracks"][p_id] = {
            "playerId": p_id,
            "coordinates": data.get("coordinates"),
            "startTime": data.get("startTime"),
            "endTime": data.get("endTime")
        }
        #TODO: validate the track data -> CV for shape matching
        return jsonify({"status": "track_received"})
    
    return jsonify(list(game["tracks"].values()))

# --- GUESSES & SCORING ---

@app.route('/games/<game_id>/guesses', methods=['POST'])
def submit_guesses(game_id):
    game = GAMES_DB.get(game_id)
    if not game: abort(404)
    
    data = request.json # {playerId, guesses: [{targetPlayerId, shape}]}
    guesser_id = data.get("playerId")
    
    for guess in data.get("guesses", []):
        target_id = guess.get("targetPlayerId")
        guessed_shape = guess.get("text")
        
        # Simple Logic: Check if guess matches the assigned challenge
        actual_challenges = game["challenges"].get(target_id, [])
        if any(c["shape"].lower() == guessed_shape.lower() for c in actual_challenges):
            # Award points to guesser and target
            game["players"][guesser_id]["score"] += 5
            game["players"][target_id]["score"] += 2
            
    return jsonify({"status": "guesses_processed"})

@app.route('/games/<game_id>/score', methods=['GET'])
def get_score(game_id):
    game = GAMES_DB.get(game_id)
    if not game: abort(404)
    
    # Sort players by score
    sorted_scores = sorted(
        game["players"].values(), 
        key=lambda x: x["score"], 
        reverse=True
    )
    return jsonify(list(sorted_scores))

if __name__ == '__main__':
    app.run(debug=True, port=8000, host='0.0.0.0')