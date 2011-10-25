#! env/bin/python

import argparse
import os
import glob
from pprint import pprint

import auth
import svnbrowse
import svnmanage
import tornado.ioloop
import tornado.web
import memcache

try:
    import settings
    repos = settings.repositories
except ImportError:
    repos = dict((os.path.basename(i), 'file://%s' % i) for i in glob.glob("/usr/local/svn/repositories/*"))

parser = argparse.ArgumentParser(description="""Starts up a webserver on port 5000
    serving all the local svn repositories""")

class OtherHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("")

@auth.require_basic_auth("Authrealm", auth.ldapauth.auth_user_ldap)
class CreateBranchHandler(tornado.web.RequestHandler):
    def get(self, reponame):
        self.write("creating a new branch for %s ..." % reponame)
        
class CreateTagHandler(tornado.web.RequestHandler):
    def get(self, reponame):
        url = repos[reponame]
        self._render_page(reponame, [], svnbrowse.get_tags(url))
       
    def post(self, reponame):
        url = repos[reponame]
        errors = []
        tagname = self.get_argument('tagname')
        tags = svnbrowse.get_tags(url)
        try:
            svnmanage.create_tag(url, tagname, 'pmanser')
            self.redirect("/%s/tags" % reponame)
        except svnmanage.Error, e:
            errors.append(str(e))

        self._render_page(reponame, errors, tags)

    def _render_page(self, reponame, errors, tags):
        tags = list(reversed(sorted(tags)))
        try:
            latest_tag = tags[0]
        except IndexError:
            latest_tag = None

        try:
            tags = tags[1:]
        except IndexError:
            tags = []

        self.render("templates/newtag.html", errors=errors,
            latest_tag=latest_tag, tags=tags,
            breadcrumbs=[], activecrumb='newtag %s' % reponame)
 

class RepoHandler(tornado.web.RequestHandler):
    def get(self, name, path=""):
        parts = [name]
        parts.extend(path.strip("/").split("/"))
        parts = filter(lambda s: s.strip(), parts)
        #pprint(parts, self)
        url = repos[name]
        files = list(svnbrowse.list_repository(url, path))
        if len(files) == 1 and files[0]['kind'] == 'file':
            #pprint(files, stream=self)
            if int(files[0]['size']) > 1048576:
                source = "File too large to display"
            else:
                source = svnbrowse.highlight_file(url + "/" + path)
            self.render("templates/repofile.html",
                file=files[0], source=source,
                breadcrumbs=parts[:-1], activecrumb=parts[-1],
                svnurl=url + "/" + path)
        else:
            #pprint(files, stream=self)
            readmes = [s for s in files if 'readme' in s['name'].lower()]
            readme = ""
            if len(readmes) > 0:
                readme = svnbrowse.highlight_file(url + "/" + path + "/" + readmes[0]['name'])
            self.render("templates/repodir.html",
                repo={"name": name}, files=files,
                breadcrumbs=parts[:-1], activecrumb=parts[-1],
                svnurl=url + "/" + path, readme=readme)

@auth.require_basic_auth("Authrealm", auth.ldapauth.auth_user_ldap)
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        mc = memcache.Client(['127.0.0.1:11211'], debug=0)
        repos_list = mc.get('repo_list')
        if not repos_list:
            repos_list = list(svnbrowse.list_repositories(sorted(repos.values())))
            mc.set('repo_list', repos_list, time=3600)
        self.render("templates/repolist.html", repos=repos_list)

settings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
}

application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/newtag/(.*)", CreateTagHandler),
    (r"/newbranch/(.*)", CreateBranchHandler),
    (r"/favicon.ico", OtherHandler),
    (r"/styles/(pygments.css)", tornado.web.StaticFileHandler,
        dict(path=settings['static_path'])),
    (r"/styles/bootstrap/(.*css)", tornado.web.StaticFileHandler,
        dict(path=settings['static_path'] + '/twitter-bootstrap-1.3.0')),
    (r"/js/(.*)", tornado.web.StaticFileHandler,
        dict(path=settings['static_path'])),
    (r"/([^/]*)/?(.*)", RepoHandler),
], debug=True)

# with the `debug=True` flag we get autoreloading - whenever a module is changed
# while the webserver is running, the whole thing is reloaded

if __name__ == "__main__":

    args = parser.parse_args()
    application.listen(5000)
    tornado.ioloop.IOLoop.instance().start()
