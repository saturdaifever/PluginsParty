## Instructions for LLMS

Instructions are loaded and send to the model at launch.  
You can customize models instruction by defining <modelname>.txt files in the instructions directory.

### Instructions loading order

* for_all_intro.txt
* <plugin name>.txt or default.txt
* <plugin named>_plugin.txt or generic_plugin.txt (template beware of properly escaping variable and curly brackets)
* for_all_outro.txt