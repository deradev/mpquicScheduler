"""
Module to create a file with the file sizes

From : http://mayankjohri.wordpress.com/2008/07/02/create-list-of-files-in-a-dir-tree/

"""

import os
import sys
from argparse import ArgumentParser

LIST_FILE = "file_sizes.txt"

def get_filesize(path):
    """ Module to list file sizes"""
    file_list = []
    for root, _ , files in os.walk(path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            file_size = os.path.getsize(file_path)
            file_list.append((file_path, file_size))
            file_list.sort()
    return file_list

def create_filelist(list_filename=LIST_FILE, path="."):
    """ Module to create a file list"""
    try:
        list_file = open(list_filename, 'w')
    except IOError:
        print "Unable to open file: ", list_filename
        return None
    for file_path, size in get_filesize(path):
        list_file.write(" ".join((file_path, str(size), "\n")))
    list_file.close()

def create_arguments(parser):
    """ Adding arguments to the parser"""
    parser.add_argument("-f", "--list_file", help="file to print the list to")
    parser.add_argument("-p", "--path", help="path to the files")

def main():
    """ Main program wrapper"""
    parser = ArgumentParser(description='Process arguments')
    create_arguments(parser)
    args = parser.parse_args()
    if not args.list_file or not args.path:
        print "Please Eneter the list_file and path.\n Exitting..."
        print args.list_file, args.path
        return
    list_file = args.list_file
    path = args.path
    print "list_file", list_file, 'path', path
    create_filelist(list_file, path)

if __name__ == "__main__":
    sys.exit(main())

