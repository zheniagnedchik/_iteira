import os
from datetime import datetime, timedelta
from flask import Flask, flash, request, redirect, url_for, jsonify, render_template, session, send_from_directory, Response
import requests
import threading
import json
import tiktoken
import re
from dotenv import load_dotenv
import pickle
import numpy as np
import time
import pandas as pd
import markdown
import logging
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

app = Flask(__name__)
limit_input_tokens=6000
dataset_folder = 'data/dataset_folder'
prompt_folder = 'data/prompt_folder'
num_chunks_of_text = 4 # number of chunks of text to search via embeddings similarity
deltahours = 0 # timedelta for alibaba servers
typing_action_seconds = 120

load_dotenv()

OPEN_AI_MODEL = os.getenv('OPEN_AI_MODEL')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or 'you_will_never_guess1111!!@@#'
LKASSA_PROXY = os.getenv('LKASSA_PROXY')

talkme_token_chat = os.getenv('talkme_token_chat')
headers = {"X-Token": talkme_token_chat, "Content-Type": "application/json"}
url_typing = 'https://lcab.talk-me.ru/json/v1.0/chat/message/sendTypingToClient'


url_bot_message = 'https://lcab.talk-me.ru/json/v1.0/customBot/send'
bot_response_json = {
  "content": {
    "text": ''
  }
}

url_bot_simulate_typing = 'https://lcab.talk-me.ru/json/v1.0/customBot/simulateTyping'
bot_simulate_typing_json = {
  "ttl": typing_action_seconds
}

url_bot_finish_code = 'https://lcab.talk-me.ru/json/v1.0/customBot/finish'
bot_finish_code_json = {
  "code": "0"
}

llm = ChatOpenAI(model_name=OPEN_AI_MODEL, 
                #openai_proxy=LKASSA_PROXY
                )

def read_prompt(folder):
    # read file
    files = os.listdir(folder)
    files = [{'filename': file, 'timestamp': (datetime.fromtimestamp(os.path.getmtime(os.path.join(folder, file)))+timedelta(hours=deltahours)).strftime('%Y-%m-%d %H:%M:%S')} for file in files if file[-4:]=='.txt']
    files.sort(key=lambda x: x['timestamp'], reverse=True)
    filename = files[0]['filename']
    file_path = f'{folder}/{filename}'
    global prompt
    prompt = ''
    with open(file_path, 'r', encoding="utf-8") as f:
        prompt = f.read()
    return prompt
prompt = read_prompt(prompt_folder)


def read_dataset():
    # list all files in dataset folder
    files = os.listdir(dataset_folder)
    files = [{'filename': file, 'timestamp': (datetime.fromtimestamp(os.path.getmtime(os.path.join(dataset_folder, file)))+timedelta(hours=deltahours)).strftime('%Y-%m-%d %H:%M:%S')} for file in files if (file[-5:]=='.xlsx' or file[-4:]=='.xls')]
    files.sort(key=lambda x: x['timestamp'], reverse=True)
    filename = files[0]['filename']
    file_path = f'{dataset_folder}/{filename}'
    # read file
    print('file that is being processed:', filename)
    df = pd.read_excel(file_path)
    global document_chunks
    document_chunks = []
    for index, row in df.iterrows():
        text = ''
        if row.notnull().iloc[1] and row.notnull().iloc[5]:
            text = text + row.iloc[1]
            text = text + '\n' + row.iloc[5]
            if row.notnull().iloc[3]:
                text = text + '\n' + row.iloc[3]
            if row.notnull().iloc[6]:
                text = text + '\n' + row.iloc[6]
            if row.notnull().iloc[2]:
                text = text + '\nПодробнее: ' + row.iloc[2]
            document_chunks.append(text)

# This utilizes OpenAIEmbeddings with an option to be used via proxy (commented openai_proxy argument)
embeddings_openai = OpenAIEmbeddings(model="text-embedding-3-large",
                                    dimensions=1024,
                                    #openai_proxy=LKASSA_PROXY
                                    )

def get_context_embeddings_co():
    global context_emb
    context_emb = embeddings_openai.embed_documents(document_chunks)
    context_emb = np.asarray(context_emb)

def read_dataset_and_create_embeddings():
    now = datetime.now()
    print("Processing dataset file...")
    read_dataset()
    print('doc_chunks len: ', len(document_chunks))
    get_context_embeddings_co()
    after = datetime.now()
    delta_time = after - now
    delta_time = round(delta_time.total_seconds())
    print('Processing file complete. Time: ' + str(delta_time) + ' seconds.')

read_dataset_and_create_embeddings()


# Here logic for upload/download of knowledge base files is described
@app.route('/upload_knowledge_base', methods=['POST'])
def upload_knowledge_base():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file.filename.split('.')[-1] != 'xls' and file.filename.split('.')[-1] != 'xlsx':
        return jsonify({'error': 'Неверный формат файла. Загрузите эксель: xls или xlsx'}), 400
    if file:
        filename = file.filename
        path_and_filename = os.path.join(dataset_folder, filename)
        if os.path.exists(path_and_filename):
            duplicate_file_timestamp = (datetime.fromtimestamp(os.path.getmtime(path_and_filename))+timedelta(hours=deltahours)).strftime('%Y-%m-%d_%H-%M-%S')
            if filename[-5:] == '.xlsx':
                new_filename_for_duplicate = filename[:-5] + '_' + duplicate_file_timestamp + '.xlsx'
                os.rename(path_and_filename, os.path.join(dataset_folder, new_filename_for_duplicate))
            elif filename[-4:] == '.xls':
                new_filename_for_duplicate = filename[:-4] + '_' + duplicate_file_timestamp + '.xls'
                os.rename(path_and_filename, os.path.join(dataset_folder, new_filename_for_duplicate))
        file.save(os.path.join(dataset_folder, filename))
        print('file that is supposed to be processed:', filename)
        # execute parsing of the uploaded file asynchronuously in background 
        thread = threading.Thread(target=read_dataset_and_create_embeddings)
        thread.start()
        # return success unswer to the webpage
        return jsonify({'success': 'File successfully uploaded', 'filename': filename}), 200

@app.route('/list_knowledge_base', methods=['GET'])
def list_knowledge_base():
    print('serving knowledge base filelist...')
    files = os.listdir(dataset_folder)
    files = [{'filename': file, 'timestamp': (datetime.fromtimestamp(os.path.getmtime(os.path.join(dataset_folder, file)))+timedelta(hours=deltahours)).strftime('%Y-%m-%d %H:%M:%S')} for file in files]
    files.sort(key=lambda x: x['timestamp'], reverse=True)
    files = files[:10]
    return jsonify({'files': files})

@app.route('/download_knowledge_base_file/<filename>', methods=['GET'])
def download_knowledge_base_file(filename):
    print('downloading knowledge base file...')
    return send_from_directory(dataset_folder, filename, as_attachment=True)


# Here logic for upload/download of prompt files is described
@app.route('/upload_prompt', methods=['POST'])
def upload_prompt():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file.filename.split('.')[-1] != 'txt':
        return jsonify({'error': 'Неверный формат файла. Загрузите текстовый файл (например, сохраненный из блокнота): txt'}), 400
    if file:
        filename = file.filename
        path_and_filename = os.path.join(prompt_folder, filename)
        if os.path.exists(path_and_filename):
            duplicate_file_timestamp = (datetime.fromtimestamp(os.path.getmtime(path_and_filename))+timedelta(hours=deltahours)).strftime('%Y-%m-%d_%H-%M-%S')
            if filename[-4:] == '.txt':
                new_filename_for_duplicate = filename[:-4] + '_' + duplicate_file_timestamp + '.txt'
                os.rename(path_and_filename, os.path.join(prompt_folder, new_filename_for_duplicate))
        file.save(os.path.join(prompt_folder, filename))
        print('file that is supposed to be processed:', filename)
        # execute parsing of the uploaded file asynchronuously in background 
        thread = threading.Thread(target=read_dataset_and_create_embeddings)
        thread.start()
        # return success unswer to the webpage
        return jsonify({'success': 'File successfully uploaded', 'filename': filename}), 200

@app.route('/list_prompt_files', methods=['GET'])
def list_prompt_files():
    print('serving prompt filelist...')
    files = os.listdir(prompt_folder)
    files = [{'filename': file, 'timestamp': (datetime.fromtimestamp(os.path.getmtime(os.path.join(prompt_folder, file)))+timedelta(hours=deltahours)).strftime('%Y-%m-%d %H:%M:%S')} for file in files]
    files.sort(key=lambda x: x['timestamp'], reverse=True)
    files = files[:10]
    return jsonify({'files': files})

@app.route('/download_prompt_file/<filename>', methods=['GET'])
def download_prompt_file(filename):
    print('downloading prompt file...')
    return send_from_directory(prompt_folder, filename, as_attachment=True)



def generate_full_llm_query(query, document_chunks, prompt, limit_input_tokens=4096):
    # Cohere embeddings
    # cohere embeddings
    # query_emb = co.embed(texts=[query], input_type="search_query", model="embed-multilingual-v3.0").embeddings
    # query_emb = np.asarray(query_emb)
    # openai embeddings
    query_emb = embeddings_openai.embed_query(query)
    query_emb = np.asarray(query_emb)

    #Compute the dot product between query embedding and document embedding
    scores = np.dot(query_emb, context_emb.T).squeeze()

    #Find the highest scores
    # argsort finds and arranges indexes of largest scores
    max_idx = np.argsort(-scores)

    context_chunks_initial = []
    context_scores = []
    for idx in max_idx[:num_chunks_of_text]:
      context_scores.append(scores[idx])
      context_chunks_initial.append(document_chunks[idx])
      # print('chunk score: ', scores[idx], 'chunk id: ', idx)
      # print('chunk found: \n', document_chunks[idx])
    context_chunks = context_chunks_initial

    llm_full_query = ''  

    # Truncating chunks to the size of limit_input_tokens
    num_of_chunks = len(context_chunks)
    for iter in range(num_of_chunks):
        context_chunks_as_str = '\n###\n'.join([str(elem) for elem in context_chunks])
        llm_full_query = prompt.format(context=context_chunks_as_str, question=query)
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens_template = len(encoding.encode(prompt))
        num_tokens = len(encoding.encode(llm_full_query))

        if num_tokens <= limit_input_tokens:
          llm_full_query, num_tokens
        elif len(context_chunks) == 1 and num_tokens > limit_input_tokens:
          chunk_appendix = '\n\nПодробности по ссылке:'
          extracted_link = re.search(r'https://.+', context_chunks[0][-100:]).group(0)
          chunk_appendix = chunk_appendix + ' ' + extracted_link
          num_of_chars_to_cut = num_tokens - limit_input_tokens + num_tokens_template + 200
          context_chunks[0] = context_chunks[0][:-num_of_chars_to_cut]
          context_chunks[0] = context_chunks[0] + chunk_appendix
          context_chunks_as_str = '\n###\n'.join([str(elem) for elem in context_chunks])
          llm_full_query = prompt.format(context=context_chunks_as_str, question=query)
          num_tokens = len(encoding.encode(llm_full_query))
          llm_full_query, num_tokens
        elif num_tokens > limit_input_tokens:
          # print('context_chunks before truncating:', len(context_chunks))
          context_chunks = context_chunks[:-1]
          # print('context_chunks after truncating:', len(context_chunks))
          print(iter)
    #print(llm_full_query)
    return llm_full_query, context_chunks, context_scores, num_tokens


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/lkassa')
def lkassa():
    return render_template('lkassa.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.get_json()
    if isinstance(data, str):
        data = json.loads(data)
    
    query = data['message']

    # Process user message here if needed
    now = datetime.now()
    llm_full_query, context_chunks, context_scores, num_tokens = generate_full_llm_query(query, document_chunks, prompt, limit_input_tokens=limit_input_tokens)
    # print('current full query:', llm_full_query)
    llm_answer = llm.invoke(llm_full_query)
    llm_answer = llm_answer.content.strip()

    after = datetime.now()
    delta_time = after - now
    delta_time = round(delta_time.total_seconds())
    encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens_llm_answer = len(encoding.encode(llm_answer))
    llm_answer = llm_answer + '\n\n' + '> response generation time: ' + str(delta_time) + ' seconds.'
    llm_asnwer_tokens_usage = num_tokens + num_tokens_llm_answer
    llm_answer = llm_answer + '\n\n' + 'tokens used: ' + str(llm_asnwer_tokens_usage)
    llm_answer = llm_answer + '\n' + 'chunks used: ' + str(len(context_chunks)) + '\nbest chunk score: ' + "{:.2f}".format(context_scores[0])
    chunk_headers_used = 'following chunks used:'
    for ind, chunk in enumerate(context_chunks):
        chunk_header = chunk.split('\n')[0]
        chunk_headers_used = chunk_headers_used + '\n' + str(ind+1) + '. ' + chunk_header
    llm_answer = llm_answer + '\n' + chunk_headers_used
    print(llm_answer)
    response = {'message': llm_answer}
    return jsonify(response)


@app.route('/get_message_talkme', methods=['POST'])
def get_message_talkme():
    data = request.get_json()
    if isinstance(data, str):
        data = json.loads(data)

    # define success response for usage further
    response = Response('Success')

    client_message = data['message']['text']
    print('client_message is', client_message)
    print('data message is', data['message'])
    print('data is', data)
    token_received = data['token']
    print('token received:', token_received)
    client_id = data['client']['clientId']
    print('headers:', headers)
    headers['X-Token'] = token_received


    # This block checks if client message == лид and sends proper signal
    if client_message.strip().lower() == "лид":
        bot_finish_code_json['code'] = 'lead_form'
        talkme_response = requests.post(url_bot_finish_code, json = bot_finish_code_json, headers = headers)
        print('lead_form code sent, talkme response:', talkme_response.text)
        return response


    # simulate typing
    talkme_response = requests.post(url_bot_simulate_typing, json = bot_simulate_typing_json, headers = headers)
    print('simulate typing sent, talkme response:', talkme_response.text)
    
    query = client_message

    now = datetime.now()
    llm_full_query, context_chunks, context_scores, num_tokens = generate_full_llm_query(query, document_chunks, prompt, limit_input_tokens=limit_input_tokens)
    # print('current full query:', llm_full_query)
    llm_answer = llm.invoke(llm_full_query)
    llm_answer = llm_answer.content.strip()
    

    extracted_llm_response = ''
    logging.error("This is an error message")
    #check message classification
    pattern = r'[\s\S]*?(?=\n.*?query_classification_variables|$)'
    match_result = re.search(pattern, llm_answer)
    if match_result:
        extracted_llm_response = llm_answer[:match_result.end()]
        print('extracted_llm_response', extracted_llm_response)

        pattern_line_with_vars = '.*query_classification_variables.*\n?'
        match_result = re.search(pattern_line_with_vars, llm_answer)

        if match_result:
            extracted_variables_line = llm_answer[match_result.start():match_result.end()]
            print('extracted_variables_line', extracted_variables_line)

            # is_it_simple_hello_from_client = 0
            # pattern_is_it_hello_value = r'is_it_simple_hello_from_client=(\d)'
            # is_it_hello_match = re.search(pattern_is_it_hello_value, extracted_variables_line)
            # if is_it_hello_match:
            #     is_it_simple_hello_from_client = int(is_it_hello_match.group(1))
            # if is_it_simple_hello_from_client:
            #     bot_response_json['content']['text'] = simple_hello_back_message
            #     talkme_response = requests.post(url_bot_message, json = bot_response_json, headers = headers)
            #     print('simple_hello_back_message sent, talkme response:', talkme_response.text)
            #     return response

            does_client_asks_human_support = 0
            pattern_wants_human = r'does_client_asks_human_support=(\d)'
            wants_human_match = re.search(pattern_wants_human, extracted_variables_line)
            if wants_human_match:
                does_client_asks_human_support = int(wants_human_match.group(1))
            if does_client_asks_human_support:
                # send finish code for redirecting to human support
                bot_finish_code_json['code'] = 'get_human'
                talkme_response = requests.post(url_bot_finish_code, json = bot_finish_code_json, headers = headers)
                print('get_human code sent, talkme response:', talkme_response.text)
                return response

            is_client_question_irrelevant_to_context = 0
            pattern_is_relevant_question = r'is_client_question_irrelevant_to_context=(\d)'
            is_it_relvant_match = re.search(pattern_is_relevant_question, extracted_variables_line)
            if is_it_relvant_match:
                is_client_question_irrelevant_to_context = int(is_it_relvant_match.group(1))
            if is_client_question_irrelevant_to_context == 1:
                llm_answer = extracted_llm_response.strip()
                extracted_llm_response = '%html%'+llm_answer
                bot_response_json['content']['text'] = extracted_llm_response
                talkme_response = requests.post(url_bot_message, json = bot_response_json, headers = headers)
                print('answer to irrelevant question sent, talkme response:', talkme_response.text)
                bot_finish_code_json['code'] = 'irrelevant_message'
                talkme_response = requests.post(url_bot_finish_code, json = bot_finish_code_json, headers = headers)
                print('irrelevant_message code sent, talkme response:', talkme_response.text)
                return response

    llm_answer = extracted_llm_response.strip()

    
    llm_answer = markdown.markdown(llm_answer)
    # this line fixes the issue, when answer has bad formatting - when items in list were displayed in new line - looked bad for client
    llm_answer = llm_answer.replace('<li><p>','<li>').replace('</p></li>', '</li>').replace('<li>\n<p>','<li>').replace('</p>\n</li>', '</li>').replace('<ol>', '<ul>').replace('</ol>', '</ul>')
    

    # This is regex to replace links to be opened in new tab when clicked
    ## regex from https://stackoverflow.com/questions/33368697/replace-a-url-into-anchor-tag-using-a-python-regex
    ## about new tab opening: https://www.freecodecamp.org/news/how-to-use-html-to-open-link-in-new-tab/
    # modifying and fixing link regexp via chatgpt: https://chatgpt.com/share/67bc6c86-da24-8002-a637-4e9d6907b9df
    def replace_func(matchObj):
        bracketed_text, bracketed_url, href_tag, href_text, span_url, standalone_url = matchObj.groups()
        if bracketed_text and bracketed_url:
            return f'{bracketed_text}(<a href="{bracketed_url}" target="_blank" rel="noopener noreferrer">{bracketed_url}</a>)'
        elif href_tag and href_text:
            return f'<a href="{href_tag}" target="_blank" rel="noopener noreferrer">{href_text}</a>'
        elif span_url:
            return f'<span><a href="{span_url}" target="_blank" rel="noopener noreferrer">{span_url}</a></span>'
        elif standalone_url:
            return f'<a href="{standalone_url}" target="_blank" rel="noopener noreferrer">{standalone_url}</a>'
        return matchObj.group(0)  # Return original match if no condition is met

    pattern = re.compile(
        r'(\[[^\]]+\])\((https?://\S+)\)|'  # Match markdown-style links (groups 1 and 2)
        r'<a href="(https?://[^"]+)">([^<]+)</a>|'  # Match existing <a> tags (groups 3 and 4)
        r'<span>(https?://\S+)</span>|'  # Match URLs inside <span> tags (group 5)
        r'(?<![\[\(>])\b(https?://\S+)\b(?![\]\)])',  # Match standalone URLs, ensuring they are not within [] or <>
        flags=re.IGNORECASE)

    llm_answer = pattern.sub(replace_func, llm_answer)


    # This is the regex to replace phone numbers to clickable html buttons phone numbers.
    def repl_func(matchObj):
        phone_number = matchObj.group(1)
        print(phone_number)
        if phone_number:
            return '<form><button formaction="tel: %s">%s</button></form>' % (phone_number, phone_number)

    pattern = re.compile(
        r'([\+]?[(]?[0-9]{3}[)]?[-\s]?[0-9]{2}[-\s]?[0-9]{3}[-\s]?[0-9]{2}[-\s]?[0-9]{2})',
        flags=re.IGNORECASE)

    llm_answer = re.sub(pattern, repl_func, llm_answer)


    llm_answer = '%html%'+llm_answer
    print('full llm_answer html:\n',llm_answer)
    bot_response_json['content']['text'] = llm_answer
    print('sending_message full llm answer in html format')
    talkme_response = requests.post(url_bot_message, json = bot_response_json, headers = headers)
    print(talkme_response.text)

    return response

@app.route('/upload_knowledge_base')
def upload_knowledge_base_func():
    print('rendering template...')
    return render_template('upload_knowledge_base.html')

@app.route('/upload_prompt')
def upload_upload_prompt_func():
    print('rendering template...')
    return render_template('upload_prompt.html')


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=4000)