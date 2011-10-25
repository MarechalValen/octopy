import re
import svnbrowse
from subprocess import call, check_call, CalledProcessError

class Error(Exception):
    pass

class TagExists(Error):
    pass

class BadName(Error):
    pass

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
        
    
