from fabric.api import *
from fabric.contrib.console import confirm
import fabric.contrib.files

#
# Update this section, including prod(), with your project-specific data
# 
git_dir = "$HOME/webapps/git/repos"
# replace username in the next path. Can't use $HOME from python.
remote_dir = '/home/username/webapps/newproj_django'
project_name = 'newproj'
code_dir = remote_dir + '/' + project_name
python_dir = remote_dir + '/lib/python2.7'
python_add_str = 'export PYTHONPATH="' + python_dir + ':$PYTHONPATH"; '
host_name = "user.webfactional.com"
user = "user"
install_list = ['django-cms', 'django-reversion']

def prod():
    env.hosts = ['%s@%s' % (user, host_name)]

#

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

def mysqldump():
    """
    Saves a copy of the database into the tmp directory.
    Modify this code directly if needed, as it hardwires the username, db name and filename.
    Usage:
        fab prod mysqldump
    (you will be prompted for the db user's password unless you add the pwd directly
    after the -p, with no space or quotes)
    """
    run("mysqldump -u database_user database_name -p > ~/tmp/exported_db.sql")

def deploy(app_to_migrate=""):
    """
    To save some output text and time,
    if you know only one app has changed its database
    structure, you can run this with the app's name.

    Usage:
        fab prod deploy
        fab prod deploy:myapp
    """
    mysqldump() # backup database before making changes
    with cd(code_dir):
        run("git pull")
        run(python_add_str + "python manage.py migrate %s" % app_to_migrate)
        run(python_add_str + "python manage.py createinitialrevisions") # only if using reversion
        run(python_add_str + "python manage.py collectstatic --noinput")
        run("../apache2/bin/restart")

#
# Extra command to import the database backup if necessary
#
def mysql_import():
    """
    Imports a database from the tmp directory.
    Use very carefully! (or just to remind yourself how to import mysql data)
    Modify this code directly if needed, as it hardwires the username, db name and filename.
    Usage:
        fab prod mysql_import
    (you will be prompted for the db user's password)
    """
    # first make another copy of the db
    run("mysqldump -u database_user database_name -p > ~/tmp/exported_db_temp.sql")
    # then import from the backup
    run("mysql -u database_user -p -D database_name < ~/tmp/exported_db.sql")

#def scp(filepath):
#    "This is only here to remind me how to use scp"
#    run("scp filename username@webNNN.webfaction.com:path")

#
#  Methods for initial installation
#
def update_ssh_shortcut(output_keyfile, quickname=None):
    """
    Set up an ssh shortcut.
    Called by setup_ssh_keys.
    You can call it separately if desired.

    Usage:
       fab update_quick_ssh:keyfilename,quickname
    """
    if quickname:
        with settings(warn_only=True):
            local("touch $HOME/.ssh/config")
        local(r"echo '' >> $HOME/.ssh/config")
        local(r"echo 'Host %s' >> $HOME/.ssh/config" % quickname)
        local(r"echo '' >> $HOME/.ssh/config")
        local(r"echo 'Hostname %s' >> $HOME/.ssh/config" % host_name)
        local(r"echo 'User %s' >> $HOME/.ssh/config" % user)
        local(r"echo 'IdentityFile ~/.ssh/%s' >> $HOME/.ssh/config" % output_keyfile)
        local(r"echo 'ServerAliveCountMax 3' >> $HOME/.ssh/config")
        local(r"echo 'ServerAliveInterval 10' >> $HOME/.ssh/config")

def setup_ssh_keys(output_keyfile="id_rsa", ssh_type="rsa", quickname=None):
    """
    Generate a new SSH key and deliver it to the server.
    If quickname is provided, also set up an ssh shortcut.
    Use this to enable password-less access to webfaction.
    Based on http://docs.webfaction.com/user-guide/access.html
    and
    http://racingtadpole.com/blog/django-cms-with-webfaction

    Usage:
       fab prod setup_ssh_keys
       fab prod setup_ssh_keys:output_keyfilename
       fab prod setup_ssh_keys:output_keyfilename,rsa|dsa
       fab prod setup_ssh_keys:output_keyfilename,rsa|dsa,quickname

    output_keyfilename defaults to "id_rsa".
    ssh_type defaults to rsa.
    If you include quickname, you can thereafter type just: ssh quickname 
    """
    with settings(warn_only=True):
        local("mkdir -p $HOME/.ssh")
    with cd("$HOME/.ssh"):
        local("ssh-keygen -t %s -f %s" % (ssh_type, output_keyfile))
        for host in env.hosts:
            local("scp %s.pub %s:temp_id_key.pub" % (output_keyfile, host))
    with settings(warn_only=True):
        run("mkdir -p $HOME/.ssh")
    run("cat $HOME/temp_id_key.pub >> ~/.ssh/authorized_keys")
    run("rm $HOME/temp_id_key.pub")
    run("chmod 600 $HOME/.ssh/authorized_keys")
    run("chmod 700 $HOME/.ssh")
    run("chmod go-w $HOME")
    if quickname:
        update_ssh_shortcut(output_keyfile, quickname)

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

def add_git_user(email=None, user_full_name=None):
    """
    """
    with cd(code_dir):
        if email:
            run('git config --global user.email "%s"' % email)
        if user_full_name:
            run('git config --global user.name "%s"' % user_full_name)

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
            run("touch index.html")
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

def initialise(static_webapp_name="myproj_static", 
               git_repo_name="myproj",
               git_user_email=None,
               git_user_name=None):
    """
    In brief:
    Creates a git repo on the server, and fills in the django and static webapps with it.
    Initialises the database, and deploys the app.

    Usage (in the local project directory, e.g. ~/Python/Projects/project) :
        fab prod initialise

    Requires a git webapp, the database, the django webapp, the static webapp
    to have been created on the server already.
    Requires that the local .git/config has no origin yet (e.g. rename it if needed first).

    In detail:
      * Installs pip itself on the server, if needed
      * Creates a new git repo on the server (do not include the .git ending in git_repo_name)
      * Sets the git user name and email address
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

    Just comment out any pieces you don't need in your situation.

    If you also want to set up a new ssh key and shortcut, you can also call:
        fab prod setup_ssh_keys:output_keyfilename,rsa|dsa,quickname
    """
    install_pip()
    create_prod_git_repo(git_repo_name)
    add_git_user(git_user_email, git_user_name)
    add_prod_repo_as_origin_and_push(git_repo_name)
    clone_into_project(git_repo_name)
    add_dirs_to_static(static_webapp_name)
    pip_installs()
    initialise_database()

    with cd(code_dir):
        run(python_add_str + "python manage.py cms check")

    deploy()