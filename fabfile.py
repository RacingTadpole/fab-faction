from fabric.api import *
from fabric.contrib.console import confirm
import fabric.contrib.files

git_dir = "$HOME/webapps/git/repos"
# replace username in the next path. Can't use $HOME from python.
remote_dir = '/home/username/webapps/newproj_django'
project_name = 'newproj'
code_dir = remote_dir + '/' + project_name
python_dir = remote_dir + '/lib/python2.7'
python_add_str = 'export PYTHONPATH="' + python_dir + ':$PYTHONPATH"; '
install_list = ['django-cms', 'django-reversion']

def prod():
    env.hosts = ['user@user.webfactional.com']

def migrate(app=''):
    """
    Usage:
        fab migrate:app_name.

    If you have added a new app, you need to manually run
        python manage.py schemamigration app_name --init.
    """
    if app:
        local("python manage.py schemamigration %s --auto" % app)
        local("python manage.py migrate %s" % app)
        local("python manage.py createinitialrevisions")

def deploy(app_to_migrate=""):
    """
    To save some output text and time,
    if you know only one app has changed its database
    structure, you can run this with the app's name.

    Usage:
        fab prod deploy
        fab prod deploy:myapp
    """
    with cd(code_dir):
        run("git pull")
        run(python_add_str + "python manage.py migrate %s" % app_to_migrate)
        run(python_add_str + "python manage.py createinitialrevisions") # only if using reversion
        run(python_add_str + "python manage.py collectstatic --noinput")
        run("../apache2/bin/restart")

#
#  Methods for initial installation
#
def install_pip():
    """
    Installs pip itself if needed.

    Usage :
        fab prod install_pip
    """
    with settings(warn_only=True):
        run('mkdir $HOME/lib/python2.7')
        run('easy_install-2.7 pip')

def create_prod_git_repo(git_repo_name):
    """
    Creates a new git repo on the server (do not include the .git ending in git_repo_name)

    Usage (in the local project directory, e.g. ~/Python/Projects/project) :
        fab prod create_prod_git_repo:project

    Requires the git webapp to have been created on the server.
    """
    with cd(git_dir):
        run("git init --bare %s.git && cd %s.git && git config http.receivepack true" %
              (git_repo_name,git_repo_name))

def add_prod_repo_as_origin_and_push(git_repo_name):
    """
    Adds the git repo on the server as the local .git repo's origin, and pushes master to it.
    (do not include the .git ending in git_repo_name)

    Usage (in the local project directory, e.g. ~/Python/Projects/project) :
        fab prod add_prod_repo_as_origin:project

    Requires that the local .git/config has no origin yet (e.g. rename it first if it does).
    """
    local("""echo '[remote "origin"]' >> .git/config""")
    local(r"echo '        fetch = +refs/heads/*:refs/remotes/origin/*' >> .git/config")
    local(r"echo '        url = %s:webapps/git/repos/%s.git' >> .git/config" % (env.hosts[0], git_repo_name))
    local(r"git push origin master")

def update_conf_file():
    """
    Updates the apache httpd.conf file to point to the new project
    instead of the default 'myproject'.

    This is called as part of clone_into_project, or you can call
    separately as:  fab prod update_conf_file
    """
    filepath = remote_dir + "/apache2/conf/httpd.conf"
    fabric.contrib.files.sed(filepath, 'myproject', project_name)

def clone_into_project(git_repo_name):
    """
    Clones the git repo into the new webapp, deleting the default myproject project
    and updating the config file to point to the new project.
    Also adds a site_settings.py file to the project/project folder.

    Usage (in the local project directory, e.g. ~/Python/Projects/project) :
        fab prod clone_into_project:project
    """
    repo_dir = git_dir + "/%s.git" % git_repo_name
    with cd(remote_dir):
        run('rm -rf myproject')
        run("git clone %s %s" % (repo_dir, project_name))
        run("echo 'MY_ENV=\"prod\"' > %s/%s/site_settings.py" % (project_name,project_name))
    update_conf_file()

def add_dirs_to_static(static_webapp_name):
    """
    Adds the "/static" and "/media" directories to the static webapp if needed,
    and deletes the default index.html.
    Also adds a project/project/static directory if there isn't one.

    Usage (in the local project directory, e.g. ~/Python/Projects/project) :
        fab prod add_dirs_to_static:static_webapp_name
    """
    static_dir = '$HOME/webapps/%s' % static_webapp_name
    with settings(warn_only=True):
        with cd(static_dir):
            run("mkdir static && mkdir media")
            run("rm index.html")
        with cd(code_dir):
            run("mkdir %s/static" % project_name)

def pip_installs():
    """
    Installs the necessary thirdparty apps
    into the local webapp (not globally) using pip.
    There is probably a better way to do this using a requirements file.
    Also appends a helpful comment to .bashrc_profile.

    Usage (in the local project directory, e.g. ~/Python/Projects/project) :
        fab prod pip_installs
    """
    pip = r'pip-2.7 install --install-option="--install-scripts=$PWD/bin" --install-option="--install-lib=$PWD/lib/python2.7" '
    with settings(warn_only=True):
        run("mkdir $HOME/tmp")
    with cd(remote_dir):
        for installation in install_list:
            run("export TEMP=$HOME/tmp && %s %s" % (pip, installation))
    run("echo '#%s' >> $HOME/.bash_profile" % python_add_str)

def initialise_database():
    """
    Initialises the database to contain the tables required for
    Django-CMS with South.
    Runs syncdb --all and migrate --fake.

    Usage :
        fab prod initialise_database
    """
    with cd(code_dir):
        run(python_add_str + "python manage.py syncdb --all")
        run(python_add_str + "python manage.py migrate --fake")

def initialise(static_webapp_name="myproj_static", git_repo_name="myproj"):
    """
    In brief:
    Creates a git repo on the server, and fills in the django and static webapps with it.
    Initialises the database, and deploys the app.

    Usage (in the local project directory, e.g. ~/Python/Projects/project) :
        fab prod install

    Requires a git webapp, the database, the django webapp, the static webapp
    to have been created on the server already.
    Requires that the local .git/config has no origin yet (e.g. rename it if needed first).

    In detail:
      * Installs pip itself on the server, if needed
      * Creates a new git repo on the server (do not include the .git ending in git_repo_name)
      * Add it as the origin to the local git repo
      * Pushes the local code to the new repo
      * Clones it into the new webapp, deleting the default myproject project
      * Modifies the apache httpd.conf file to point to the new project, not myproject
      * Adds a site_settings.py file
      * Adds the "/static" and "/media" directories to the static webapp if needed
      * Adds a project/project/static directory if there isn't one
      * Adds a comment to .bash_profile for the python path (for the user's ref if desired)
      * Installs the necessary thirdparty apps
      * Initialises the database using South
      * Runs the Django-CMS cms check command
      * Deploys the app as normal (the git pull is redundant but harmless)
    """
    install_pip()
    create_prod_git_repo(git_repo_name)
    add_prod_repo_as_origin_and_push(git_repo_name)
    clone_into_project(git_repo_name)
    add_dirs_to_static(static_webapp_name)
    pip_installs()
    initialise_database()

    with cd(code_dir):
        run(python_add_str + "python manage.py cms check")

    deploy()