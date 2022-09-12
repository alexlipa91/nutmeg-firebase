import glob
import sys
import fileinput

commit_sha = sys.argv[1]

for filepath in glob.glob('functions-python/**/requirements.txt', recursive=True):
    for line in fileinput.input(filepath, inplace=True):
        if "subdirectory=nutmeg_utils&egg=nutmeg_utils" in line:
            sys.stdout.write("-e git+https://github.com/alexlipa91/nutmeg-firebase.git@{}#subdirectory=nutmeg_utils&egg=nutmeg_utils\n".format(commit_sha))
        else:
            sys.stdout.write(line)
