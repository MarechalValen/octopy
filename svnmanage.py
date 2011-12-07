import logging
import re
import svnbrowse
from subprocess import call, check_call, CalledProcessError
from tempfile import TemporaryFile

class Error(Exception):
    pass

class TagExists(Error):
    pass

class BadName(Error):
    pass

def create_repo(name, username):
    with TemporaryFile() as tmp:
        #check_call(['createrepo', '-u', username, name])
        out = call(['createrepo', name], stderr=tmp)
        if out is not 0:
            tmp.seek(0)
            msg = tmp.read()
            logging.error(msg)
            raise Error(msg)
        return True

def create_branch(repourl, branchname, username):
    pass
    
def create_tag(repourl, tagname, username):
    tags = svnbrowse.get_tags(repourl)
    if tagname in tags:
        raise TagExists("""'%s' is already tagged, please try using a 
            different tag name""" % tagname)
    elif re.sub('[\w\.-]', '', tagname) != '':
        raise BadName("""'%s' is an invalid name. Try using just letters, numbers,
            dashes, underscores and periods.""" % tagname)

    #try:
    check_call(['svn', 'copy', '%s/trunk' % repourl, 
            '%s/tags/%s' % (repourl, tagname), '-m', 
            'Tagging the %s release' % tagname])
    return True
    #except CalledProcessError, e:
        
    
