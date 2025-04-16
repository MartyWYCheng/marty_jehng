from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename
import os

#############
import base64
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google import genai
from google.genai import types
from google.cloud import texttospeech_v1


client2 = texttospeech_v1.TextToSpeechClient()

def sample_synthesize_speech(text=None, ssml=None):
        input = texttospeech_v1.SynthesisInput()
        if ssml:
            input.ssml = ssml
        else:
            input.text = text

        voice = texttospeech_v1.VoiceSelectionParams()
        voice.language_code = "en-UK"
        # voice.ssml_gender = "MALE"

        audio_config = texttospeech_v1.AudioConfig()
        audio_config.audio_encoding = "LINEAR16"

        request = texttospeech_v1.SynthesizeSpeechRequest(
            input=input,
            voice=voice,
            audio_config=audio_config,
        )
        response = client2.synthesize_speech(request=request)
        return response.audio_content


def generate(filename, prompt):
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    files = [client.files.upload(file=f) for f in filename]  # upload each file

    model = "gemini-2.5-pro-exp-03-25"
    contents = [
        types.Content(
            role="user",
            parts=[
                *[
                    types.Part.from_uri(
                        file_uri=f.uri,
                        mime_type=f.mime_type,
                    ) for f in files
                ],
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        response_mime_type="text/plain",
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )
    
    print(response.candidates[0].content.parts[0].text)
    return response.candidates[0].content.parts[0].text


app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav','pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if allowed_file(filename):
            files.append(filename)
            print(filename)
    files.sort(reverse=True)
    return files

@app.route('/')
def index():
    files = get_files()
    return render_template('index.html', files=files)



@app.route('/upload_pdf', methods=['POST'])
def upload_text():
    book_file = request.files['pdf_data']
    filename = 'book.pdf'
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    book_file.save(file_path)

    return redirect('/') #success
    


@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' in request.files and request.files['audio_data'].filename != '':
        file = request.files['audio_data']
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p")
        file_path_prompt = os.path.join(app.config['UPLOAD_FOLDER'], filename + '_QUESTION.wav')
        file.save(file_path_prompt)
        #prompt_file = Part.from_uri(file_path_prompt, mime_type="audio/wav")

        file_path_book = os.path.join(app.config['UPLOAD_FOLDER'], 'book.pdf')
        #book_file = Part.from_uri(file_path_book, mime_type="application/pdf")

        prompt = "Answer the user's query in the audio file based on the pdf book"

        contents = [file_path_prompt, file_path_book]
        text = generate(contents, prompt)

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename + '_RESPONSE.wav.txt')
        f = open(file_path,'w')
        #print(text)
        f.write(text)
        f.close()       

        # Save the output as a audio file in the 'tts' directory 
        wav = sample_synthesize_speech(text)

        # save audio
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename + '_RESPONSE')
        f = open(file_path + '.wav','wb')
        f.write(wav)
        f.close()

    else:
        flash('No data to upload')
        return redirect(request.url)

    #if file.filename == '':
    #    flash('No selected file')
    #    return redirect(request.url)


        
        #

    return redirect('/') #success

@app.route('/upload/<filename>')
def get_file(filename):
    return send_file(filename)



@app.route('/script.js',methods=['GET'])
def scripts_js():
    return send_file('./script.js')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/<filename>')
def tts_file(filename):
    return send_from_directory(os.getcwd(), filename)

if __name__ == '__main__':
    app.run(debug=True)
