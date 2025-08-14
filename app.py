# app.py
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import requests
import os
from threading import Thread
import time

# -----------------------------------------------------------------------------
# Flask app
# -----------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

# -----------------------------------------------------------------------------
# Ngrok URL (fetched periodically from MongoDB)
# -----------------------------------------------------------------------------
ngrok_url = None

def get_ngrok_tunnel_url_from_db():
    """
    Fetch ngrok URL from MongoDB.
    Prefer environment variable for URI; falls back to literal if needed.
    """
    uri = os.getenv(
        "MONGODB_URI",
        "mongodb+srv://phawitboo:JO3hoCXWCSXECrGB@cluster0.fvc5db5.mongodb.net/?retryWrites=true&w=majority"
    )
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client["my_database"]
        collection = db["ngrok_tunnels"]
        result = collection.find_one({})
        if result and "ngrok_url" in result:
            print("Successfully retrieved ngrok URL from MongoDB.")
            return result["ngrok_url"]
        print("Error: ngrok_url not found in the database.")
        return None
    except Exception as e:
        print(f"An error occurred while connecting to MongoDB: {e}")
        return None

def fetch_ngrok_url_periodically():
    """
    Periodically refresh ngrok URL so the UI always displays the latest.
    """
    global ngrok_url
    while True:
        url = get_ngrok_tunnel_url_from_db()
        if url:
            ngrok_url = url
            print(f"Updated ngrok URL: {ngrok_url}")
        else:
            print("Could not update ngrok URL. Will retry in 60 seconds.")
        time.sleep(60)

url_fetch_thread = Thread(target=fetch_ngrok_url_periodically, daemon=True)
url_fetch_thread.start()

# -----------------------------------------------------------------------------
# HTML (UI)
# -----------------------------------------------------------------------------
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Speech-to-Text</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji', sans-serif; }
    .animate-spin { animation: spin 1s linear infinite; }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg);} }
  </style>
</head>
<body class="bg-gray-100 min-h-full p-4 flex items-center justify-center text-gray-800">
  <div class="bg-white p-8 rounded-3xl shadow-2xl w-full max-w-2xl border border-gray-200">
    <h1 class="text-4xl font-extrabold text-center text-indigo-600 mb-6">Speech to Text</h1>
    <p class="text-center text-gray-600 mb-8">Transcribe audio using different models.</p>

    <!-- API URL Display -->
    <div class="mb-6 bg-gray-50 p-3 rounded-xl border border-gray-200">
      <p class="text-sm font-semibold text-gray-700">Transcription Service URL:</p>
      <p id="apiUrl" class="text-sm text-indigo-500 font-mono break-all"></p>
    </div>

    <form id="transcription-form" class="space-y-6">
      <!-- Model Selection -->
      <div class="space-y-2">
        <label for="model" class="block text-lg font-medium text-gray-700">
            Select Transcription Model:
        </label>
        <select id="model" name="model"
            class="mt-1 block w-full pl-3 pr-10 py-3 text-base border-2 border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-600 rounded-xl shadow-sm cursor-pointer transition-all duration-200">
            <option value="transcribe">Single-step Transcribe</option>
            <option value="transcribe-2step">Two-step Transcribe</option>
        </select>
        </div>


      <!-- Audio Input Options -->
      <div class="space-y-4">
        <h3 class="text-lg font-medium text-gray-700">Audio Input:</h3>

        <!-- File Upload -->
        <div class="flex flex-col p-6 border-2 border-dashed border-gray-300 rounded-xl hover:border-indigo-400 transition-all duration-200">
          <label for="file-upload" class="relative cursor-pointer self-center">
            <span class="flex items-center text-indigo-600 hover:text-indigo-800 transition-colors duration-200">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
                   viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                   class="mr-2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" x2="12" y1="3" y2="15"></line>
              </svg>
              <span class="font-semibold text-lg">Upload Audio File</span>
            </span>
            <input id="file-upload" name="file-upload" type="file" class="sr-only" accept="audio/*" onchange="handleFileChange(event)" />
          </label>

          <!-- File name pill + Play sound button -->
          <div id="fileInfo" class="mt-4 hidden items-center justify-between">
            <span id="fileNamePill" class="inline-flex items-center px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-sm font-medium">
              <svg xmlns="http://www.w3.org/2000/svg" class="mr-1" width="16" height="16"
                   viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"></path>
                <path d="M14 2v4a2 2 0 0 0 2 2h4"></path>
              </svg>
              <span id="fileName">Selected:</span>
            </span>
            <button type="button" id="playUploadedBtn"
                    onclick="playUploaded()"
                    class="ml-3 inline-flex items-center px-3 py-1.5 rounded-lg bg-gray-200 hover:bg-gray-300 text-gray-700 text-sm font-medium transition">
              <svg xmlns="http://www.w3.org/2000/svg" class="mr-1" width="16" height="16"
                   viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              Play sound
            </button>
          </div>
        </div>

        <div class="flex justify-center items-center text-sm font-medium text-gray-500">— OR —</div>

        <!-- Microphone Recording -->
        <div class="flex flex-col items-center p-6 border-2 border-dashed border-gray-300 rounded-xl">
          <p class="text-lg font-semibold text-gray-700 mb-3">Record from Microphone</p>
          <div class="flex space-x-4">
            <button type="button" id="recordButton" onclick="isRecording ? stopRecording() : startRecording()"
                    class="flex items-center justify-center w-12 h-12 rounded-full bg-indigo-500 hover:bg-indigo-600 text-white shadow-lg transition-all duration-300">
              <svg id="micIcon" xmlns="http://www.w3.org/2000/svg" width="24" height="24"
                   viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" x2="12" y1="19" y2="22"/>
              </svg>
            </button>
            <button type="button" id="playButton" onclick="playRecording()"
                    class="flex items-center justify-center w-12 h-12 rounded-full bg-gray-200 hover:bg-gray-300 text-gray-700 shadow-lg transition-all duration-300"
                    style="display: none;">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
                   viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
            </button>
          </div>
          <p id="recordingStatus" class="mt-2 text-sm text-red-500 animate-pulse" style="display: none;">Recording...</p>
          <div id="audioPlayerContainer" class="mt-4 w-full" style="display: none;">
            <audio id="audioPlayer" controls class="w-full"></audio>
          </div>
        </div>
      </div>

      <!-- Submit Button -->
      <button type="submit" id="submitButton"
              class="w-full flex items-center justify-center py-3 px-4 rounded-xl font-bold text-lg text-white transition-all duration-300 shadow-lg bg-gray-400 cursor-not-allowed"
              disabled>
        <svg id="submitIcon" xmlns="http://www.w3.org/2000/svg" width="24" height="24"
             viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
             class="mr-2">
          <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>
          <path d="M14 2v4a2 2 0 0 0 2 2h4"/>
          <line x1="16" x2="8" y1="13" y2="13"/>
          <line x1="16" x2="8" y1="17" y2="17"/>
          <line x1="10" x2="8" y1="9" y2="9"/>
        </svg>
        <span id="submitText">Transcribe Audio</span>
      </button>
    </form>

    <!-- Transcription Output -->
    <div id="transcriptionOutput" class="mt-8" style="display: none;">
      <h2 class="text-2xl font-bold text-indigo-600 mb-4 flex items-center">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
             viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
             class="mr-2">
          <circle cx="12" cy="12" r="10"/>
          <polygon points="10 8 16 12 10 16 10 8"/>
        </svg>
        Transcription Result
      </h2>
      <div class="bg-gray-50 p-6 rounded-xl border border-gray-200">
        <p id="transcriptionText" class="text-gray-700 whitespace-pre-wrap"></p>
      </div>
    </div>
  </div>

  <!-- Waiting Overlay -->
  <div id="waitingOverlay" class="fixed inset-0 bg-black/50 backdrop-blur-sm hidden items-center justify-center z-50">
    <div class="bg-white rounded-2xl p-6 shadow-xl flex items-center space-x-3">
      <svg xmlns="http://www.w3.org/2000/svg" class="animate-spin" width="28" height="28"
           viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
      </svg>
      <span class="font-semibold text-gray-700">Processing… please wait</span>
    </div>
  </div>

<script>
  // -------------------- State --------------------
  let file = null;
  let isRecording = false;
  let recordedAudioBlob = null;
  let mediaRecorder = null;
  let audioChunks = [];
  const API_BASE_URL = window.location.origin;

  // -------------------- DOM --------------------
  const fileInput = document.getElementById('file-upload');
  const fileInfo = document.getElementById('fileInfo');
  const fileNameText = document.getElementById('fileName');
  const recordButton = document.getElementById('recordButton');
  const recordingStatus = document.getElementById('recordingStatus');
  const audioPlayerContainer = document.getElementById('audioPlayerContainer');
  const audioPlayer = document.getElementById('audioPlayer');
  const playButton = document.getElementById('playButton');
  const form = document.getElementById('transcription-form');
  const submitButton = document.getElementById('submitButton');
  const submitIcon = document.getElementById('submitIcon');
  const submitText = document.getElementById('submitText');
  const transcriptionOutput = document.getElementById('transcriptionOutput');
  const transcriptionText = document.getElementById('transcriptionText');
  const ngrokUrlElement = document.getElementById('apiUrl');
  const modelSelect = document.getElementById('model');
  const waitingOverlay = document.getElementById('waitingOverlay');
  const playUploadedBtn = document.getElementById('playUploadedBtn');

  // -------------------- Init --------------------
  updateSubmitButtonState();
  fetchNgrokUrl();

  function fetchNgrokUrl() {
    fetch(`${API_BASE_URL}/get_ngrok_url`)
      .then(r => r.json())
      .then(data => {
        if (data.ngrok_url) {
          ngrokUrlElement.textContent = data.ngrok_url;
        } else {
          ngrokUrlElement.textContent = 'Could not fetch URL. Is the server running?';
          ngrokUrlElement.classList.add('text-red-500');
        }
      })
      .catch(err => {
        console.error('Error fetching ngrok URL:', err);
        ngrokUrlElement.textContent = 'Network error. Could not connect to Flask server.';
        ngrokUrlElement.classList.add('text-red-500');
      });
  }

  function updateSubmitButtonState() {
    const hasAudio = !!(file || recordedAudioBlob);
    submitButton.disabled = !hasAudio;
    if (hasAudio) {
      submitButton.classList.remove('bg-gray-400', 'cursor-not-allowed');
      submitButton.classList.add('bg-indigo-600', 'hover:bg-indigo-700', 'focus:ring-indigo-500');
    } else {
      submitButton.classList.add('bg-gray-400', 'cursor-not-allowed');
      submitButton.classList.remove('bg-indigo-600', 'hover:bg-indigo-700', 'focus:ring-indigo-500');
    }
  }

  // ------------- File upload -------------
  function handleFileChange(event) {
    file = event.target.files[0];
    recordedAudioBlob = null;
    audioChunks = [];

    if (file) {
      fileNameText.textContent = `Selected: ${file.name}`;
      fileInfo.classList.remove('hidden');

      const audioUrl = URL.createObjectURL(file);
      audioPlayer.src = audioUrl;
      audioPlayerContainer.style.display = 'block';
      playButton.style.display = 'none';
      playUploadedBtn.disabled = false;
    } else {
      fileInfo.classList.add('hidden');
      fileNameText.textContent = 'Selected:';
      audioPlayerContainer.style.display = 'none';
      playUploadedBtn.disabled = true;
    }
    updateSubmitButtonState();
  }

  function playUploaded() {
    if (file && audioPlayer.src) {
      audioPlayer.play();
    }
  }

  // ------------- Microphone recording -------------
  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      recordedAudioBlob = null;
      file = null;

      mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        recordedAudioBlob = audioBlob;
        const audioUrl = URL.createObjectURL(recordedAudioBlob);
        audioPlayer.src = audioUrl;
        audioPlayerContainer.style.display = 'block';
        playButton.style.display = 'inline-flex';
        updateSubmitButtonState();
      };

      mediaRecorder.start();
      isRecording = true;
      recordButton.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
             viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <rect x="9" y="9" width="6" height="6"></rect>
        </svg>`;
      recordButton.classList.remove('bg-indigo-500', 'hover:bg-indigo-600');
      recordButton.classList.add('bg-red-500', 'hover:bg-red-600');
      recordingStatus.style.display = 'block';
      fileInfo.classList.add('hidden');
      fileNameText.textContent = 'Selected:';
    } catch (error) {
      console.error('Error accessing microphone:', error);
      alert('Could not access microphone. Please check your permissions.');
    }
  }

  function stopRecording() {
    if (mediaRecorder) {
      mediaRecorder.stop();
      isRecording = false;
      recordButton.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
             viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" x2="12" y1="19" y2="22"/>
        </svg>`;
      recordButton.classList.remove('bg-red-500', 'hover:bg-red-600');
      recordButton.classList.add('bg-indigo-500', 'hover:bg-indigo-600');
      recordingStatus.style.display = 'none';
    }
  }

  function playRecording() {
    if (recordedAudioBlob) audioPlayer.play();
  }

  function toggleWaiting(isOn) {
    if (isOn) {
      waitingOverlay.classList.remove('hidden');
      waitingOverlay.classList.add('flex');
      submitButton.disabled = true;
      recordButton.disabled = true;
      fileInput.disabled = true;
      modelSelect.disabled = true;
    } else {
      waitingOverlay.classList.add('hidden');
      waitingOverlay.classList.remove('flex');
      submitButton.disabled = false;
      recordButton.disabled = false;
      fileInput.disabled = false;
      modelSelect.disabled = false;
    }
  }

  // ------------- Submit -------------
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    toggleWaiting(true);

    let audioSource = file || recordedAudioBlob;
    if (!audioSource) {
      alert('Please select a file or record audio.');
      toggleWaiting(false);
      return;
    }

    submitButton.disabled = true;
    submitText.textContent = 'Transcribing...';
    submitIcon.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
           viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
           class="animate-spin">
        <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
      </svg>`;

    try {
      const reader = new FileReader();
      reader.readAsDataURL(audioSource);
      reader.onloadend = async () => {
        const base64Audio = reader.result.split(',')[1];
        const model = modelSelect.value;

        const resp = await fetch(`${API_BASE_URL}/transcribe-audio`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audio_base64: base64Audio, model })
        });

        const data = await resp.json();
        if (data.transcription) {
          transcriptionText.textContent = data.transcription;
        } else {
          transcriptionText.textContent = 'Error: ' + (data.error || 'Unknown error');
        }
        transcriptionOutput.style.display = 'block';

        updateSubmitButtonState();
        submitText.textContent = 'Transcribe Audio';
        submitIcon.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
               viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
               class="mr-2">
            <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>
            <path d="M14 2v4a2 2 0 0 0 2 2h4"/>
            <line x1="16" x2="8" y1="13" y2="13"/>
            <line x1="16" x2="8" y1="17" y2="17"/>
            <line x1="10" x2="8" y1="9" y2="9"/>
          </svg>`;
        toggleWaiting(false);
      };
    } catch (error) {
      console.error('Error during transcription:', error);
      transcriptionText.textContent = 'An unexpected error occurred.';
      transcriptionOutput.style.display = 'block';
      updateSubmitButtonState();
      submitText.textContent = 'Transcribe Audio';
      submitIcon.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"
             viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
             class="mr-2">
          <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>
          <path d="M14 2v4a2 2 0 0 0 2 2h4"/>
          <line x1="16" x2="8" y1="13" y2="13"/>
          <line x1="16" x2="8" y1="17" y2="17"/>
          <line x1="10" x2="8" y1="9" y2="9"/>
        </svg>`;
      toggleWaiting(false);
    }
  });

  // expose functions for inline handlers
  window.handleFileChange = handleFileChange;
  window.startRecording = startRecording;
  window.stopRecording = stopRecording;
  window.playRecording = playRecording;
  window.playUploaded = playUploaded;
</script>
</body>
</html>
"""

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/transcribe-audio", methods=["POST"])
def transcribe_audio():
    """
    Receives base64 audio + model from the UI,
    forwards to external transcription service via ngrok,
    normalizes response, bubbles upstream errors.
    """
    if not ngrok_url:
        return jsonify({"error": "Ngrok URL is not yet available."}), 503

    try:
        incoming = request.get_json(silent=True) or {}
        audio_b64 = incoming.get("audio_base64")
        model = incoming.get("model")
        if not audio_b64 or not model:
            return jsonify({"error": "Missing audio data or model"}), 400

        # Ensure scheme on tunnel URL
        base = ngrok_url.strip()
        if not base.startswith(("http://", "https://")):
            base = "https://" + base

        # Base JSON payload (true JSON types)
        payload_json = {
            "audio_base64": audio_b64,
            "use_chunked": False,
            "num_beams": 1,
            "max_new_tokens": 256,
        }

        if model == "transcribe":
            target = f"{base}/transcribe"
            payload_json["tgt_lang"] = "tha"
        elif model == "transcribe-2step":
            target = f"{base}/transcribe-2step"
            payload_json.update({
                "s2tt_tgt_lang": "eng",
                "mt_src_lang_code": "eng_Latn",
                "use_chunked": True,
                "chunk_sec": 30.0,
                "overlap_sec": 1.0,
                "use_spectral_nr": True,
            })
        else:
            return jsonify({"error": "Invalid model selected"}), 400

        def normalize(body):
            if isinstance(body, dict):
                if isinstance(body.get("result"), dict) and "text" in body["result"]:
                    return body["result"]["text"]
                if "text" in body:
                    return body["text"]
                if "translation" in body:
                    return body["translation"]
            return None

        # Attempt 1: JSON
        try:
            resp = requests.post(target, json=payload_json, timeout=120)
            try:
                body = resp.json()
            except ValueError:
                body = None

            if resp.ok:
                text = normalize(body) if body is not None else None
                if text is not None:
                    return jsonify({"transcription": text})
                return jsonify({
                    "error": "Unexpected response shape from transcription service",
                    "upstream_status": resp.status_code,
                    "upstream_body": body if body is not None else resp.text
                }), 502
            else:
                # 400/415 often indicates wrong content type for this backend -> try form
                if resp.status_code in (400, 415):
                    raise RuntimeError("fallback-to-form")
                return jsonify({
                    "error": "Transcription service error",
                    "upstream_status": resp.status_code,
                    "upstream_body": body if body is not None else resp.text
                }), 502

        except RuntimeError as r:
            if str(r) != "fallback-to-form":
                raise

            # Attempt 2: form-encoded (booleans/numbers -> strings)
            payload_form = {
                k: (str(v).lower() if isinstance(v, bool) else str(v))
                for k, v in payload_json.items()
            }
            resp2 = requests.post(target, data=payload_form, timeout=120)
            try:
                body2 = resp2.json()
            except ValueError:
                body2 = None

            if resp2.ok:
                text = normalize(body2) if body2 is not None else None
                if text is not None:
                    return jsonify({"transcription": text})
                return jsonify({
                    "error": "Unexpected response shape from transcription service (form)",
                    "upstream_status": resp2.status_code,
                    "upstream_body": body2 if body2 is not None else resp2.text
                }), 502
            else:
                return jsonify({
                    "error": "Transcription service error (form)",
                    "upstream_status": resp2.status_code,
                    "upstream_body": body2 if body2 is not None else resp2.text
                }), 502

    except requests.exceptions.Timeout:
        return jsonify({"error": "Transcription service timed out"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to connect to the transcription service: {e}"}), 502
    except Exception as e:
        print(f"Unhandled server error: {e}")
        return jsonify({"error": f"Unexpected server error: {str(e)}"}), 500

@app.route("/get_ngrok_url", methods=["GET"])
def get_ngrok_url_endpoint():
    if ngrok_url:
        return jsonify({"ngrok_url": ngrok_url})
    return jsonify({"ngrok_url": "URL not available"}), 503

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(port=5000, debug=True)
