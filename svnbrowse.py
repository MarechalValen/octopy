
from os.path import basename, dirname
from subprocess import call, check_call
from tempfile import TemporaryFile
from xml.etree.ElementTree import ElementTree

from pygments import highlight
from pygments.lexers import guess_lexer, get_lexer_for_filename, TextLexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

def list_repositories(repos):
    """Returns a list of all the available repositories as a label and path
    expects repos to be an iterable of svn urls 
    """
    for repourl in repos:
        repo = {}
        with TemporaryFile() as tmp:
            call(['svn', 'info', repourl], stdout=tmp)

            tmp.seek(0)
            for line in tmp:
                line = line.strip()
                if not line: 
                    continue
                key = line.split(':')[0].replace(' ', '_').lower()
                value = ':'.join(line.split(':')[1:]).strip()
                repo[key] = value

        repo['name'] = basename(repo['url'])
        repo['weburl'] = repo['name'] + '/' + repo['url'].replace(repo['repository_root'], '')
        yield repo

def list_repository(repourl, path, rev=None, recursive=False):
    """Returns a listing of the repository, every folder and file"""

    name = basename(repourl.strip("/"))
    url = repourl + "/" + path
    cmd = ['svn', 'list', '--xml', url]
    if rev:
        cmd.extend(['-r', str(rev)])
    if recursive:
        cmd.extend(['-R'])

    with TemporaryFile() as tmp:
        call(cmd, stdout=tmp)
        tmp.seek(0)
        tree = ElementTree()
        tree.parse(tmp)

    for entry in tree.iter('entry'):
        commit = entry.find('commit')
        webpath = "/" + name
        if path != "":
           webpath += "/" + path
        webpath += "/" + entry.find('name').text
        data = { 'kind': entry.attrib['kind'],
            'name': entry.find('name').text,
            'revision': commit.attrib['revision'],
            'author': commit.find('author').text,
            'date': commit.find('date').text,
            'webpath': webpath}
        try:
            data['size'] = entry.find('size').text
        except AttributeError:
            data['size'] = None

        yield data


def list_changesets(repourl, revfrom, revto):
    """Returns the parsed changeset"""

    revfrom, revto = int(revfrom), int(revto)

    cmd = ['svn', 'diff', '--xml', '--summarize', 
        '-r', '%d:%d' % (revfrom, revto), repourl]
    with TemporaryFile() as tmp:
        check_call(cmd, stdout=tmp)
        tmp.seek(0)
        tree = ElementTree()
        tree.parse(tmp)

    for path in tree.iter('path'):
        data = { 'props': path.attrib['props'],
            'kind': path.attrib['kind'],
            'item': path.attrib['item'],
            'path': path.text}
        yield data

    # and svn diff 

def highlight_file(repourl):
    with TemporaryFile() as tmp:
        check_call(['svn', 'cat', repourl], stdout=tmp)
        tmp.seek(0)
        try:
            return highlight(tmp.read(), 
                get_lexer_for_filename(basename(repourl)),
                HtmlFormatter()) 
        except ClassNotFound, e:
            tmp.seek(0)
            return highlight(tmp.read(), 
                TextLexer(), HtmlFormatter()) 
    
