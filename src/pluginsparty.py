#!/usr/bin/env python3

import openai
from rich import print as rich_print
from rich.markdown import Markdown
from rich.console import Console
import re
import subprocess
import register_plugin 
import json
import requests
import os
import logging
import readline
from halo import Halo
import warnings
import argparse
from register_plugin import register_plugin, create_model_instructions, get_plugins_stubs

logger = logging.getLogger('pluginspartylogger')

# Define the global logger variable at the module level
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def initialize_logger(log_level):
    global logger
    numeric_log_level = logging.getLevelName(log_level.upper())
    logging.basicConfig(level=numeric_log_level, format=log_format)
    logger = logging.getLogger('pluginpartylogger')

# Initialize the global variable chat_completion_args with default values
chat_completion_args = {
    'model': "gpt-3.5-turbo-0301",
    'temperature': 0.7,
    'messages': None,
    'stream': True
}

instruction_role = "system"
messages=[]

console = Console()
plugin_instructions = {}
spinner = Halo(text='', spinner='dot1')

def get_instructions_for_plugin(plugin_url):
    try:
        name, stub = register_plugin(plugin_url)
        # Call create_model_instructions to get instructions for each plugin
        instructions_str, _, _ = create_model_instructions(plugin_url)
        return {"role": instruction_role, "content": instructions_str}
    except Exception as e:
        print(f"Error processing plugin at {plugin_url}: {e}")
        return None

def get_instructions_for_plugins(plugins):
    instructions = []
    for plugin_url in plugins:
        instruction = get_instructions_for_plugin(plugin_url)
        if instruction is not None:
            instructions.append(instruction)
    return instructions



def extract_command(message):
    content = message.get("content")

    triple_curly_pattern = r"(?s).*?(?:(?:```\s*))?\{\{\{(?P<content>.*?)\}\}\}(?:(?:\s*```))?.*"
    simplified_pattern = r"(?P<namespace>[\w_]+)\s*\.\s*(?P<operationid>[\w_]+)\s*\(\s*(?P<args>.*?)\s*\)"
    
    regex_flags = re.IGNORECASE | re.DOTALL

    triple_curly_match = re.search(triple_curly_pattern, content, regex_flags)

    if triple_curly_match:
        triple_curly_content = triple_curly_match.group("content")
        match = re.search(simplified_pattern, triple_curly_content, regex_flags)

        if match:
            namespace, operation_id, params = match.group("namespace"), match.group("operationid"), match.group("args")
            try:
                params = json.loads(params)
            except (ValueError, json.JSONDecodeError) as e:
                error_msg = f"Error: Invalid command format: The 'args' is not a valid JSON object. namespace: {namespace}, operation_id: {operation_id}, parameters: {params}."
                raise InvalidCommandFormatError(error_msg) from e
            return (namespace, operation_id), params
        else:
            error_msg = f"Error: Invalid command format: The command is not well formed. Expected a JSON object as the parameter."
            raise InvalidCommandFormatError(error_msg)
    return None, None


def invoke_plugin_stub(plugin_operation, parameters):
    plugin_name, operation_id = plugin_operation

    # Get the plugins stubs (assuming it's a JSON object)
    plugins_stubs = get_plugins_stubs()

    # Get the stubs for the plugin from the dictionary
    stubs = plugins_stubs.get(plugin_name)
    if not stubs:
        print(f"Error: Plugin '{plugin_name}' not found")
        return None

    # Find the operation in the stubs using the .get() method with a default value
    operation_stub = stubs.get('operations', {}).get(operation_id)
    if not operation_stub:
        print(f"Error: Operation '{operation_id}' not found")
        return None

    # Construct the URL for the API request
    path = operation_stub['path']
    method = operation_stub['method']
    api_url = stubs.get('api', {}).get('url')
    url = api_url.rstrip('/') + path.format(**parameters)

    # Define the headers for the request
    headers = {
        'Content-Type': 'application/json'
    }

    # Load the bearer token from the file, if it exists
    plugin_dir = os.path.join("plugins", plugin_name)
    bearer_file = os.path.join(plugin_dir, "bearer.secret")
    if os.path.exists(bearer_file):
        with open(bearer_file, "r") as f:
            bearer_token = f.read().strip()
        headers['Authorization'] = f'Bearer {bearer_token}'

    # Make the API request using the requests library
    logger.debug(f"{method}")
    logger.debug(f"{url}")
    logger.debug(f"{headers}")
    logger.debug(f"{parameters}")

    response = requests.request(method, url, json=parameters, headers=headers)
 
    # Check if the response is successful
    if response.ok:
        # Check if the response body is empty
        if response.text.strip():
            return response.text
        else:
            content="Error: Response body is empty"
            return content
    else:
        errormsg = f"""
        Error: API request failed with status code {response.status_code}
        Response headers: {response.headers}
        Response content: {response.content} 
        """
        print(errormsg)
        return errormsg


def is_markdown(text):
    markdown_patterns = [
        r'\*\*[\w\s]+\*\*',  # bold
        r'\*[\w\s]+\*',  # italic
        r'\!\[[\w\s]*\]\([\w\/\:\.]+\)',  # image
        r'\[[\w\s]+\]\([\w\/\:\.]+\)',  # link
        r'^#{1,6}\s[\w\s]+',  # headings
        r'^\*[\w\s]+',  # unordered list
        r'^\d\.[\w\s]+',  # ordered list
        r'`[^`]+`',  # inline code
        r'```[\s\S]*?```',  # code blocks
        r'(?:(?:\|[^|]+\|)+\r?\n)+(?:\|[-:]+)+\|',  # tables
        r'^>{1,}\s[\w\s]+',  # blockquotes
        r'^-{3,}\s*$',  # horizontal rule (hyphens)
        r'^\*{3,}\s*$',  # horizontal rule (asterisks)
        r'^_{3,}\s*$',  # horizontal rule (underscores)
        r'<[\w\/]+>',  # HTML tags (basic support)
        r'~~[\w\s]+~~',  # strikethrough (extended syntax)
    ]

    for pattern in markdown_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    return False

def print_markdown(text):
    if is_markdown(text):
        md = Markdown(text)
        console = Console()
        console.print(md)
    else:
        print(text)

def send_messages(messages, spin=False):
    # Create a spinner with the default style
 
    chat_completion_args['messages']=messages
    if (spin and not chat_completion_args['stream']): spinner.start()
    response = openai.ChatCompletion.create(**chat_completion_args)
    if (spin and not chat_completion_args['stream']): spinner.stop()

    buffer = ""
    markdown_buffer = ""
    in_markdown = False
    rawcontent = ""

    if (chat_completion_args['stream']==False):
        rawcontent=response['choices'][0]['message']['content']
        print_markdown(rawcontent)
        return rawcontent

    for message in response:
        choice = message['choices'][0]['delta']
        if 'content' in choice:
            content = choice['content']
            buffer += content
            rawcontent += content                              
            while buffer:
                if not in_markdown:
                    if '<mrkdwn'.startswith(buffer):
                        break
                    elif buffer.startswith('<mrkdwn>'):
                        buffer = buffer[len('<mrkdwn>'):]
                        in_markdown = True
                    else:
                        print(buffer, end='')
                        buffer = ""
                else:
                    if '</mrkdwn'.startswith(buffer):
                        break
                    if buffer.startswith('</mrkdwn>'):
                        buffer = buffer[len('</mrkdwn>'):]
                        md = Markdown(markdown_buffer)
                        console.print(md, end='')
                        markdown_buffer = ""
                        in_markdown = False
                    else:
                        markdown_buffer += buffer[0]
                        buffer = buffer[1:]

    if buffer:
        print(buffer, end='')

    if markdown_buffer:
        md = Markdown(markdown_buffer)
        console.print(md, end='')
    return rawcontent

def read_instructions(model_name):
    instructions_path = f'instructions/{model_name}.txt'
    default_instructions_path = 'instructions/default.txt'

    if not os.path.exists(instructions_path):
        logger.debug(f"No specific model instructions text file found for {model_name}. Using default.")
        instructions_path = default_instructions_path
    else:
        logger.debug(f"Specific model instructions text file found for {model_name}.")

    instructions = []
    with open(instructions_path, 'r') as file:
        for line in file:
            escaped_line = json.dumps(line.strip())
            instructions.append({"role": f"{instruction_role}", "content": escaped_line})

    return instructions

def find_last_code_block(messages):
    # Define regex patterns for single and triple backtick code blocks
    triple_backtick_pattern = r'```(.*?)```'
    single_backtick_pattern = r'`(.*?)`'
    
    # Iterate through the messages in reverse order
    for message in reversed(messages):
        # Check if the role is "assistant"
        if message['role'] == 'assistant':
            # Use regex to extract the code block surrounded by triple backticks
            triple_backtick_match = re.search(triple_backtick_pattern, message['content'], re.DOTALL)
            if triple_backtick_match:
                return triple_backtick_match.group(1).strip()
            
            # Use regex to extract the code block surrounded by single backticks
            single_backtick_match = re.search(single_backtick_pattern, message['content'], re.DOTALL)
            if single_backtick_match:
                return single_backtick_match.group(1).strip()
    
    return None

def get_user_input(prompt):
    try:
        # Read input from the user with shell-like line editing capabilities
        user_input = input(prompt)
        return user_input
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def start_dialog(first_prompt = "", spin=True, cli_mode=False):

    while True:
        if (spin and not chat_completion_args['stream']): spinner.stop()
        if (first_prompt == ""):
            user_input = get_user_input("\n]")
        else:
            user_input = first_prompt
            print ("]"+user_input)
            first_prompt=""

        if (spin and not chat_completion_args['stream'] ): spinner.start()
        
        if user_input.lower() == "exit":
            break
        if user_input == "/..":
            user_input= "Create a hello world python program and publish it using the gist plugin. Figure out missing parameters by yourserlf."
            print (user_input)

        if user_input == '/m':
            for message in messages:
                print (message)
            continue

        if user_input.startswith('/register'):
        # Split the user input by space to extract the URL
            parts = user_input.split()
            if len(parts) == 2:
                # Extract the URL and invoke the register_plugin function
                url = parts[1]
                
                messages.append(get_instructions_for_plugin(url))
            else:
                print("Invalid input. Usage: /register <url>")
            continue


        # Check if the user input is '!' and there is at least one message in the list
        if user_input == '/!' and messages:
            code_to_execute = find_last_code_block(messages)
            if code_to_execute:
                # Create and append the confirmation asking message with role "assistant"
                confirmation_message = f"Do you want to execute the following code?\n{code_to_execute}\n[y/n]: "
                messages.append({"role": "assistant", "content": confirmation_message})
                
                # Ask for user confirmation and append the user's input with role "user"
                confirmation = input(confirmation_message)
                messages.append({"role": "user", "content": confirmation})
            
                if confirmation.lower() == 'y':
                    # Execute the code as a system command and capture the output
                    result = subprocess.run(code_to_execute, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        # Command executed successfully
                        output_message = result.stdout
                    else:
                        # Command execution failed
                        output_message = f"Command execution failed. Error:\n{result.stderr}"
                    
                    # Add the output message to the messages list with role INSTRUCTIONROLE
                    messages.append({"role": "user", "content": f"<RESPONSE FROM shell> {output_message} </RESPONSE> Interprete the results or silently correct the command if you get an error."})
                    print (output_message)
                    send_messages(messages, spîpin)

                    # Send the message using send_messages function
                    rawcontent = send_messages(messages, spin)               
            else:
                print("No code block found in the assistant's messages.")
            continue

        
        messages.append({"role": "user", "content": user_input})
        rawcontent = send_messages(messages, spin)
        messages.append({"role": "assistant", "content": rawcontent})

        # Print the assistant's response to diagnose the issue
        # print("\nAssistant's response:", rawcontent)

        exception_count = 0
        max_exceptions = 3

        retry = True

        while(retry):
            try:
                plugin_operation, params = extract_command(messages[-1])
                if plugin_operation:
                    logger.info(f"Invoking plugin operation {plugin_operation}")
                    response = invoke_plugin_stub(plugin_operation, params)  # Update the function call
                    console.print("```\n"+response+"\n```")
                    messages.append({"role": "user", "content": f"<RESPONSE FROM {plugin_operation}> {response} </RESPONSE> Answer my initial question given the plugin response. You can use the results to initiate another plugin call if needed."})
                    logger.info(f"Sending plugin response (SUCCESS) to model")
                    send_messages(messages,spin)
                retry=False
            except (Exception) as e:
                if exception_count < max_exceptions:
                    logger.info(f"Plugin invocation failed: {str(e)}")
                    errormessage = "Invalid Plugin function call. Check the parameter is a well-formed JSON Object."
                    messages.append({"role": "user", "content": f"<RESPONSE FROM plugin> {errormessage} </RESPONSE> analyse the error and try to correct the command. Make sure it respects the format and that the syntax is valid. (ex: matching opening and closing brackets and parenthesis are mandatory)"})
                    print(f"{str(e)}")
                    logger.info(f"Sending plugin response (FAILURE) to model")
                    send_messages(messages,spin)
                    exception_count += 1
                else:
                    logger.info(f("\nReached maximum number of allowed exceptions - aborting"))
                    retry=False
        if (cli_mode): return

def load_plugins():
    # Define the path to the default_plugins.json file in the plugins directory
    plugins_file_path = os.path.join('plugins', 'default_plugins.json')

    try:
        # Open and read the JSON file
        with open(plugins_file_path, 'r') as file:
            # Load and return the JSON data as a dictionary
            return json.load(file)
    except FileNotFoundError:
        print(f"The file {plugins_file_path} does not exist.")
        return {}
    except json.JSONDecodeError:
        print(f"The file {plugins_file_path} contains invalid JSON data.")
        return {}
    
def main(args):
   # Update the OpenAI API base if a value is provided
    if args.openai_api_base:
        openai.api_base = args.openai_api_base

    if args.log_level.upper() == "SILENT":
        numeric_log_level = logging.CRITICAL + 1
    else:
        numeric_log_level = logging.getLevelName(args.log_level.upper())
        
    # Update the logger.basicConfig initialization to use the specified logging level
    logging.basicConfig(level=numeric_log_level, format=log_format)

    # Update the global variable chat_completion_args with command-line parameters
    global chat_completion_args
    chat_completion_args['model'] = args.model
    chat_completion_args['temperature'] = args.temperature
    chat_completion_args['stream'] = not args.disable_streaming

    global instruction_role
    instruction_role = args.instruction_role

    #Don't set streaming to false or api will fail if not supported...

      # Display warnings based on the conditions
    if "vicuna" in args.model and not args.disable_streaming:
        warnings.warn("Using a Vicuna model with streaming enabled is not recommended.")

    if "vicuna" in args.model and args.instruction_role != "user":
        warnings.warn("Using a Vicuna model and instruction role different than 'user' is not recommended.")

    messages.extend(read_instructions('for_all_intro'))
    messages.extend(read_instructions(chat_completion_args['model']))

    # Call the get_instructions_for_plugins function and append each instruction to the messages list
    plugins = load_plugins()
    logger.debug(f"fetching instruction for :{plugins}")
    plugin_instructions = get_instructions_for_plugins(plugins)
    logger.debug(f"instructions :{plugin_instructions}")
    #for instruction in plugin_instructions:
    messages.extend(plugin_instructions)
    messages.extend (read_instructions('for_all_outro'))
    logger.debug(messages)
    logger.info("Sending instructions to model")
    rawcontent = send_messages(messages)
    
    start_dialog(args.prompt, not args.disable_spinner, args.cli)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configure the AI model and API settings.")
    parser.add_argument("--model", default="gpt-3.5-turbo-0301", help="Specify the model to use.")
    parser.add_argument("--disable-streaming", action="store_true", default=False, help="Disable streaming mode.")
    parser.add_argument("--instruction-role", default="system", choices=["system", "user"], help="Specify the instruction role.")
    parser.add_argument("--temperature", type=float, default=0.7, help="Specify the temperature.")
    parser.add_argument("--disable-spinner", action="store_true", default=False, help="Disable spinner.")
    parser.add_argument("--hide-raw-plugin-reponse", action="store_true", default=False, help="Hide plugin raw reponse.")

    parser.add_argument("--prompt", default="", type=str, help="Send a prompt") 
    parser.add_argument("--cli", action="store_true", default=False, help="Enable CLI mode (exit after first answer).")  # New argument
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "SILENT"], 
                        help="Specify the logging level.")
    # Check for the OPENAI_API_BASE environment variable and set the default value
    default_openai_api_base = os.environ.get("OPENAI_API_BASE", None)

    parser.add_argument("--openai_api_base", default=default_openai_api_base, help="Specify the OpenAI API base URL.")
    parser.add_argument("--openai_api_key", default=os.environ.get("OPENAI_API_KEY"), required=not os.environ.get("OPENAI_API_KEY"), help="Specify the OpenAI API key.")

    args = parser.parse_args()
    main(args)


