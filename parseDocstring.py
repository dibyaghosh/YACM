import sys
import nbformat.notebooknode as nn
import json


isOK = lambda cell: '%%rundoctest' == cell['source'].split('\n')[0].strip().replace(' ', '')


def parseDoctest(cell):
    line,cell = cell.split("\n")[0],cell.split("\n")[1:]
    allDocTests = []
    currDocTest = ""
    for newLine in cell:
        if newLine == "":
            allDocTests.append(currDocTest)
            currDocTest = ""
        else:
            currDocTest += newLine+"\n"
    if currDocTest != "":
        allDocTests.append(currDocTest)
    return allDocTests

docTestExample = """
{
'code': r\"\"\"
%s
\"\"\",
'hidden': False,
'locked': False
}
"""

submissionCells = [{'cell_type': 'code',
  'execution_count': None,
  'metadata': {'collapsed': False},
  'outputs': [],
  'source': '# For your convenience, you can run this cell to run all the tests at once!\nimport os\n_ = [autograder.grade(q[:-3]) for q in os.listdir("tests") if q.startswith(\'q\')]'},
 {'cell_type': 'code',
  'execution_count': None,
  'metadata': {'collapsed': True},
  'outputs': [],
  'source': 'import gsExport\ngsExport.generateSubmission()'}]


okTest = open("generators/ok_example.py").read()


def insertDoctests(dts):
    return [docTestExample%value for value in dts]

questionNum = 1
allTests = []

def generateOKTestFile(cell,builddirectory,to_file=False):
    global questionNum
    name = 'Question'
    points = 1
    doctest_list = insertDoctests(parseDoctest(cell['source']))
    doctests = ",".join(doctest_list)
    output = okTest%(name,points,doctests)
    fname = "%s/tests/q%d.py"%(builddirectory,questionNum)
    if to_file:
        open(fname,"w").write(output)
    cell['source'] = "_ = autograder.grade('q%d')"%questionNum
    allTests.append({"score":1, "num":"q%d"%questionNum, "name":"Question %d"%questionNum})
    questionNum += 1

def generateDoctests(notebook,builddirectory="",output=False):
    notebook.cells = [c for c in notebook.cells if 'import doctest' not in c['source']]
    cells = [c for c in notebook.cells if isOK(c)]
    [generateOKTestFile(c,builddirectory,output) for c in cells]
    notebook.cells.append(nn.NotebookNode(submissionCells[0]))
    notebook.cells.append(nn.NotebookNode(submissionCells[1]))
    testData = {"tests":allTests}


