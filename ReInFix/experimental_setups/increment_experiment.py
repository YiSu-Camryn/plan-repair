"""Create a new experiment folder under ReInFix/experimental_setups/."""

import os

BASE = os.path.join(os.path.dirname(__file__))
LIST_PATH = os.path.join(BASE, "experiments_list.txt")

SUBDIRS = (
    "logs",
    "responses",
    "external_fixes",
    "saved_contexts",
    "mutations_history",
    "plausible_patches",
    "spec_logs",
)

with open(LIST_PATH, "r+", encoding="utf-8") as expl:
    exps = expl.read().splitlines()
    last_exp = int(exps[-1].split("_")[1]) if exps else 0
    new_name = "experiment_{}".format(last_exp + 1)
    print("Creating experiment folder:", last_exp + 1)
    expl.write(new_name + "\n")
    exp_dir = os.path.join(BASE, new_name)
    os.mkdir(exp_dir)
    for sub in SUBDIRS:
        os.mkdir(os.path.join(exp_dir, sub))
