#!/usr/bin/env python3

from flask import Flask,request, send_from_directory,render_template,abort,redirect,send_file
import os
import pypandoc
import nbformat
from nbconvert import MarkdownExporter
import glob
import shutil
import json
from subprocess import Popen
from os.path import join,normpath,exists
import webbrowser
import zipfile

import server_utils.parseNotebook as pN
from server_utils.file_utils import FileMonitor

######
#
# FLASK STARTUP
#
######

def create_app():
    app = Flask(__name__,static_url_path='')
    def run_on_start(*args, **argv):
        url = "http://127.0.0.1:5000"
        webbrowser.open(url,new=2)
    run_on_start()
    return app
#app = create_app()
app = Flask(__name__,static_url_path='')

app.config['TEMPLATES_AUTO_RELOAD'] = True




######
#
# DIRECTORY SETUP
#
######

FIRST_SETUP_COMPLETE = False
notebook_monitor = None

def start_up_all():
	global notebook_monitor
	if not os.path.exists("materials"):
		print("Never set up before")
		print("Will default to the setup page")

	else:
		for name,subfolder in [('Homework','hw'),('Labs','labs'),('Questions','questions')]:
			if not os.path.exists(os.path.join("materials",subfolder)):
				print("%s Folder doesn't exist? Creating now..."%name)
				os.makedirs(os.path.join(os.getcwd(),'materials',subfolder))
		FIRST_SETUP_COMPLETE = True
		notebook_monitor = FileMonitor('.ipynb',['materials','questions'])

######
#
# STATIC ASSETS
#
######
@app.route('/css/<path:path>')
def send_js(path):
		return send_from_directory(normpath('assets/css'), path)



######
#
# MAIN FILES
#
######
@app.route('/')
def index():
	return render_template("index.html")


@app.route('/lab')
def browse_labs():
	all_hws = get_all_of("lab")
	hw_names = list(enumerate([i['name'] for i in all_hws]))
	return render_template("browse_hws.html",hws=hw_names,file_type="Lab",file_verbose="Lab",type_hidden="lab")

@app.route('/hw')
def browse_hws():
	all_hws = get_all_of("hw")
	hw_names = list(enumerate([i['name'] for i in all_hws]))
	return render_template("browse_hws.html",hws=hw_names,file_type="HW",file_verbose="Homework Assignment",type_hidden="hw")

@app.route('/settings')
def settings():
	return open("settings.html").read()


######
#
# VIEWING INDIVIDUAL NOTEBOOKS
#
######

def nb_to_html(nb):
	md = MarkdownExporter()
	body,resources = md.from_notebook_node(nb)
	output =  pypandoc.convert_text(body, 'html', format='md')
	return output

def back_to_browse(path):
	return path.rpartition("/")[0]

translaters = {'master':lambda x: x, 'solution': pN.generate_solution, 'student': pN.generate_student}

@app.route('/edit/questions/<path:path>')
def edit_notebook(path):
	show_mode = request.args.get('show','master')
	print(show_mode)
	if show_mode not in translaters:
		abort(404)
	if not is_valid_question(path):
		abort(404)
	full_path = to_full_path(path)
	title = os.path.relpath(full_path,os.path.join(os.getcwd(),'materials','questions'))
	last_path = back_to_browse(path)
	

	nb = pN.load_notebook(full_path)
	new_nb = translaters[show_mode](nb)
	nb_html = nb_to_html(new_nb)
	return render_template("edit_question.html",current_path=path,title=title,notebook=nb_html,last_path=last_path,status=show_mode.capitalize())


######
#
# LAUNCHING NOTEBOOKS
#
######

@app.route('/launch/questions/<path:path>')
def launch_notebook(path):
	full_path = to_full_path(path)
	launch(full_path)
	return redirect('/edit/questions/%s'%path)


@app.route('/launch/hw/<int:path>')
def launch_preamble(path):
	file_name = normpath('materials/hw/%d/preamble.ipynb'%path)
	launch(file_name)
	return redirect('/edit/hw/%d'%path)


@app.route('/launch/lab/<int:path>')
def launch_lab(path):
	file_name = normpath('materials/labs/%d/lab.ipynb'%path)
	launch(file_name)
	return redirect('/edit/lab/%d'%path)


def launch(full_path):
	if not os.path.exists(full_path):
		abort(404)
	Popen(['nbopen',full_path])

######
#
# BROWSING DIRECTORIES (UTILS)
#
######

class Folder:
	def __init__(self,path=None,full_path=None):
		self.path = path
		self.fpath = full_path

		if path is None and full_path is None:
			abort(404)

		if not exists(self.full_path()):
			abort(404)

	def full_path(self):
		if self.fpath is not None:
			return self.fpath 
		return join(os.getcwd(),'materials','questions',normpath(self.path))

	def relpath(self):
		if self.path is not None:
			return self.path
		return os.path.relpath(self.fpath,join(os.getcwd(),'materials','questions'))


	def get_description(self):
		path_to_description = join(self.full_path(),'description.txt')
		if not exists(path_to_description):
			self.set_description("Generic Description Here")
		with open(path_to_description) as f:
			return f.read()

	def set_description(self,text):
		path_to_description = join(self.full_path(),'description.txt')
		with open(path_to_description,'w') as f:
			f.write(text)

	def get_directories(self):
		banned = ['.ipynb_checkpoints']
		files = [f for f in os.scandir(self.full_path()) if f.is_dir() and f.name not in banned]

		return [(f.name,Folder(full_path=f.path).get_description()) for f in files]

	def get_questions(self):
		all_relevant_files = glob.glob(join(self.full_path(),"*.ipynb"))
		return [os.path.basename(f) for f in all_relevant_files]

	def new_folder(self,name):
		pass

	def new_question(self,name):
		pass

	def above_folder(self):
		return Folder(full_path=(join(self.full_path(),'..')))

	def to_server(self):
		return self.relpath().replace('\\','/')

def is_valid_question(path):
	return os.path.isfile(to_full_path(path))

######
#
# BROWSING DIRECTORIES
#
######

@app.route('/questions/')
def browse_splash():
	folder = Folder('')
	return browse(folder, title='MAIN DIRECTORY',show_desc=False)

@app.route('/questions/<path:path>')
def browse_directory(path):
	folder = Folder(path)
	return browse(folder,title=path,show_desc=True)

def browse(folder,**kwargs):
	folders = folder.get_directories()
	notebooks  = folder.get_questions()
	current_path = folder.to_server()
	description = folder.get_description()
	last_path = folder.above_folder().to_server()
	return render_template("browse_questions.html",folders=folders,current_path=current_path,description=description, notebooks=notebooks,last_path=last_path,**kwargs)

@app.route('/update_description/<path:path>',methods=['POST'])
def update_description(path):
	if is_valid_question_path(path):
		full_path = to_full_path(path)
		description = request.form['description']
		set_folder_description(full_path,description)
		return redirect('/questions/%s'%path[:-1])
	else:
		abort(404)


######
#
# EDITING HW
#
######
def to_full_path(yo):
	return join(os.getcwd(),'materials','questions',normpath(yo))


@app.route('/edit/hw/<int:hw_num>')
def edit_hw(hw_num):
	show_mode = request.args.get('show','master')
	if show_mode not in translaters:
		abort(404)

	if not exists_of("hw",hw_num):
		abort(404)

	if notebook_monitor:
		notebook_monitor.refresh()

	info = get_info("hw",hw_num)
	title = info['name']
	nb_names = info['order']

	all_notebooks = notebook_monitor.get_viewable_files()
	all_other_notebooks = [i for i in all_notebooks if i[0] not in nb_names]
	all_current_notebooks = [i for i in all_notebooks if i[0] in nb_names]
	all_current_notebooks.sort(key=lambda x: nb_names.index(x[0]))
	print("ALL CURRENT NOTEOOKS" ,all_current_notebooks)

	base_nb_location = join(os.getcwd(),'materials','hw',str(hw_num),'preamble.ipynb')
	base_nb = pN.load_notebook(base_nb_location)

	nbs = [pN.load_notebook(to_full_path(nb_name)) for nb_name,last_updated in all_current_notebooks]
	combined = pN.generate_combined(nbs,base=base_nb)
	new_nb = translaters[show_mode](combined)
	html = nb_to_html(new_nb)
	return render_template("edit_hw.html",title=title,notebook=html,nb_files=all_other_notebooks,curr_files=all_current_notebooks,hw_num=hw_num,status=show_mode.capitalize())


@app.route('/edit/lab/<int:hw_num>')
def edit_lab(hw_num):
	show_mode = request.args.get('show','master')
	if show_mode not in translaters:
		abort(404)

	if not exists_of("lab",hw_num):
		abort(404)

	info = get_info("lab",hw_num)
	title = info['name']

	base_nb_location = join(os.getcwd(),'materials','labs',str(hw_num),'lab.ipynb')
	base_nb = pN.load_notebook(base_nb_location)
	new_nb = translaters[show_mode](base_nb)
	html = nb_to_html(new_nb)
	return render_template("edit_lab.html",title=title,notebook=html,hw_num=hw_num,status=show_mode.capitalize())



downloaders = ['student','solution']

@app.route('/download/hw/<int:hw_num>')
def download_hw(hw_num):
	show_mode = request.args.get('show','student')
	
	if show_mode not in translaters:
		abort(404)

	if not exists_of("hw",hw_num):
		abort(404)

	if notebook_monitor:
		notebook_monitor.refresh()

	info = get_info("hw",hw_num)
	title = info['name']
	nb_names = info['order']

	all_notebooks = notebook_monitor.get_viewable_files()
	all_current_notebooks = [i for i in all_notebooks if i[0] in nb_names]
	all_current_notebooks.sort(key=lambda x: nb_names.index(x[0]))

	base_nb_location = join(os.getcwd(),'materials','hw',str(hw_num),'preamble.ipynb')
	base_nb = pN.load_notebook(base_nb_location)
	print(all_current_notebooks)

	nbs = [pN.load_notebook(to_full_path(nb_name)) for nb_name,last_updated in all_current_notebooks]
	combined = pN.generate_combined(nbs,base=base_nb)

	if show_mode == 'student':
		return download_student_notebook(combined,"hw%d"%hw_num)
	
	elif show_mode == 'solution':
		return download_solution_notebook(combined,"hw%d_solution"%hw_num)
	abort(404)


@app.route('/download/lab/<int:hw_num>')
def download_lab(hw_num):
	show_mode = request.args.get('show','student')
	
	if show_mode not in translaters:
		abort(404)

	if not exists_of("lab",hw_num):
		abort(404)

	base_nb_location = join(os.getcwd(),'materials','labs',str(hw_num),'lab.ipynb')
	base_nb = pN.load_notebook(base_nb_location)

	if show_mode == 'student':
		return download_student_notebook(base_nb,"lab%d"%hw_num)
	
	elif show_mode == 'solution':
		return download_solution_notebook(base_nb,"lab%d_solution"%hw_num)
	
	abort(404)


def download_student_notebook(notebook,name):
	build_directory = join(os.getcwd(),'tmp','student')
	shutil.rmtree(build_directory,ignore_errors=True)
	shutil.copytree(join(os.getcwd(),'generators','student_export'),build_directory)
	notebook = pN.generate_student(notebook,build_directory)
	pN.save_notebook(notebook,join(build_directory,name))
	pN.save_notebook(notebook,join(build_directory,'grading','base'))
	shutil.make_archive(join(os.getcwd(),'tmp',name), 'zip',build_directory)
	return send_file(join(os.getcwd(),'tmp','%s.zip'%name),as_attachment=True,attachment_filename="%s.zip"%name)


def download_solution_notebook(notebook,name):
	solutions = pN.generate_student(notebook)
	pN.save_notebook(solutions,join(os.getcwd(),'tmp',name))
	return send_file(join(os.getcwd(),'tmp','%s.ipynb'%name),as_attachment=True,attachment_filename="%s.ipynb"%name)



start_directory = {"hw":join(os.getcwd(),'materials','hw'), "lab":join(os.getcwd(),'materials','labs')}

def get_all_of(file_type):
	i = 1
	alls = []
	while exists(join(start_directory[file_type],str(i))):
		alls.append(get_info(file_type,i))
		i += 1
	return alls

def how_many_of(file_type):
	i = 0
	while exists(join(start_directory[file_type],str(i))):
		i+=1 
	return i

def exists_of(file_type,i):
	path_to_json = os.path.join(start_directory[file_type],str(i),'info.json')
	return os.path.exists(path_to_json)

def get_info(file_type,i):
	path_to_json = os.path.join(start_directory[file_type],str(i),'info.json')
	if os.path.exists(path_to_json):
		return json.load(open(path_to_json))
	return None


def set_info(file_type,**kwargs):
	current = get_info(file_type,i)
	for k,v in kwargs.items():
		current[k] = v
	path_to_json = os.path.join(start_directory[file_type],str(i),'info.json')
	json.dump(current, open(path_to_json,'w'))

def create_new_hw(i,description="Generic Homework Assignment"):
	path_to_hw = os.path.join(os.getcwd(),'materials','hw',str(i))
	if os.path.exists(path_to_hw):
		print("Already Exists")
		return
	os.makedirs(path_to_hw)
	new_config = {'name':description, 'order':list()}
	json.dump(new_config,open(os.path.join(path_to_hw,'info.json'),'w'))	
	shutil.copyfile(os.path.join('generators','preamble.ipynb'),os.path.join(path_to_hw,'preamble.ipynb'))


def create_new_lab(i,description="Generic Lab"):
	path_to_lab = os.path.join(os.getcwd(),'materials','labs',str(i))
	if os.path.exists(path_to_lab):
		print("Already Exists")
		return
	os.makedirs(path_to_lab)
	new_config = {'name':description}
	json.dump(new_config,open(os.path.join(path_to_lab,'info.json'),'w'))	
	shutil.copyfile(os.path.join('generators','question.ipynb'),os.path.join(path_to_lab,'lab.ipynb'))




@app.route('/update/hw/<int:hw_num>',methods=['POST'])
def update_hw(hw_num):
	if not hw_exists(hw_num):
		abort(404)
	print(request.form)
	if 'order' in request.form:
		print(json.loads(request.form['order']))
		set_hw_info(hw_num, order=json.loads(request.form['order']))
	if 'name' in request.form:
		print(request.form['order'])
	if 'duedate' in request.form:
		print(request.form['duedate'])
	return ''

@app.route('/new',methods=['POST'])
def new_item():
	possible = ['hw','lab','category','question']
	if 'type' not in request.form:
		abort(404)
	new_type = request.form['type']
	if new_type == 'hw':
		name = request.form.get('name','Generic Assignment')
		num = how_many_of("hw") + 1
		create_new_hw(num,name)
		return redirect('/edit/hw/%d'%num)

	if new_type == 'lab':
		name = request.form.get('name','Generic Lab')
		num = how_many_of("lab") + 1
		create_new_hw(num,name)
		return redirect('/edit/labs/%d'%num)

	if new_type == 'category':
		name = request.form.get('name','Generic Category')
		path = request.form.get('path','')
		new_path = os.path.join(os.getcwd(),'materials','questions',path,name)
		print(new_path)
		if not os.path.exists(new_path):
			os.makedirs(new_path)
		return redirect('/questions/%s%s'%(path,name))

	if new_type == 'question':
		name = request.form.get('name','Generic Category')
		path = request.form.get('path','')
		new_path = os.path.join(os.getcwd(),'materials','questions',path,name+".ipynb")
		print("NEW_PATH",new_path)
		if not os.path.exists(new_path):
			shutil.copyfile(os.path.join('generators','question.ipynb'),new_path)
		return redirect('/edit/questions/%s/%s'%(path,name+".ipynb"))

	return 'Sorry! Looks like something messed up. Contact Dibya and we\'ll try to fix it'




if __name__ == '__main__':
	start_up_all()
	app.run(debug=True)
