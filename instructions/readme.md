## Instructions for LLMS

Instructions are loaded and send to the model at launch.  
You can customize models instruction by defining <modelname>.txt files in the instructions directory.

### Instructions loading order

* for_all_intro.txt
* <plugin name>.txt or default.txt
* plugins registration loop (not model specific): 
    * instructions defined(hard coded) in register_plugin.py customized with plugin info - could eventually be templated
* for_all_outro.txt