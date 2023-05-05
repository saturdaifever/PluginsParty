## Bringing ChatGPT plugins support to all LLMs

**early realese**

This project aims to bring **Out-of-the-box support of ChatGPT plugins to more conversational LLMs**.
(**tested working with Vicuna, StableVicuna and of course GPT-3.5, GPT-4)

**Note:** This project does not involve Langchain or AutoGPT.

The client is built to allow LLMs to invoke external plugins, extending LLMs capabilities beyond language generation.  
Models are accessed via the OpenAI client python api

Made to be a **multi-llm plugin** playground and could also be valuable for **plugin test automation**

## Features

- Interactive command-line interface for LLMs conversation
- Markdown rendering for rich text responses
- Support for standard ChatGPT plugins
- Support for multiple language models (Vicuna, StableVicuna, GPT-3.5, GPT-4...)
- Ability to execute code blocks provided by the assistant
- Support for streaming mode with the OpenAI API (where applicable)
- Generic or model-specific instructions support
- Bearer token authentication

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/your-repo/ai-xxxpluginsparty-.git
   cd pluginparty
   ```

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Set the OpenAI API key as an environment variable:
   ```
   export OPENAI_API_KEY=your-api-key
   ```

## Usage

1. Run pluginsparty:
   ```
   python3 src/pluginsparty.py
   ```

2. Enjoy !

3. To exit type `exit` and press Enter.

## Plugin Integration

* Plugins listed in plugins/default_plugins are ***registered*** at start.
* Model is instructed about how to use the plugin

You can also register a plugin while conversing, use the `/register` command followed by the plugin URL:
```
/register https://example.com/plugin.json
```

Once registered, the model will (eventually) invoke the plugin when needed.

## Program Invocation Options

You can customize the behavior of the program using command-line arguments:

- `--model`: Specify the language model to use (e.g., `gpt-3.5-turbo-0301`, `gpt-4`, `vicuna`, `stablevicuna-13b`). Default is `gpt-3.5-turbo-0301`.
- `--disable-streaming`: Disable streaming mode for the OpenAI API (required for FastChat (vicuna/stablevicuna). 
- `--instruction-role`: Specify the instruction role (`system` or `user`). Default is `system`.
- `--temperature`: Specify the temperature for the language model. Default is `0.7`.
- `--openai_api_base`: Specify the OpenAI API base URL (optional).
- `--openai_api_key`: Specify the OpenAI API key (required if not set as an environment variable).

Example usage with command-line arguments:
```
python pluginsparty.py --model gpt-4 --temperature 0.8 --instruction-role user
```

## Internal commands
In addition to interacting with language models and plugins, the AI pluginsparty project provides three internal commands that users can use to perform specific actions within the pluginsparty. These commands are:

1. `/m`: The `/m` command allows users to view the list of messages exchanged between the user and the pluginsparty. When this command is entered, the pluginsparty will display the entire message history, including both user inputs and assistant responses. This can be useful for reviewing previous interactions and instructions.

2. `/!`: The `/!` command allows users to execute the last code block provided by the assistant. When this command is entered, the pluginsparty will search for the most recent code block in the assistant's messages and prompt the user for confirmation before executing the code. If the user confirms with "y" (yes), the code will be executed as a system command, and the output will be displayed. This command is useful for running code snippets provided by the assistant.

3. `/register`: The `/register` command allows users to register a new plugin while conversing. The format of the command is `/register <plugin_url>`. When this command is entered, the pluginsparty will fetch the plugin's manifest, instructions, and operations from the provided URL and register the plugin for use. 

These internal commands enhance the user experience by providing quick access to useful features and actions within the pluginsparty.

## Directory structure

The project is organized into a directory structure that includes important files and directories related to instructions, plugins, and plugin manifests

.
├── instructions              
│   ├── default.txt           
│   ├── for_all_intro.txt
│   ├── for_all_outro.txt
│   ├── readme.md
│   ├── stablevicuna-13b.txt  
│   └── vicuna-13b.txt
├── plugins                   
│   ├── default_plugins.json
│   └── a plugin
│   │   ├── openapi.yaml
│   │   ├── ai-plugin.json
│   │   └── bearer.token
    └── register_plugin.py
├── readme.md
├── requirements.txt
└── src
    ├── pluginsparty.py
    └── register_plugin.py

The **instructions** directory contains instructions for the language models. These instructions can be either generic (applicable to all models) or specific to a particular model.

The **plugins** directory contains subdirectories for caching plugin manifests (ai-plugin.json) and OpenAPI specification (openapi.yaml).
The default_plugins.json file contains a list of plugins that are loaded at startup

The **bearer.secret** file, if present in a plugin directory, contains the bearer token for authenticating with the plugin's API. If the bearer.secret file is not present, the user will be prompted to provide the bearer token when registering the plugin.

## Model instructions

   Models are instructed to use the plugins.
   see [instruction/readme.md](instructions/readme.md)

## Developement to do list

- [x] Bearer Authentication support
- [x] Refining Vicuna model instruction.
- [ ] Explain plugin invocation flow and backend support.
- [ ] OAUTH Authentication support
- [ ] Improve error handling with user feedback
- [ ] List of working plugins with associated known to work prompts
- [ ] Improve documentation
- [ ] Implement unit tests and automated testing for plugins
- [ ] Keep watching for Vicuna Openchat API server streaming support
- [ ] Cleanup/simplify plugins openapi yaml to remove unnecessary information/details (would save tokens and allow llm to focus better)

## Vicuna / StableVicuna

It's amazing to see that quantized 13B parameters models (running locally on a 24GB GPU!) are able (most of the time) to properly construct the commands to invoke the plugins. (Models are prety slow using a P6000, so testing wasn't that extensive, send 4090s in this direction!)

Those models are stuborn, not always following properly instructions but they'll manage! 

Hints & notes: 
* loading one plugin at a time or changing temperature might help.
* They do not support (to confirm) ***System role*** so instructions have to be provided with ***user role***.
* 

## Notes about OpenAI Plugins & models

* plugin manifest and openapi specifications are documented.
* plugin invocation / interpretation / instructions to models to handle plugins are not 
* Most of the plugins (api endpoints) accessible through openai alpha are locked to IPs originating from OpenAI backends (wolfram, owd, etc...). Manifest and openapi specifications are often accessible (If you can find them)

* Plugins **developped for ChatGPT** are usualling working fine
* Plugins developed for langchain or auto-gpt will most of the time not work. (not really following openai plugins spirit - need to document that)

* Alpha chatgpt-plugin model (accessible via chat.openai) seem to use a model with larger token input window (plugin instruction are quite token wasting)

* Some Models are are instructed that they ***do not have access to external information or resources, and not able to browse the internet or access any external data*** so they tend to "believe" what they are told  and refuse to even try following  instructions.
* RL or finetuning including plugin interraction would definitly help. (seems like gpt-35-turbo seems already ***plugin aware***, gpt-4 definitly is)

## List of plugins tested to work

   * weather
   * web_search
   * ...

## Contributing

Contributions to this project are welcome! If you'd like to contribute, please fork the repository, make your changes, and submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Disclaimer

This project is for educational and demonstration purposes only. Please use it responsibly.