
import re
from datetime import datetime
from os.path import basename, dirname
from subprocess import call, check_call, CalledProcessError
from tempfile import TemporaryFile
from xml.etree.ElementTree import ElementTree

from pygments import highlight
from pygments.lexers import guess_lexer, get_lexer_for_filename, TextLexer, DiffLexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

DEFAULT_DATE_FMT = "%x %I:%M:%S %p"

class NoTagDirectoryInRepo(Exception):
    pass

class LogParser(object):
    def __init__(self, logoutput):
        self.log = logoutput
    def __iter__(self):
        tree = ElementTree()
        tree.parse(self.log)
        iterator = getattr(tree, 'iter', getattr(tree, 'getiterator'))
        for entry in iterator('logentry'):
            data = {}
            data['revision'] = entry.attrib['revision']
            try:
                data['author'] = entry.find('author').text
            except AttributeError:
                data['author'] = ''
            data['date'] = datetime.strptime(entry.find('date').text[0:19], 
                "%Y-%m-%dT%H:%M:%S").strftime(DEFAULT_DATE_FMT)
            data['orig_date'] = entry.find('date').text
            data['message'] = entry.find('msg').text
            data['paths'] = []
            for path in entry.find('paths').findall('path'):
                data['paths'].append({'path': path.text,
                    'kind': path.attrib['kind'],
                    'action': path.attrib['action']})
            yield data

class ListParser(object):
    def __init__(self, logoutput):
        self.log = logoutput
    def __iter__(self):
        tree = ElementTree()
        tree.parse(self.log)
        iterator = getattr(tree, 'iter', getattr(tree, 'getiterator'))
        for entry in iterator('entry'):
            root = entry.find('repository').find('root').text
            data = { 'kind': entry.attrib['kind'],
                'name': entry.attrib['path'], 
                'fullpath': entry.find('url').text.replace(root, '') }
            commit = entry.find('commit')
            data['revision'] = commit.attrib['revision']
            data['orig_date'] = commit.find('date').text[0:19]
            data['date'] = datetime.strptime(data['orig_date'], 
                    "%Y-%m-%dT%H:%M:%S").strftime(DEFAULT_DATE_FMT)            
            try:
                data['author'] = commit.find('author').text
            except AttributeError:
                data['author'] = ''
            yield data
        
        #logex = re.compile('\s*(\d+)\s(\w+)\s*(\d+)?\s*(\w+\s\d+\s\d+:\d+)\s(.*)')
        #for line in self.log:
        #    rev, author, size, date, path = logex.match(line).groups()
        #    data = { 'kind': 'dir' if path[-1] == '/' else 'file',
        #        'size': size, 'name': '.' if path == './' else basename(path) , 
        #        'revision': rev, 'author': author or '', 
        #        'date': datetime.strptime(date, 
        #            "%b %d %H:%M").strftime(DEFAULT_DATE_FMT),
        #        'orig_date': date, 'webpath': ''}
        #    yield data

def list_repositories(repos):
    """Returns a list of all the available repositories as a label and path
    expects repos to be an iterable of svn urls 
    """
    for repourl in repos:
        yield get_root_info(repo)

def get_root_info(repourl):
    """Returns a list of all the available repositories as a label and path
    expects repos to be an iterable of svn urls 
    """
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
    repo['orig_last_changed_date'] = repo['last_changed_date']
    repo['last_changed_date'] = datetime.strptime(
        repo['last_changed_date'][:19], "%Y-%m-%d %H:%M:%S").strftime(DEFAULT_DATE_FMT)
    
    try:
        repo['most_recent_change'] = list_history(repo['url'], repo['last_changed_rev'])[0]
    except IndexError:
        repo['most_recent_change'] = {}

    return repo

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

    for entry in getattr(tree, 'iter', getattr(tree, 'getiterator'))('entry'):
        commit = entry.find('commit')
        webpath = "/" + name
        if path != "":
            webpath += "/" + path
        webpath += "/" + entry.find('name').text
        data = { 'kind': entry.attrib['kind'],
            'name': entry.find('name').text,
            'revision': commit.attrib['revision'],
            'author': getattr(commit.find('author'), 'text', ''),
            'date': datetime.strptime(commit.find('date').text[:19], 
                "%Y-%m-%dT%H:%M:%S").strftime(DEFAULT_DATE_FMT),
            'orig_date': commit.find('date').text,
            'webpath': webpath}
        try:
            data['size'] = entry.find('size').text
        except AttributeError:
            data['size'] = None

        yield data
    
    
def list_repository2(repourl, path, rev=None, recursive=False):
    """Returns a listing of the repository, every folder and file"""

    name = basename(repourl.strip("/"))
    url = repourl + "/" + path
    #cmd = ['svn', 'list', '-v', url]
    cmd = ['svn', 'info', '--xml', '--depth', 'immediates', url]
    if rev:
        cmd.extend(['-r', str(rev)])
    if recursive:
        cmd.extend(['-R'])

    with TemporaryFile() as tmp:
        call(cmd, stdout=tmp)
        tmp.seek(0)
        parser = ListParser(tmp)
        return list(parser)

def list_history(repourl, revision=None):
    """returns the parsed history of the repository"""
    cmd = ['svn', 'log', '--xml', '-v', repourl]
    if revision is not None and int(revision):
        cmd.extend(['-r', revision])
    with TemporaryFile() as tmp:
        check_call(cmd, stdout=tmp)
        tmp.seek(0)
        parser = LogParser(tmp)
        return list(parser) 

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

    for path in getattr(tree, 'iter', getattr(tree, 'getiterator'))('path'):
        data = { 'props': path.attrib['props'],
            'kind': path.attrib['kind'],
            'item': path.attrib['item'],
            'path': path.text}
        yield data

def list_diff(repourl, from_path, from_rev, to_path, to_rev):

    cmd = ['svn', 'diff',
            '%s/%s@%s' % (repourl, from_path, from_rev),
            '%s/%s@%s' % (repourl, to_path, to_rev) ]

    print ' '.join(cmd)
    with TemporaryFile() as tmp:
        check_call(cmd, stdout=tmp)
        tmp.seek(0)
        return tmp.read()

def highlight_file(repourl):
    with TemporaryFile() as tmp:
        check_call(['svn', 'cat', repourl], stdout=tmp)
        tmp.seek(0)
        try:
            return highlight(tmp.read(), 
                get_lexer_for_filename(basename(repourl)),
                HtmlFormatter(linenos=True)) 
        except ClassNotFound, e:
            tmp.seek(0)
            return highlight(tmp.read(), 
                TextLexer(), HtmlFormatter(linenos=True)) 
    
def highlight_diff(diff):
    return highlight(diff, DiffLexer(), HtmlFormatter())

def get_tags(repourl):
    cmd = ['svn', 'list', '%s/tags' % repourl]
    try:
        with TemporaryFile() as tmp:
            check_call(cmd, stdout=tmp)
            tmp.seek(0)
            return [i.strip().strip("/") for i in tmp.readlines()]
    except CalledProcessError:
        raise NoTagDirectoryInRepo("The repository %s does not have a 'tags' directory" % repourl)

def get_branches(repourl):
    cmd = ['svn', 'list', '%s/branches' % repourl]
    try:
        with TemporaryFile() as tmp:
            check_call(cmd, stdout=tmp)
            tmp.seek(0)
            return [i.strip().strip("/") for i in tmp.readlines()]
    except CalledProcessError:
        raise NoBranchDirectoryInRepo("The repository %s does not have a 'branches' directory" % repourl)

