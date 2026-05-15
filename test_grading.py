import sys
import os

# We will trick OR114-2_midtermProject_exampleCode_grading_program.py
# into loading our algo_union_submit by substituting the algorithm_module.
import algo_union_submit

# The real example_code grading script needs MTP_lib
sys.path.insert(0, os.path.join(os.getcwd(), 'example_code'))
from datetime import datetime

def check_format(assignment, relocation):
    for i in assignment:
        if not isinstance(i, int):
            return False
            
    for relocate in relocation:
        if not isinstance(relocate[0], int) and not isinstance(relocate[1], int) and not isinstance(relocate[2], int):
            return False

        date_format = "%Y/%m/%d %H:%M"

        try:
            dateObject = datetime.strptime(relocate[3], date_format)
        except ValueError:
            return False

        import re
        r = re.compile('.{4}/.{2}/.{2} .{2}:.{2}')
        if r.match(relocate[3]) is None:
            return False
            
        # Optional strict check just to be safe
        if len(relocate) > 4:
            return False
            
    # Check -1 vs 0
    if 0 in assignment:
        print("Warning: 0 found in assignment, expected -1 for rejected!")
        return False

    return True

print("Running grading check on data/instance04.txt")
file_path = 'data/instance04.txt'
assignment, relocation = algo_union_submit.heuristic_algorithm(file_path)

if check_format(assignment, relocation):
    print("FORMAT PASS: The output perfectly matched the format requirements!")
else:
    print("FORMAT FAIL: The output deviated from the format requirements!")
    print("Length of a relocation item:", len(relocation[0]) if relocation else "Empty")
    
print("Testing instance01...")
try:
    a, r = algo_union_submit.heuristic_algorithm('data/instance01.txt')
    if check_format(a, r):
        print("instance01: FORMAT PASS")
    else:
        print("instance01: FORMAT FAIL")
except Exception as e:
    print(f"instance01 failed with exception: {e}")
