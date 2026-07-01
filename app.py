import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import config
import database
import signals

app = Flask(__name__)

# Apply rate limiting as outlined in production safety parameters
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day"],
    storage_uri="memory://"
)

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    creator_id = data.get("creator_id", "").strip()

    if not text or not creator_id:
        return jsonify({"error": "Missing required text or creator_id parameters"}), 400

    # Execute individual signals
    llm_score = signals.get_llm_score(text)
    stylo_score = signals.get_stylometric_score(text)

    # Process weighted score
    confidence = (llm_score * config.LLM_WEIGHT) + (stylo_score * config.STYLO_WEIGHT)
    confidence = round(confidence, 2)

    # Map back to calibrated system categories & verbatim labels
    if confidence <= config.HUMAN_THRESHOLD:
        attribution = "likely_human"
        label = config.LABEL_HUMAN
    elif confidence >= config.AI_THRESHOLD:
        attribution = "likely_ai"
        label = config.LABEL_AI
    else:
        attribution = "uncertain"
        label = config.LABEL_UNCERTAIN

    content_id = str(uuid.uuid4())

    # Construct complete transaction packet for audit logging
    audit_entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylometric_score": stylo_score,
        "status": "classified",
        "appeal_reasoning": None
    }
    database.save_submission(audit_entry)

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label
    }), 200

@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json() or {}
    content_id = data.get("content_id", "").strip()
    creator_id = data.get("creator_id", "").strip()
    reasoning = data.get("creator_reasoning", "").strip()

    if not content_id or not creator_id or not reasoning:
        return jsonify({"error": "Missing elements from payload criteria"}), 400

    record = database.get_record(content_id)
    if not record:
        return jsonify({"error": "Content record not found"}), 404

    # Enforce identity authorization constraints
    if record.get("creator_id") != creator_id:
        return jsonify({"error": "Unauthorized submitter ID validation failure"}), 403

    # Perform operational mutations
    success = database.update_record_status(content_id, reasoning)
    if success:
        return jsonify({
            "status": "success",
            "message": "Appeal successfully received. Content status set to under_review.",
            "content_id": content_id
        }), 200

    return jsonify({"error": "Failed to handle state transaction"}), 500

@app.route("/log", methods=["GET"])
def get_logs():
    return jsonify({"entries": database.get_all_logs()}), 200

if __name__ == "__main__":
    app.run(port=5000, debug=True)