#! env/bin/python

import argparse
import os
import random
import string
from pprint import pprint

import svnbrowse
import svnmanage
import tornado.ioloop
import tornado.web
import memcache

import settings

parser = argparse.ArgumentParser(description="""Starts up a webserver on port 5000
    serving all the local svn repositories""")

class RequestHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        mc = memcache.Client(['127.0.0.1:11211'], debug=0)
        try:
            return mc.get(self.get_secure_cookie('octopy_session_id'))
        except mc.MemcachedKeyNoneError:
            return None

class OtherHandler(RequestHandler):
    def get(self):
        self.write("")

class RepoHistoryHandler(RequestHandler):
    @tornado.web.authenticated
    def get(self, path):
        reponame = path.split("/")[0]
        url = settings.repositories[reponame] + "/" + "/".join(path.split("/")[1:])
        # TODO enable caching (again)
        #mc = memcache.Client(['127.0.0.1:11211'], debug=0)
        #logs = mc.get('%s_history' % reponame.encode('ISO-8859-1'))
        #if not logs:
        #    logs = svnbrowse.list_history(url)
        #    mc.set('%s_history' % reponame.encode('ISO-8859-1'), logs, time=300)
        logs = svnbrowse.list_history(url)
        self.render("templates/repohist.html", logs=logs, repo={"name": reponame},
            breadcrumbs=[reponame], activecrumb='log', svnurl=url)

class CreateRepoHandler(RequestHandler):
    @tornado.web.authenticated
    def get(self, errors=None):
        errors = errors or []
        self.render("templates/newrepo.html", errors=errors,
            breadcrumbs=[], activecrumb='newrepo', messages=[],
            site_title=settings.SITE_TITLE)
    @tornado.web.authenticated
    def post(self):
        reponame = self.get_argument('reponame')
        try:
            svnmanage.create_repo(reponame, 'www-data')
            mc = memcache.Client(['127.0.0.1:11211'], debug=0)
            reload(settings)
            url = settings.repositories[reponame]
            mc.set('repo_list_%s' % reponame,
                svnbrowse.get_root_info(url), time=36000)
            mc.set('repo_log_%s' % reponame,
                list(reversed(svnbrowse.list_history(url))), time=36000)
            self.redirect("/%s" % reponame)
        except Exception, e:
            self.get([str(e)])

class CreateBranchHandler(RequestHandler):
    @tornado.web.authenticated
    def get(self, reponame):
        url = settings.repositories[reponame]
        self.render("templates/newbranch.html", errors=[],
            repo={'name': reponame}, breadcrumbs=[], 
            activecrumb='newbranch %s' % reponame)
        
    @tornado.web.authenticated
    def post(self, reponame):
        url = settings.repositories[reponame]
        branchname = self.get_argument('branchname')
        try:
            svnmanage.create_branch(url, branchname, self.get_current_user()['username'])
            self.redirect("/%s/branches" % reponame)
        except svnmanage.Error, e:
            self.render("templates/newbranch.html", errors=[str(e)],
                repo={'name': reponame}, breadcrumbs=[], 
                activecrumb='newbranch %s' % reponame)

class CreateTagHandler(RequestHandler):
    @tornado.web.authenticated
    def get(self, reponame):
        url = settings.repositories[reponame]
        self._render_page(reponame, [], 
            svnbrowse.get_tags(url))
       
    @tornado.web.authenticated
    def post(self, reponame):
        url = settings.repositories[reponame]
        tagname = self.get_argument('tagname')
        try:
            svnmanage.create_tag(url, tagname, self.get_current_user()['username'])
            self.redirect("/%s/tags" % reponame)
        except svnmanage.Error, e:
            self._render_page(reponame, [str(e)], 
                svnbrowse.get_tags(url))

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
            latest_tag=latest_tag, tags=tags, repo={'name': reponame},
            breadcrumbs=[], activecrumb='newtag %s' % reponame)
 

class RepoHandler(RequestHandler):
    @tornado.web.authenticated
    def get(self, name, path=""):
        parts = [name]
        parts.extend(path.strip("/").split("/"))
        parts = filter(lambda s: s.strip(), parts)
        url = settings.repositories[name]
        files = svnbrowse.list_repository2(url, path)
        
        mc = memcache.Client(['127.0.0.1:11211'], debug=0)
        logs = mc.get('repo_log_%s' % str(name))
        if logs is None:
            logs = list(reversed(svnbrowse.list_history(url)))
            mc.set('repo_log_%s' % str(name), logs, time=36000)
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
                breadcrumbs=parts[:-1], activecrumb=parts[-1], logs=logs,
                svnurl=url + "/" + path, currentpath=name + "/" + path)
        else:
            readmes = [s for s in files if 'readme' in s['name'].lower()]
            readme = ""
            if len(readmes) > 0:
                readme = svnbrowse.highlight_file(url + "/" + path + "/" + readmes[0]['name'])
            self.render("templates/repodir.html",
                repo={"name": name}, files=[f for f in files if f['fullpath'] not in ("/" + path, '')],
                breadcrumbs=parts[:-1], activecrumb=parts[-1], logs=logs,
                svnurl=url + "/" + path, readme=readme, currentpath=name + "/" + path)

class MainHandler(RequestHandler):
    @tornado.web.authenticated
    def get(self):
        mc = memcache.Client(['127.0.0.1:11211'], debug=0)
        names = settings.repositories.keys()
        repos_list = mc.get_multi(names, 'repo_list_')
        missing = set(names) - set(repos_list.keys())
        if len(missing) > 0:
            reload(settings)
            for name in missing:
                url = settings.repositories[name]
                repos_list[name] = svnbrowse.get_root_info(url)
                mc.set('repo_list_%s' % name, repos_list[name], time=36000)
        self.render("templates/repolist.html", repos=repos_list.values(), 
                site_title=settings.SITE_TITLE)

class LoginHandler(RequestHandler):
    def get(self):
        self.render("templates/login.html", 
            redirect_to=self.get_argument("next"), errors=[])
    def post(self):
        username = self.get_argument("username")
        password = self.get_argument("password")
        redirect_to = self.get_argument("redirect_to")
        if not settings.auth(username, password):
            return self.render("templates/login.html", redirect_to=redirect_to, 
                errors=['Login failed - invalid credentials'])

        sessid = ''.join(random.choice(string.letters) for i in xrange(32))
        mc = memcache.Client(['127.0.0.1:11211'], debug=0)
        if mc.get(sessid) is not None:
            return self.render("templates/login.html", redirect_to=redirect_to, 
                errors=['Login failed - failed to generate unique key'])

        mc.set(sessid, {'username': username}, time=32400)
        self.set_secure_cookie('octopy_session_id', sessid, expires_days=1)
        self.redirect(redirect_to)

class DumpSettingsHandler(RequestHandler):
    @tornado.web.authenticated
    def get(self):
        pprint(settings.repositories, self)

class FlushCacheHandler(RequestHandler):
    def get(self, name):
        mc = memcache.Client(['127.0.0.1:11211'], debug=0)
        mc.delete('repo_list_%s' % str(name))
        mc.delete('repo_log_%s' % str(name))

appsettings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
}

application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/login", LoginHandler),
    (r"/dump-settings", DumpSettingsHandler),
    (r"/refresh/(.*)", FlushCacheHandler),
    (r"/newtag/(.*)", CreateTagHandler),
    (r"/newbranch/(.*)", CreateBranchHandler),
    (r"/newrepo", CreateRepoHandler),
    (r"/favicon.ico", OtherHandler),
    (r"/styles/(pygments.css)", tornado.web.StaticFileHandler,
        dict(path=appsettings['static_path'])),
    (r"/styles/bootstrap/(.*css)", tornado.web.StaticFileHandler,
        dict(path=appsettings['static_path'] + '/twitter-bootstrap-1.3.0')),
    (r"/js/bootstrap/(.*)", tornado.web.StaticFileHandler,
        dict(path=appsettings['static_path'] + '/twitter-bootstrap-1.3.0/js')),
    (r"/js/(.*)", tornado.web.StaticFileHandler,
        dict(path=appsettings['static_path'])),
    (r"/history/(.*)", RepoHistoryHandler),
    (r"/([^/]*)/?(.*)", RepoHandler),
], debug=True, login_url="/login", cookie_secret=settings.SECURE_COOKIE_KEY)

# with the `debug=True` flag we get autoreloading - whenever a module is changed
# while the webserver is running, the whole thing is reloaded

if __name__ == "__main__":

    args = parser.parse_args()
    application.listen(5000)
    tornado.ioloop.IOLoop.instance().start()
