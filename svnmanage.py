import logging
import re
import svnbrowse
from subprocess import call, check_call, CalledProcessError
from tempfile import TemporaryFile, NamedTemporaryFile

class Error(Exception):
    pass

class TagExists(Error):
    pass

class BranchExists(Error):
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
    #logging.info("username is %s" % username)
    limbs = svnbrowse.get_branches(repourl)
    if branchname in limbs:
        raise BranchExists("""'%s' is already a branch, please try using a 
            different branch name""" % branchname)
    elif re.sub('[\w\.-]', '', branchname) != '':
        raise BadName("""'%s' is an invalid name. Try using just letters, numbers,
            dashes, underscores and periods.""" % branchname)
    reponame = svnbrowse.get_root_info(repourl)['repository_root'].split('/')[-1]
    with TemporaryFile() as tmperr:
        with TemporaryFile() as tmpout:
            out = call(['svn', 'copy', '%s/trunk' % repourl, 
                '%s/branches/%s' % (repourl, branchname), '-m', 'Creating a new branch named %s' % branchname],
                stderr=tmperr, stdout=tmpout)

            if out is not 0:
                tmperr.seek(0)
                msg = tmperr.read()
                logging.error(msg)
                raise Error(msg)

            tmpout.seek(0)
            rev = re.search('Committed revision (\d+)', tmpout.read()).groups()[0]
            logging.info("changing the author of %s r%s to %s" % (reponame, rev, username))
            with NamedTemporaryFile() as tmpauthor:
                #logging.debug("tmperr %r, tmpout %r, tmpauthor %r" % (tmperr, tmpout, tmpauthor))
                tmpauthor.write(username)
                tmpauthor.seek(0)
                out = call(['svnadmin', 'setrevprop', '/usr/local/svn/repositories/%s' % reponame, '-r', rev, 'svn:author', tmpauthor.name])
                if out is not 0:
                    raise Error("Failed to set the commit author")

    return True
    
    
def create_tag(repourl, tagname, username):
    tags = svnbrowse.get_tags(repourl)
    if tagname in tags:
        raise TagExists("""'%s' is already tagged, please try using a 
            different tag name""" % tagname)
    elif re.sub('[\w\.-]', '', tagname) != '':
        raise BadName("""'%s' is an invalid name. Try using just letters, numbers,
            dashes, underscores and periods.""" % tagname)
    reponame = svnbrowse.get_root_info(repourl)['repository_root'].split('/')[-1]
    #logging.debug("reponame %s" % (reponame,))
    with TemporaryFile() as tmperr:
        with TemporaryFile() as tmpout: 
            out = call(['svn', 'copy', '%s/trunk' % repourl, 
                '%s/tags/%s' % (repourl, tagname), '-m', 'Tagging the %s release' % tagname],
                stderr=tmperr, stdout=tmpout)

            if out is not 0:
                tmperr.seek(0)
                msg = tmperr.read()
                logging.error(msg)
                raise Error(msg)
            
            tmpout.seek(0)
            rev = re.search('Committed revision (\d+)', tmpout.read()).groups()[0]
            logging.info("changing the author of %s r%s to %s" % (reponame, rev, username))
            with NamedTemporaryFile() as tmpauthor:
                #logging.debug("tmperr %r, tmpout %r, tmpauthor %r" % (tmperr, tmpout, tmpauthor))
                tmpauthor.write(username)
                tmpauthor.seek(0)
                out = call(['svnadmin', 'setrevprop', '/usr/local/svn/repositories/%s' % reponame, '-r', rev, 'svn:author', tmpauthor.name])
                if out is not 0:
                    raise Error("Failed to set the commit author")

    return True
    
