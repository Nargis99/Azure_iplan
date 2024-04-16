import streamlit as st
from streamlit_chat import message
from utilities.helper import LLMHelper
import os
import traceback
import regex as re
from random import randint
import io
import requests
import mimetypes
import chardet
from urllib import parse
from redis.exceptions import ResponseError
import uuid

# Function to clear chat data
def clear_chat_data():
    st.session_state['chat_history'] = []
    st.session_state['chat_source_documents'] = []
    st.session_state['chat_askedquestion'] = ''
    st.session_state['chat_question'] = ''
    st.session_state['chat_followup_questions'] = []

# Callback to assign the follow-up question selected by the user
def ask_followup_question(followup_question):
    st.session_state.chat_askedquestion = followup_question
    st.session_state['input_message_key'] = st.session_state['input_message_key'] + 1

# Define Predefined Prompts
predefined_prompts = [
    "Generate summary for this project?",
    "Generate task and subtasks for the given project",
]

# Function to handle predefined prompt selection
def handle_predefined_prompt(prompt):
    st.session_state.chat_askedquestion = prompt
    st.session_state['input_message_key'] += 1

def display_predefined_prompts(file_uploaded=False):
    if file_uploaded:
        col1, col2 = st.columns(2)  # Create two columns for side-by-side display
        for i, prompt in enumerate(predefined_prompts):
            if i % 2 == 0:
                button_container = col1
            else:
                button_container = col2
            if button_container.button(prompt, key=prompt):
                handle_predefined_prompt(prompt)

# def display_predefined_prompts(file_uploaded=False):
#     if file_uploaded:
#         for prompt in predefined_prompts:
#             if st.button(prompt, key=prompt):
#                 handle_predefined_prompt(prompt)


# Function to interact with the chatbot
def chatbot_interaction():

    # If a question is asked, execute the request to get the result
    if st.session_state.chat_askedquestion:
        st.session_state['chat_question'] = st.session_state.chat_askedquestion
        st.session_state.chat_askedquestion = ""
        st.session_state['chat_question'], result, context, sources = llm_helper.get_semantic_answer_lang_chain(st.session_state['chat_question'], st.session_state['chat_history'])
        result, chat_followup_questions_list = llm_helper.extract_followupquestions(result)
        st.session_state['chat_history'].insert(0, (st.session_state['chat_question'], result))  # Insert at the beginning
        st.session_state['chat_source_documents'].insert(0, sources)  # Insert at the beginning
        st.session_state['chat_followup_questions'] = chat_followup_questions_list

    # Display the chat history
    if st.session_state['chat_history']:
        history_range = range(len(st.session_state['chat_history'])-1, -1, -1)
        for i in range(len(st.session_state['chat_history'])-1, -1, -1):
            if i == history_range.start:
                answer_with_citations, sourceList, matchedSourcesList, linkList, filenameList = llm_helper.get_links_filenames(st.session_state['chat_history'][i][1], st.session_state['chat_source_documents'][i])
                st.session_state['chat_history'][i] = st.session_state['chat_history'][i][:1] + (answer_with_citations,)

                answer_with_citations = re.sub(r'\$\^\{(.*?)\}\$', r'(\1)', st.session_state['chat_history'][i][1]).strip()

                if len(st.session_state['chat_followup_questions']) > 0:
                    st.markdown('**Proposed follow-up questions:**')
                with st.container():
                    for questionId, followup_question in enumerate(st.session_state['chat_followup_questions']):
                        if followup_question:
                            str_followup_question = re.sub(r"(^|[^\\\\])'", r"\1\\'", followup_question)
                            st.button(str_followup_question, key=randint(1000,99999), on_click=ask_followup_question, args=(followup_question, ))

    # Display chat history
    if st.session_state['chat_history']:
        for i in range(len(st.session_state['chat_history'])):
            idx = len(st.session_state['chat_history']) - i - 1
            answer_with_citations = re.sub(r'\$\^\{(.*?)\}\$', r'(\1)', st.session_state['chat_history'][idx][1])
            message(st.session_state['chat_history'][idx][0], is_user=True, key=str(idx)+'user' + '_user', avatar_style="icons", seed="Ginger")
            message(answer_with_citations ,key=str(idx)+'answers', avatar_style="bottts-neutral", seed="Sophie")
            st.markdown(f'\n\nSources: {st.session_state["chat_source_documents"][idx]}')

    # # UI components for chat interaction
    # input_text = st.text_input("", placeholder="Type your question", key="input"+str(st.session_state ['input_message_key']), on_change=questionAsked)
    # clear_chat = st.button("Clear chat", key="clear_chat", on_click=clear_chat_data, type="primary")

    # UI components
    col1, col2 = st.columns([1, 6])
    with col1:
        upload_file_and_process()  # Placing file uploader in the second column
        clear_chat = st.button("Clear chat", key="clear_chat", on_click=clear_chat_data, type="primary")

    with col2:
        # display_predefined_prompts(file_uploaded=True)
        input_text = st.text_area("", placeholder="Type your question", key="input"+str(st.session_state['input_message_key']), on_change=questionAsked)
    # clear_chat = st.button("Clear chat", key="clear_chat", on_click=clear_chat_data, type="primary")

# Function to upload text and embeddings
def upload_text_and_embeddings():
    file_name = f"{uuid.uuid4()}.txt"
    source_url = llm_helper.blob_client.upload_file(st.session_state['doc_text'], file_name=file_name, content_type='text/plain; charset=utf-8')
    llm_helper.add_embeddings_lc(source_url) 
    # st.success("Embeddings added successfully.")
    # st.success("File uploaded successfully.")

# Function to handle question asked
def questionAsked():
    st.session_state.chat_askedquestion = st.session_state["input"+str(st.session_state ['input_message_key'])]
    st.session_state["input"+str(st.session_state ['input_message_key'])] = ""
    st.session_state.chat_question = st.session_state.chat_askedquestion

# Function to upload file and process it
def upload_file_and_process():
    uploaded_file = st.file_uploader("", type=['pdf', 'txt', 'docx'])
    css = '''
    <style>
        [data-testid='stFileUploader'] {
            width: max-content;
        }
        [data-testid='stFileUploader'] section {
            padding: 0;
            float: left;
        }
        [data-testid='stFileUploader'] section > input + div {
            display: none;
        }
        [data-testid='stFileUploader'] section + div {
            float: right;
            padding-top: 0;
        }

    </style>
    '''

    st.markdown(css, unsafe_allow_html=True)

    if uploaded_file is not None:
        # Process the uploaded file
        file_contents = uploaded_file.read()
        st.session_state['doc_text'] = file_contents
        # st.session_state['embeddings_model'] = st.selectbox('Embeddings models', [llm_helper.get_embeddings_model()['doc']], disabled=True)
        # st.button("Compute Embeddings", on_click=upload_text_and_embeddings)
        upload_text_and_embeddings()
        # display_predefined_prompts(file_uploaded=True)

try:
    # Set page layout to wide screen and menu item
    menu_items = {
        'Get help': None,
        'Report a bug': None,
        'About': '''
        ## Document and Chat App
        Upload documents and interact with the chatbot to get information.
        '''
    }
    st.set_page_config(layout="wide", menu_items=menu_items)

    llm_helper = LLMHelper()

    # Initialize session state variables
    if 'chat_question' not in st.session_state:
        st.session_state['chat_question'] = ''
    if 'chat_askedquestion' not in st.session_state:
        st.session_state.chat_askedquestion = ''
    if 'chat_history' not in st.session_state:
        st.session_state['chat_history'] = []
    if 'chat_source_documents' not in st.session_state:
        st.session_state['chat_source_documents'] = []
    if 'chat_followup_questions' not in st.session_state:
        st.session_state['chat_followup_questions'] = []
    if 'input_message_key' not in st.session_state:
        st.session_state ['input_message_key'] = 1

    # Initialize Chat Icons
    # user_avatar_style = os.getenv("CHAT_USER_AVATAR_STYLE", "icons")
    # user_seed = os.getenv("CHAT_USER_SEED", "Mia")
    # ai_avatar_style = os.getenv("CHAT_AI_AVATAR_STYLE", "icons")
    # ai_seed = os.getenv("CHAT_AI_SEED", "Mia")
    ai_avatar_style = "🤖"
    ai_seed = "NewAI"
    user_avatar_style = ""
    user_seed = "NewUser"

    # UI layout
    col1, col2, col3 = st.columns([1,0.3,1])
    # with col2:
    #     st.image(os.path.join('images','logo.png'), use_column_width=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Use Markdown syntax to style the text
        st.markdown(
            "<h2 style='text-align: center; font-weight: bold;'>Start Chatting</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align: center; font-size: 15px; font-weight: 100; margin-top: -10px;'>This chatbot is configured to answer your questions</p>",
            unsafe_allow_html=True,
        )

    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        display_predefined_prompts(file_uploaded=True)
    
    
    # st.write("# iPlan")
    # st.write("Upload a document and interact with the chatbot to get information.")

    # Document upload and processing
    # with st.expander("Upload a document", expanded=True):
    # upload_file_and_process()

    # Chatbot interaction
    # with st.expander("Chatbot", expanded=True):
    chatbot_interaction()

except Exception as e:
    st.error(traceback.format_exc())
