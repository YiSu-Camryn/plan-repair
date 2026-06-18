import os
import sys

def list_java_files(main_dir) -> list:
    directory = main_dir
    java_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.relpath(os.path.join(root, file), main_dir))

    return java_files

#with open(os.path.join(sys.argv[1], "files_index.txt"), "w") as fit:
#    fit.write("\n".join(list_java_files(sys.argv[1])))