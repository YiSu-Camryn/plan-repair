import json
import os
from tqdm import tqdm


def extract_name(s):
    return s.split('-')[0]


import subprocess


def generate_and_execute_commands(bug_name):
    bug_id = bug_name.replace("_", "-")
    project = bug_id.split("-")[0].lower() + bug_id.split("-")[1]

    commands = [
        f"python3 ./mf_val_d4j.py -i ./mf-patches/{bug_name} -o ./mf-validation/{bug_name} -d ./dataset/defects4j-mf.json "
    ]

    # 执行命令
    for i, cmd in enumerate(commands, 1):
        print(f"Executing {i}:")
        print(cmd)
        try:
            result = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
            print("Output:")
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Exception info:")
            print(e.output)
        print()


i = 1


def convert_chart_string(input_string):
    parts = input_string.split('_')
    if len(parts) > 1:
        prefix = parts[0].capitalize()
        number = ''.join(filter(str.isdigit, prefix))
        suffix = parts[1].split('.')[0]
        return f'{prefix[:-len(number)]}-{number}'
    else:
        return input_string

patch_path = "mf-patches"
files =os.listdir(patch_path) 
files.sort()

for filename in files:
    if filename.endswith(".json"):
        bug_name = convert_chart_string(filename)
        print(bug_name)
        print(i)
        i += 1
        generate_and_execute_commands(bug_name)
        
