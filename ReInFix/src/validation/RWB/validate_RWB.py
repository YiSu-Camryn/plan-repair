import json
import random
import sys
import javalang
import subprocess
import re
import subprocess as sp



def clean_parse_rwb(folder, dataset):
    if dataset == "RWBV1.0":
        with open(folder + "../../../RWB_dataset/RWB-V1.0.json", "r") as f:
            result = json.load(f)
    else:
        with open(folder + "../../../RWB_dataset/RWB-V2.0.json", "r") as f:
            result = json.load(f)

    cleaned_result = {}
    for k, v in result.items():
        lines = v['buggy'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        cleaned_result[k + ".java"] = {"buggy": "\n".join([line[leading_white_space:] for line in lines])}
        lines = v['fix'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        cleaned_result[k + ".java"]["fix"] = "\n".join([line[leading_white_space:] for line in lines])
        cleaned_result[k + ".java"]["location"] = [location - v['start'] + 1 for location in v["location"]]
    return cleaned_result


def git_reset(repo_dir_path):
    sp.run(['git', 'reset', '--hard', 'HEAD'],
           cwd=repo_dir_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)


def git_clean(repo_dir_path):
    sp.run(['git', 'clean', '-df'],
           cwd=repo_dir_path, stdout=sp.DEVNULL, stderr=sp.DEVNULL)


def compile_repo(repo_dir_path):
    # actual compiling
    compile_proc = sp.run(
        ['mvn', 'compile', '-Drat.skip=true'],
        stdout=sp.PIPE, stderr=sp.PIPE, cwd=repo_dir_path)

    return compile_proc.returncode


def run_test(source, repo_dir_path):
    bugg = False
    compile_fail = False
    timed_out = False
    entire_bugg = False
    log = ""
    failing_tests = 0

    # try:
    #     tokens = javalang.tokenizer.tokenize(source)
    #     parser = javalang.parser.Parser(tokens)
    #     parser.parse()
    # except:
    #     print("Syntax Error")
    #     return compile_fail, timed_out, bugg, entire_bugg, True, None

    if compile_repo(repo_dir_path) != 0:
        return True, timed_out, bugg, entire_bugg, True, None

    print('Check if it passes all the test')

    try:
        test_process = subprocess.run(['mvn', 'test', '-Drat.skip=true'], capture_output=True, cwd=repo_dir_path,timeout=270)
        captured_stdout = test_process.stdout.decode()
        print(captured_stdout)
        pattern = re.compile(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)')
        matches = pattern.findall(captured_stdout)
        failures = int(matches[-1][1])
        errors = int(matches[-1][2])
        failing_tests = failures + errors

    except subprocess.TimeoutExpired:
        timed_out = True
    except Exception as e:
        return True, timed_out, bugg, entire_bugg, True, None

    if not timed_out and failing_tests == 0:
        print('success')
    else:
        entire_bugg = True

    return compile_fail, timed_out, bugg, entire_bugg, False, log


def apply_patch(start_loc, end_loc, buggy_full_path, patch,encoding_mode="utf-8"):
    # bug_path = bug_info['loc']
    # start_loc = bug_info['start']
    # end_loc = bug_info['end']
    # patch = self.patch_code.strip()
    # buggy_full_path = os.path.join(proj_dir, bug_path) 
    print(buggy_full_path)       
    with open(buggy_full_path, 'r', encoding=encoding_mode) as file:
        orig_buggy_code = file.readlines()
    with open(buggy_full_path, 'w', encoding=encoding_mode, errors='ignore') as file:
        patched = False
        for idx, line in enumerate(orig_buggy_code):
            if start_loc - 1 <= idx <= end_loc -1:
                if not patched:
                    file.write(patch)
                    patched = True
                    print("Patch applied")
            else:
                file.write(line)
        assert patched, f'[ERROR] [ASSERT FAILURE] insert_fix_into_src not pateced'
    return


def validate_patch_rwb(file, dataset="RWBV1.0"):
    if dataset == "RWBV1.0":
        with open("./dataset/RWB-V1.0.json", "r") as f:
            bug_dict = json.load(f)
    else:
        with open("./dataset/RWB-V2.0.json", "r") as f:
            bug_dict = json.load(f)

    current_file = file.split('/')[-1]
    bug_id = current_file.split('.')[0]
    project = bug_id.split("-")[0]
    bug = bug_id.split("-")[1]
    start = bug_dict[bug_id]['start']
    end = bug_dict[bug_id]['end']
    fixed_class_path = bug_dict[bug_id]["fixed_class_path"]

    print(current_file, bug_id)

    git_reset(f"./data/{project}/{bug}f")
    git_clean(f"./data/{project}/{bug}f")

    with open(file, 'r') as f:
        patch = f.readlines()
    patch = ''.join(patch)
    print(patch)
    buggy_full_path = f"./data/{project}/{bug}f/{fixed_class_path}" 

    try:
        with open(buggy_full_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except:
        with open(buggy_full_path, 'r', encoding='ISO-8859-1') as f:
            original_content = f.read()
    apply_patch(start, end+1, buggy_full_path,patch)

    compile_fail, timed_out, bugg, entire_bugg, syntax_error, log = run_test("",f"./data/{project}/{bug}f/")
    # print(compile_fail, timed_out, bugg, entire_bugg, syntax_error, log)

    try:
        with open(buggy_full_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
            print("File resumed!")
    except:
        with open(buggy_full_path, 'w', encoding='ISO-8859-1') as f:
            f.write(original_content)

    


    if not compile_fail and not timed_out and not bugg and not entire_bugg and not syntax_error:
        print("{} has valid patch: {}".format(bug_id, file))
        directory = "./Results/passed/"
        with open(f"{directory}{bug_id}.java", 'w', encoding='utf-8') as f:
            f.write(str(patch))
        return True, None
    else:
        compile_fail, timed_out, bugg, entire_bugg, syntax_error, log
        print("{} has invalid patch: {}".format(bug_id, file))
        if compile_fail:
            message = "Compile Fail"
        elif timed_out:
            message = "Time Out"
        elif syntax_error:
            message = "Syntex Error"
        else:
            message = "Test Fail"
        # with open(f"./data/{project}/{bug}f/{fixed_class_path}", 'w', encoding='utf-8') as f:
        #     f.write(str(source))
        return False, message


def run_validation_rwb(file, output):
    # start = output.find("// Fixed Function")
    # end = output.rfind("}") + 1
    # patch = output[start:end]
    patch = output
    try:
        with open(f"./Results/RWB/{file}", 'w') as f:
            print(file)
            f.write(patch)
    except:
        with open(f"./Results/RWB/{file}", 'w') as f:
            f.write("write error ... ")
    return validate_patch_rwb(f"./Results/RWB/{file}", "RWBV1.0")

def shuffle_validated_patches(candidate_patches):
    items = list(candidate_patches.items())
    random.shuffle(items)
    shuffled_patches = {key: value for key, value in items}
    return shuffled_patches

class Logger(object):
    def __init__(self, filename='default.log', stream=sys.stdout):
        self.terminal = stream
        self.log = open(filename, 'a')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        pass



if __name__ == "__main__":
    inference_dataset = clean_parse_rwb(folder="", dataset="RWBV1.0")
    if not os.path.exists('./Results'):
        os.makedirs('./Results')
        os.makedirs('./Results/log')
        os.makedirs('./Results/passed')
        os.makedirs('./Results/RWB')
    sys.stdout = Logger('./Results/log/sf.log', sys.stdout)

    for file, bug in inference_dataset.items():
        print("Validating bug {} ... ".format(file.split(".")[0]))
        repair_result = []
        bug_name = file.split('.')[0]
        input_patch_file = "./sf-patches/"+bug_name+".json"
        candidate_patches = json.load(open(input_patch_file, 'r'))
        candidate_patches = shuffle_validated_patches(candidate_patches)
        j=1

        for candidate_patch in candidate_patches[bug_name]['patches']:
            valid, message = run_validation_rwb(file, candidate_patch)
            print(j)
            j=j+1
            print(valid,message)
            repair_result.append({"output": candidate_patch, "valid": valid})
            if valid==True:
                break
    with open('repair_result.json', 'a', encoding='utf-8') as f:
        json.dump(repair_result, f, ensure_ascii=False, indent=4)
