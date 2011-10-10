#! env/bin/python

import argparse
import os
import svnbrowse
import glob
import tornado.ioloop
import tornado.web
import webbrowser
from pprint import pprint

SVNDIR = "/usr/local/svn/repositories"

parser = argparse.ArgumentParser(description="""Starts up a webserver on port 5000
    serving all the local svn repositories""")
parser.add_argument("-d", type=str, default=SVNDIR, 
    dest="svndir", help="sets the svn repository directory (defaults to %s)" % SVNDIR)

class OtherHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("")

class RepoHandler(tornado.web.RequestHandler):
    def get(self, name, path=""):
        breadcrumbs = [name]
        parts = path.strip("/").split("/")
        if len(parts) > 0:
            breadcrumbs.extend(parts)
        url = "file:///usr/local/svn/repositories/" + name 
        files = list(svnbrowse.list_repository(url, path))
        if len(files) == 1 and files[0]['kind'] == 'file':
            pprint(files, stream=self)
            self.render("templates/repofile.html",
                file=files[0], source=svnbrowse.highlight_file(url + "/" + path),
                breadcrumbs=breadcrumbs[:-1], activecrumb=breadcrumbs[-1])
        else:
            self.render("templates/repodir.html",
                repo={"name": name}, files=files,
                breadcrumbs=breadcrumbs[:-1], activecrumb=breadcrumbs[-1])

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        repos = ('file://%s' % i for i in glob.glob(SVNDIR + '/*'))
        self.render("templates/repolist.html", 
            repos=svnbrowse.list_repositories(repos))

settings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
}

application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/favicon.ico", OtherHandler),
    (r"/styles/(pygments.css)", tornado.web.StaticFileHandler,
        dict(path=settings['static_path'])),
    (r"/([^/]*)/?(.*)", RepoHandler),
])

if __name__ == "__main__":

    args = parser.parse_args()

    # TODO verify svndir

    application.listen(5000)
    webbrowser.open("http://localhost:5000")
    tornado.ioloop.IOLoop.instance().start()
