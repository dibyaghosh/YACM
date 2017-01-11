import nbformat as nbf
import sys
import parseDocstring as docparse
import os

def load_notebook(name):
    return nbf.read(name,nbf.current_nbformat)

def fix_notebook(nb):
    for cell in nb.cells:
        fix_cell(cell)
    joinSetups(nb)
    return nb

#isSetup = lambda cell: 'specialcell_type' in cell['metadata'] and cell['metadata']['specialcell_type'] == 'setup'
isSetup = lambda cell: '#SETUP' == cell['source'].split('\n')[0].strip().replace(' ', '')
isOK_test1 = lambda cell: '#OK' == cell['source'].split('\n')[0].strip().replace(' ', '')
isOK_test2 = lambda cell: '%%rundoctest' == cell['source'].split('\n')[0].strip().replace(' ', '')
isOK = lambda cell: isOK_test1(cell) or isOK_test2(cell)
isSolution = lambda cell: '#SOLUTION' == cell['source'].split('\n')[0].strip().replace(' ', '')


def joinSetups(nb):
    allSetups = [c for c in nb.cells if isSetup(c)]
    if len(allSetups) == 0:
        return nb
    firstSetup = allSetups[0]
    firstSetup['source'] += "\nfrom client.api.assignment import load_assignment\nautograder = load_assignment('main.ok')"
    nb.cells = [firstSetup] + [c for c in nb.cells if not isSetup(c)]
    return nb


def generate_combined(nbs,base=None):
    if base is None:
        base = load_notebook(os.path.normpath("generators/preamble.ipynb"))
    for nb in nbs:
        base.cells.extend(nb.cells)
    joinSetups(base)
    return base



def save_notebook(nb,name):
    nbf.write(nb,open(name+".ipynb","w"))

def fix_cell(cell):
    if isSolution(cell):
        cell['metadata']['purpose'] = 'solution'
        if cell['cell_type'] == 'markdown':
            fix_cell_markdown(cell)
        elif cell['cell_type'] == 'code':
            fix_cell_code(cell)
    clear_outputs(cell)

def fix_cell_markdown(cell):
    cell['source'] = 'Enter your solution here'
def fix_cell_code(cell):
    print("Fixing: ",cell)
    lines = cell['source'].split('\n')[1:]
    i = 0
    result = []
    while i < (len(lines)-1):
        if "#solution" in lines[i].lower():
            lines[i] = ""
            i +=1
            continue
        if '=' in lines[i]:
            lines[i] = lines[i].split('=')[0] + '= ... # Write your solution here'
        result.append(lines[i])
        if 'def ' in lines[i]:
            result.append( '\t... # Your code here')
            i += 1
            while i <= len(lines)-1 and '\t' in lines[i]:
                i += 1
        i += 1

    cell['source'] = "\n".join(result)
    print("\n".join(result))
def clear_outputs(cell):
    if 'outputs' in cell:
        cell['outputs'] = []


def generate_solution(nb):
    nb = nb.copy()
    nb.cells = [cell for cell in nb.cells if not isOK(cell)]
    return nb

def generate_student(nb_orig):
    nb = nb_orig.copy()
    fix_notebook(nb)
    docparse.generateDoctests(nb,"",False)
    return nb


if __name__ == "__main__":
    fileToParse = sys.argv[-1]
    print("Attempting to read from : ", fileToParse+".ipynb")
    nb = load_notebook(fileToParse+".ipynb")
    outputLocation = "build/%s"%fileToParse


    print("Generating Solution Notebook")
    solution_nb = generate_solution(nb)
    save_notebook(solution_nb,"%s/solution"%outputLocation)


    print("Parsing notebook")
    fix_notebook(nb)


    print("Generating OK Tests")
    docparse.generateDoctests(nb,outputLocation)
    save_notebook(nb,"%s/student"%outputLocation)
    save_notebook(nb,"%s/grading/base"%outputLocation)
    print
