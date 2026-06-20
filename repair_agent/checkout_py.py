import subprocess
import os
import argparse
import sys
import shutil

def checkout_project(project_name, version):
    write_to = os.path.join("auto_gpt_workspace", "{}_{}_buggy".format(project_name.lower(), version))
    config_file = os.path.join(write_to, ".defects4j.config")

    if os.path.exists(write_to):
        shutil.rmtree(write_to)

    command = f'defects4j checkout -p {project_name} -v {version}b -w {write_to}'

    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Checkout failed with error: {e}")
        sys.exit(1)

    if not os.path.isfile(config_file):
        print(f"Checkout failed: missing {config_file}")
        sys.exit(1)

    print(f"Checkout completed successfully: {write_to}")


parser = argparse.ArgumentParser()
parser.add_argument("project")
parser.add_argument("index")
args = parser.parse_args()

checkout_project(args.project, args.index)
