#! env/bin/python

import argparse
import os
from pprint import pprint

import auth
import svnbrowse
import svnmanage
import tornado.ioloop
import tornado.web
import memcache

def _temp_auth(*a, **kw): return True
auth.ldapauth.auth_user_ldap = _temp_auth

import settings

parser = argparse.ArgumentParser(description="""Starts up a webserver on port 5000
    serving all the local svn repositories""")

class OtherHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("")

@auth.require_basic_auth("Authrealm", auth.ldapauth.auth_user_ldap)
class RepoHistoryHandler(tornado.web.RequestHandler):
    def get(self, reponame):
        url = settings.repositories[reponame]
        mc = memcache.Client(['127.0.0.1:11211'], debug=0)
        logs = mc.get('%s_history' % reponame.encode('ISO-8859-1'))
        if not logs:
            logs = svnbrowse.list_history(url)
            mc.set('%s_history' % reponame.encode('ISO-8859-1'), logs, time=300)
        self.render("templates/repohist.html", logs=logs, repo={"name": reponame},
            breadcrumbs=[reponame], activecrumb='log', svnurl=url)

@auth.require_basic_auth("Authrealm", auth.ldapauth.auth_user_ldap)
class CreateRepoHandler(tornado.web.RequestHandler):
    def get(self, errors=None):
        errors = errors or []
        self.render("templates/newrepo.html", errors=errors,
            breadcrumbs=[], activecrumb='newrepo', messages=[])
    def post(self):
        reponame = self.get_argument('reponame')
        try:
            svnmanage.create_repo(reponame, 'www-data')
            mc = memcache.Client(['127.0.0.1:11211'], debug=0)

            reload(settings)
            mc.set('repo_list_%s' % reponame,
                svnbrowse.get_root_info(settings.repositories[reponame]), 
                time=3600)

            self.redirect("/%s" % reponame)
        except Exception, e:
            self.get([str(e)])

@auth.require_basic_auth("Authrealm", auth.ldapauth.auth_user_ldap)
class CreateBranchHandler(tornado.web.RequestHandler):
    def get(self, reponame):
        self.write("not ready quite yet ... :)")
        #self.write("creating a new branch for %s ..." % reponame)
        
@auth.require_basic_auth("Authrealm", auth.ldapauth.auth_user_ldap)
class CreateTagHandler(tornado.web.RequestHandler):
    def get(self, reponame):
        self.write("not ready quite yet ... :)")
        #url = repos[reponame]
        #self._render_page(reponame, [], svnbrowse.get_tags(url))
       
    def post(self, reponame):
        self.get(reponame)
        #url = repos[reponame]
        #errors = []
        #tagname = self.get_argument('tagname')
        #tags = svnbrowse.get_tags(url)
        #try:
        #    svnmanage.create_tag(url, tagname, 'pmanser')
        #    self.redirect("/%s/tags" % reponame)
        #except svnmanage.Error, e:
        #    errors.append(str(e))

        #self._render_page(reponame, errors, tags)

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
 

@auth.require_basic_auth("Authrealm", auth.ldapauth.auth_user_ldap)
class RepoHandler(tornado.web.RequestHandler):
    def get(self, name, path=""):
        parts = [name]
        parts.extend(path.strip("/").split("/"))
        parts = filter(lambda s: s.strip(), parts)
        url = settings.repositories[name]
        files = svnbrowse.list_repository2(url, path)
        for f in files: 
            f['webpath'] = "/" + name + f['fullpath']
        if len(files) == 1 and files[0]['kind'] == 'file':
            # TODO fetch file size
            #if int(files[0]['size']) > 1048576:
            #    source = "File too large to display"
            #else:
            #    source = svnbrowse.highlight_file(url + "/" + path)
            source = svnbrowse.highlight_file(url + "/" + path)
            self.render("templates/repofile.html",
                file=files[0], source=source, repo={"name": name},
                breadcrumbs=parts[:-1], activecrumb=parts[-1],
                svnurl=url + "/" + path)
        else:
            readmes = [s for s in files if 'readme' in s['name'].lower()]
            readme = ""
            if len(readmes) > 0:
                readme = svnbrowse.highlight_file(url + "/" + path + "/" + readmes[0]['name'])
            self.render("templates/repodir.html",
                repo={"name": name}, files=[f for f in files if f['fullpath'] not in ("/" + path, '')],
                breadcrumbs=parts[:-1], activecrumb=parts[-1],
                svnurl=url + "/" + path, readme=readme)

@auth.require_basic_auth("Authrealm", auth.ldapauth.auth_user_ldap)
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        mc = memcache.Client(['127.0.0.1:11211'], debug=0)
        names = settings.repositories.keys()
        repos_list = mc.get_multi(names, 'repo_list_')
        missing = set(names) - set(repos_list.keys())
        if len(missing) > 0:
            reload(settings)
            for name in missing:
                url = settings.repositories[name]
                mc.set('repo_list_%s' % name, svnbrowse.get_root_info(url), time=3600)
        self.render("templates/repolist.html", repos=repos_list.values())

@auth.require_basic_auth("Authrealm", auth.ldapauth.auth_user_ldap)
class DumpSettingsHandler(tornado.web.RequestHandler):
    def get(self):
        pprint(settings.repositories, self)

appsettings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
}

application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/dump-settings", DumpSettingsHandler),
    (r"/newtag/(.*)", CreateTagHandler),
    (r"/newbranch/(.*)", CreateBranchHandler),
    (r"/newrepo", CreateRepoHandler),
    (r"/favicon.ico", OtherHandler),
    (r"/styles/(pygments.css)", tornado.web.StaticFileHandler,
        dict(path=appsettings['static_path'])),
    (r"/styles/bootstrap/(.*css)", tornado.web.StaticFileHandler,
        dict(path=appsettings['static_path'] + '/twitter-bootstrap-1.3.0')),
    (r"/js/(.*)", tornado.web.StaticFileHandler,
        dict(path=appsettings['static_path'])),
    (r"/history/([^/]*)/?", RepoHistoryHandler),
    (r"/([^/]*)/?(.*)", RepoHandler),
], debug=True)

# with the `debug=True` flag we get autoreloading - whenever a module is changed
# while the webserver is running, the whole thing is reloaded

if __name__ == "__main__":

    args = parser.parse_args()
    application.listen(5000)
    tornado.ioloop.IOLoop.instance().start()
