from flask import Flask,request, send_from_directory,render_template,abort,redirect
import os
import pypandoc
import nbformat
from nbconvert import MarkdownExporter
import glob
import parseNotebook as pN
import parseDocstring as docparse
from file_utils import FileMonitor
import shutil
import json
from subprocess import Popen
from os.path import join,normpath,exists
######
#
# FLASK STARTUP
#
######

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
	return open("index.html").read()


@app.route('/lab')
def browse_labs():
	return open("browse_labs.html").read()

@app.route('/hw')
def browse_hws():
	all_hws = get_all_hws()
	hw_names = list(enumerate([i['name'] for i in all_hws]))
	return render_template("browse_hws.html",hws=hw_names)

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
			self.set_description("Generic Description AF")
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
	if not hw_exists(hw_num):
		abort(404)

	if notebook_monitor:
		notebook_monitor.refresh()

	info = get_hw_info(hw_num)
	title = info['name']
	nb_names = info['order']

	all_notebooks = notebook_monitor.get_viewable_files()
	all_other_notebooks = [i for i in all_notebooks if i[0] not in nb_names]
	all_current_notebooks = [i for i in all_notebooks if i[0] in nb_names]
	print(all_current_notebooks)

	base_nb_location = join(os.getcwd(),'materials','hw',str(hw_num),'preamble.ipynb')
	base_nb = pN.load_notebook(base_nb_location)

	nbs = [pN.load_notebook(to_full_path(nb_name)) for nb_name,last_updated in all_current_notebooks]
	combined = pN.generate_combined(nbs,base=base_nb)
	html = nb_to_html(combined)


	return render_template("edit_hw.html",title=title,notebook=html,nb_files=all_other_notebooks,curr_files=all_current_notebooks,hw_num=hw_num)

def get_all_hws():
	i = 1
	all_hws = []
	while os.path.exists(os.path.join('materials','hw',str(i))):
		all_hws.append(get_hw_info(i))
		i += 1
	return all_hws

def how_many_hws():
	i = 0
	while os.path.exists(os.path.join('materials','hw',str(i+1))):
		i+=1 
	return i	

def hw_exists(i):
	path_to_json = os.path.join('materials','hw',str(i),'info.json')
	return os.path.exists(path_to_json)

def get_hw_info(i):
	path_to_json = os.path.join('materials','hw',str(i),'info.json')
	if os.path.exists(path_to_json):
		return json.load(open(path_to_json))
	return None

def set_hw_info(i,name=None,order=None):
	current = get_hw_info(i)
	if name is not None:
		current['name'] = name
	if order is not None:
		current['order'] = order
	path_to_json = os.path.join('materials','hw',str(i),'info.json')
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





@app.route('/update/hw/<int:hw_num>',methods=['POST'])
def update_hw(hw_num):
	if not hw_exists(hw_num):
		abort(404)
	if 'order' in request.form:
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
		num = how_many_hws() + 1
		create_new_hw(num,name)
		return redirect('/edit/hw/%d'%num)
	if new_type == 'lab':
		pass
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
