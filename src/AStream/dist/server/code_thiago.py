import os
import json
import os.path

PATH = "C:\Users\Thiago\Desktop"
path = PATH
def list_sizes(path):
    """ Module to list the file sizes """
    files = os.listdir(path)
    files.sort()
    #Initialize dict
    my_dict = dict()
    for file_name in files:
        if os.path.isdir(file_name):
            folder_name = os.listdir(file_name)
            folder_name.sort()
            for folder_name11 in folder_name:
                if os.path.isfile(folder_name11):
                    file_size = os.path.getsize(folder_name11)
                    my_dict[folder_name11] = file_size
                elif os.path.isdir(folder_name11):
                    res = update_dict(folder_name11)
                    my_dict.update(res)
        return my_dict
    
    # store in json file
    with open('result_sizes.txt','w') as obj:
        json.dump(my_dict, obj)
   
list_sizes(PATH);
