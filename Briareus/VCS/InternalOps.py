# Internal functionality for managing VCS Repo interactions.

from thespian.actors import *
from thespian.initmsgs import initializing_messages
from Briareus.Input.Description import RepoDesc
from Briareus.VCS.InternalMessages import *
from Briareus.VCS.GitRepo import GitRepoInfo
from urllib.parse import urlparse, urlunparse
from collections import defaultdict
import attr
import logging
import os


class GatherRepoInfo(ActorTypeDispatcher):
    "Main Actor for obtaining information from VCS repositories."

    def __init__(self, *args, **kw):
        super(GatherRepoInfo, self).__init__(*args, **kw)
        self._get_git_info = None
        self.top_requestor = None
        self._stats = {}
        self.responses_pending = 0
        self.pending_requests = []

    def receiveMsg_str(self, msg, sender):
        if msg == "status":
            self.send(sender, self._stats)
        elif msg == 'Deactivate' and self._get_git_info:
            # From the Director via the TLI file; offer our cached
            # information to our successor.
            successor = self.createActor("Briareus.VCS.InternalOps.GatherRepoInfo",
                                         globalName='GatherRepoInfo')
            self.send(successor, 'HaveCachedInfo')
        elif msg == 'HaveCachedInfo':
            if sender != self.myAddress:
                # Ask sender for their cached info...
                logging.critical('Get cached repo info from %s', sender)
            pass
        elif msg == 'Start':
            # Sent by Thespian Director based on the TLI file; this is
            # intended only to ensure this Actor is instantiated.
            pass
        else:
            objmsg = fromJSON(msg)
            self._dispatch(objmsg, sender, jsonReply=True)

    def _dispatch(self, objmsg, sender, jsonReply=False):
        if isinstance(objmsg, GatherInfo):
            self._gatherInfo(objmsg, sender, jsonReply=jsonReply)
        elif isinstance(objmsg, ReadFileFromVCS):
            self.read_vcs_file(objmsg, sender, jsonReply=jsonReply)
        else:
            logging.warning('No handling for objmsg [%s]: %s', type(objmsg), msg)


    def _incr_stat(self, stat_name):
        self._stats[stat_name] = self._stats.get(stat_name, 0) + 1

    def get_git_info(self, reqmsg):
        if not self._get_git_info:
            # n.b. use a globalName for GetGitInfo because tests will
            # override the GetGitInfo instance below with a mocked
            # version appropriate to that test.
            self._get_git_info = self.createActor(GetGitInfo, globalName="GetGitInfo")
        self.responses_pending += 1
        self._incr_stat("get_git")
        self.send(self._get_git_info, reqmsg)


    def respond_to_requestor(self, response_msg):
        if self.top_requestor:
            self.send(self.top_requestor, response_msg)
            self.top_requestor = None
        if self.pending_requests:
            self._dispatch(*self.pending_requests.pop(0))

    def is_idle(self, newmsg, msg_sender, jsonReply):
        if self.top_requestor is None:
            return True
        self.pending_requests.append( (newmsg, msg_sender, jsonReply) )
        return False

    def got_response(self, got_a_response=True, response_name='unk'):
        self._incr_stat(response_name)
        if got_a_response and self.responses_pending:
            self.responses_pending -= 1
        if self.responses_pending == 0:
            self.respond_to_requestor(
                self.prepareReply(
                    GatheredInfo({ "pullreqs" : self.pullreqs,
                                   "submodules": self.submodules,
                                   "subrepos" : self.subrepos,
                                   "branches" : self.branches
                    })))

    def receiveMsg_ChildActorExited(self, msg, sender):
        if msg.childAddress == self._get_git_info:
            self._get_git_info = None
            self.respond_to_requestor(self.prepareReply(GatheredInfo(None, 'GitInfo actor exited')))

    def receiveMsg_InvalidRepo(self, msg, sender):
        self.respond_to_requestor(
            self.prepareReply(
                GatheredInfo(None, 'Invalid %s repo "%s", remote %s (@ %s): %s' %
                             (msg.repo_type,
                              msg.reponame,
                              msg.repo_remote,
                              msg.repo_api_url,
                              msg.errorstr))))

    def receiveMsg_ReadFileFromVCS(self, msg, sender):
        """Main entrypoint to read a specific file from a repo at the
           specified URL
        """
        self.read_vcs_file(msg, sender)

    def read_vcs_file(self, readfile_msg, sender, jsonReply=False):
        if not self.is_idle(readfile_msg, sender, jsonReply):
            return
        self.top_requestor = sender
        self.prepareReply = toJSON if jsonReply else (lambda x: x)
        self.get_git_info(Repo_AltLoc_ReqMsg(to_http_url(readfile_msg.repourl,
                                                         readfile_msg.repolocs),
                                             readfile_msg))

    def receiveMsg_FileReadData(self, msg, sender):
        self.respond_to_requestor(self.prepareReply(msg))

    def receiveMsg_GatherInfo(self, msg, sender):
        """Main entrypoint to gather information for the list of repos and
           branches provided in the input GatherInfo message, sending
           the information back in the GatheredInfo response message.

           Uses sub-actors to get information, and recursively adds
           new requests as new repositories, branches, and pull
           requests are discovered during the information gathering.

        """
        self._gatherInfo(msg, sender)

    def _gatherInfo(self, msg, sender, jsonReply=False):
        if not self.is_idle(msg, sender, jsonReply):
            return
        self.top_requestor = sender
        self.prepareReply = toJSON if jsonReply else (lambda x: x)
        self.responses_pending = 0

        self.pullreqs = set()
        self.submodules = set()
        self.subrepos = set()
        self.branches = set()
        self.known_branches = defaultdict(set)
        self.branches_check = {}
        self._pending_info = {}

        self.RL = msg.repolist
        self.RX = msg.repolocs
        self.BL = msg.branchlist
        self.BL_queried = []
        for repo in self.RL:
            self.get_info_for_a_repo(repo)
        # In case there were no repos, this is the "I am done" check:
        self.got_response(False)

    def get_info_for_a_repo(self, repo):
        self.get_git_info(DeclareRepo(repo.repo_name, repo.repo_url, self.RX))
        self._pending_info[repo.repo_name] = repo

    def _all_repos(self): return set(self.RL).union(set(self.subrepos))

    def receiveMsg_RepoDeclared(self, msg, sender):
        "Response message from the GetGitInfo actor to a DeclareRepo message"
        repo = self._pending_info.get(msg.reponame, None)
        if repo:
            del self._pending_info[msg.reponame]
            self.get_git_info(HasBranch(repo.repo_name, repo.main_branch))
            self.get_git_info(GetPullReqs(repo.repo_name))
        self.got_response(response_name='repo_declared')

    def receiveMsg_PullReqsData(self, msg, sender):
        "Response message from the GetGitInfo actor to a GetPullReqs message"
        # A pull request references a branch in a (possibly different)
        # repo where that branch exists; the branch may not exist in
        # the current repo (it does for gitlab, it does not for
        # github).
        #
        # For github, there is also a "pullreq_mergeref",
        # which is a specific sha for a test merge commit for that
        # repo; this is not used here because it is only available for
        # automatic merges and represents a step not yet taken for the
        # workflow.
        #
        # Note that this branch may not exist on the main repo; if it
        # does, it's considered to be different than the pull request,
        # so don't compare it to a local branch (i.e. build both if
        # specified).  By extension, there can be multiple PR's for
        # the same branch name from two separate source repositories:
        # again, these are distinct.
        #
        # For compatibility with this PR, other repos might have a
        # branch or a PR with the same name (or both!).  Note that the
        # latter supercedes the former, and the latter is already
        # handled by the pullreqs retrievals, so just check for
        # branches.

        for p in msg.pullreqs:

            # First, determine the source repo URL for the pullreq.
            # Sometimes this is known, but sometimes the reference
            # must be translated (e.g. GitLab sometimes just provides
            # 'source_project_id').
            if p.pullreq_srcurl == "SameProject":
                # This is likely a GitLab repo, where the merge
                # request has a source_project_id instead of a
                # source_project_url, and the source_project_id is the
                # same as the target_project_id, (it's just a branch
                # in the original repo).  The GitLabInfo information
                # collection didn't have the URL, so it couldn't
                # generate an actual URL.
                p.pullreq_srcurl = [ r.repo_url
                                     for r in self.RL if r.repo_name == msg.reponame ][0]  # must match
            elif isinstance(p.pullreq_srcurl, tuple) and \
                 p.pullreq_srcurl[0] == 'DifferentProject':
                # This is likely a GitLab repo, where the merge
                # request has a source_project_id instead of a
                # source_rpoject_url and the source_project_id is
                # different than the target_project_id.  The
                # GitLabInfo information collection didn't have the
                # URL, so it couldn't generate an actual URL.
                src_reponame = p.pullreq_srcurl[1]
                p.pullreq_srcurl = ([ r.repo_url
                                      for r in self.RL if r.repo_name == src_reponame ]
                                    + [None])[0]
            elif p.pullreq_srcurl is None:
                # Debug vvv Hypothesis: this occurs during the small
                # window where the pull request was identified and
                # then it is merged and then additional data is
                # attempted to be collected for it.
                #
                # Alternative (verified): gitlab is kinda broken
                # because a private fork of a private repo doesn't
                # inherit the permissions from the original repo and
                # therefore is not visible to users that can access
                # the original repo.  This manifests in 404 when
                # attempting to follow the link to the merge source,
                # and from the API perspective it causes the
                # pullreq_srcurl to be None.  Since not much
                # information can be gathered about these PR's they
                # are ignored.
                logging.critical('ERR: srcurl is None for pullreq %s in msg %s', p, msg)
                # Debug ^^^

            # If this is a new pull request branch, and that branch
            # has not already been probed for the target repo, check
            # to see if the branch exists (and if it is confirmed to
            # exist and it's the project repo, also get any submodule
            # data on that branch).
            for pr in self.pullreqs:
                if p.pullreq_branch == pr.pr_branch:
                    break
            else:
                # Have not previously queried for this branch, so
                # check various repos for this branch now.
                for repo in self._all_repos():
                    self.check_for_branch(repo.repo_name, p.pullreq_branch)

            # If this PR is for the project repo, check the gitmodules
            # in the source because the PR might be changing the
            # gitmodule list/references.
            for repo in self.RL:
                if repo.project_repo and repo.repo_name == msg.reponame:
                    # Get submodules information because the pr is
                    # on the project repo and might have changed
                    # the submodules configuration.  Note that the
                    # gitmodules file should be retrieved with the
                    # pullreq_ref (the commit sha) if possible
                    # because Gitlab only supports file reading
                    # via ref, not via branchname.
                    if p.pullreq_srcurl and p.pullreq_srcurl != repo.repo_url:
                        # Source for pull request is in a different repo
                        self.get_git_info(
                            Repo_AltLoc_ReqMsg(to_http_url(p.pullreq_srcurl, self.RX),
                                               GitmodulesData(repo.repo_name,
                                                              p.pullreq_branch,
                                                              p.pullreq_number,
                                                              p.pullreq_ref or
                                                              p.pullreq_branch)))
                    else:
                        # Source for pull request is in this repo
                        self.get_git_info(GitmodulesData(repo.repo_name,
                                                         p.pullreq_branch,
                                                         p.pullreq_number,
                                                         p.pullreq_ref or
                                                         p.pullreq_branch))

        self.pullreqs.update(set([
            PRInfo(pr_target_repo=msg.reponame,
                   pr_srcrepo_url=(to_access_url(p.pullreq_srcurl,
                                                 ([r for r in self.RL
                                                   if r.repo_name == msg.reponame] + [None])[0],
                                                 self.RX) or
                                   self._url_for_repo(msg.reponame)),
                   pr_branch=p.pullreq_branch,
                   pr_ident=str(p.pullreq_number),  # PR idents must be strings
                   pr_title=p.pullreq_title,
                   pr_user=p.pullreq_user,
                   pr_email=p.pullreq_email)
            for p in msg.pullreqs
            if p.pullreq_srcurl is not None]))
        self.got_response(response_name='pull_reqs_data')

    def _url_for_repo(self, repo_name):
        for each in self._all_repos():
            if each.repo_name == repo_name:
                return each.repo_url
        raise ValueError('Repo not known by name (for url): ' % repo_name)

    def check_for_branch(self, repo_name, branch_name):
        self._incr_stat('chk_for_branch')
        if self.branches_check.get((repo_name, branch_name), False):
            # This branch has a pending request already
            return
        if self._branch_checked(repo_name, branch_name):
            # This branch status is already known
            return
        if self._branch_checked_shared_repo(repo_name, branch_name):
            # This branch status is already known from a repo sharing the same location
            return
        self._incr_stat('chk_for_branch_missed')
        self.branches_check[(repo_name, branch_name)] = True
        self.get_git_info(HasBranch(repo_name, branch_name))

    def _branch_checked(self, repo_name, branch_name):
        curbr = (repo_name, branch_name)
        for br in self.branches:
            if curbr == br:
                return True
        if repo_name in self.known_branches and self.known_branches[repo_name]:
            # Have known_branches for this repo, so presumably *all*
            # branches for this repo are known without needing to
            # issue a query.
            for br in self.known_branches[repo_name]:
                if branch_name == br:
                    self.branches.add(curbr)
            return True
        return False

    def _branch_checked_shared_repo(self, repo_name, branch_name):
        # Some repos have different names but are essentially
        # different subdirs in the same actual repo, so the branch is
        # valid there as well.
        tgt_repos = [r for r in self.RL if r.repo_name == repo_name]
        if len(tgt_repos) != 1:
            tgt_repos = [r for r in self.subrepos if r.repo_name == repo_name]
            if len(tgt_repos) != 1:
                return False
        tgt_repo = tgt_repos[0]
        for r in self._all_repos():
            if r.repo_url == tgt_repo.repo_url and r.repo_name != tgt_repo.repo_name:
                if self._branch_checked(r.repo_name, branch_name):
                    return True
        return False


    def receiveMsg_BranchPresent(self, msg, sender):
        "Response message from the GetGitInfo actor to a HasBranch message"
        if msg.branch_present:
            self.branches_check[(msg.reponame, msg.branch_name)] = False  # no longer pending
            self.branches.add( (msg.reponame, msg.branch_name) )
            for repo in self.RL:
                if repo.project_repo and repo.repo_name == msg.reponame:
                    # This is a branch on the project repo, so see if
                    # there is any submodule information on that
                    # branch.
                    self.get_git_info(GitmodulesData(repo.repo_name, msg.branch_name,
                                                     None, # Branches are never queried in PR source repos
                                                     None))
        main_r = ([ r for r in self._all_repos() if r.repo_name == msg.reponame ] +
                  [ None ])[0]
        for br in msg.known_branches:
            self.known_branches[msg.reponame].add(br)
            if main_r:
                # Set branches any other projects sharing this repo
                for each in self._all_repos():
                    if each.repo_url == main_r.repo_url and each.repo_name != main_r.repo_name:
                        self.known_branches[each.repo_name].add(br)

        if msg.reponame not in self.BL_queried:
            self.BL_queried.append(msg.reponame)
            for branch in self.BL:
                self.get_git_info(HasBranch(msg.reponame, branch.branch_name))

        self.got_response(response_name='branch_present')


    def receiveMsg_GitmodulesRepoVers(self, msg, sender):
        "Response message from the GetGitInfo actor to a GitmodulesData message"
        for each in msg.gitmodules_repovers:
            named_submod_repo = ([r for r in self._all_repos()
                                  if r.repo_name == each.subrepo_name] + [None])[0]
            if not named_submod_repo:
                # TBD: currently assumes a subrepo URL doesn't change
                # across project repo branches, but this could happen.
                # If that's the case, need to associate this project
                # repo branch with the corresponding changed subrepo
                # url.
                named_submod_repo = RepoDesc(each.subrepo_name, each.subrepo_url)
                self.get_info_for_a_repo(named_submod_repo)
            self.subrepos.add(named_submod_repo)
            # Add the submodule specification for this submodule repo
            # and any other modules that share the same repo
            nsr_url = to_http_url(named_submod_repo.repo_url, self.RX).apiloc
            for r in self._all_repos():
                if r.repo_url == nsr_url or r.repo_url == named_submod_repo.repo_url:
                    self.submodules.add( SubModuleInfo(sm_repo_name=msg.reponame,
                                                       sm_branch=msg.branch_name,
                                                       sm_pullreq_id=msg.pullreq_id,
                                                       sm_sub_name=r.repo_name,
                                                       sm_sub_vers=each.subrepo_vers) )
            # Now check for PR-driven branches in those subrepos
            for pr in self.pullreqs:
                # For any pull requests that have already been fetched:
                # check to see if there is a corresponding branch in
                # this subrepo
                self.check_for_branch(msg.reponame, pr.pr_branch)
        self.got_response(response_name='gitmodules_repo_vers')


class GetGitInfo(ActorTypeDispatcher):
    def __init__(self, *args, **kw):
        super(GetGitInfo, self).__init__(*args, **kw)
        self.gitinfo_actors = {}
        self.gitinfo_actors_by_url = {}

    def _get_subactor(self, reponame, repourl=None, repolocs=None):
        suba = self.gitinfo_actors.get(reponame, None)
        if not suba:
            if not repourl:
                raise RuntimeError('No URL for defined repo %s' % reponame)  # KWQ: make a message

            # Optimization: sometimes different modules
            # share a repo (they are different subdirectories).  In
            # this case, the queries are at the repo level, so there's
            # no need to query multiple times.  If there is already an
            # entry for this repo URL, just re-use it.
            if repourl in self.gitinfo_actors_by_url:
                self.gitinfo_actors[reponame] = self.gitinfo_actors_by_url[repourl]
                return self.gitinfo_actors[reponame]

            suba = self.createActor(GitRepoInfo)
            self.gitinfo_actors[reponame] = suba
            self.gitinfo_actors_by_url[repourl] = suba
            apiloc = to_http_url(repourl, repolocs or [])
            self.send(suba, RepoRemoteSpec(apiloc))
        return suba

    def receiveMsg_ActorExitRequest(self, msg, sender):
        for each in self.gitinfo_actors.values():
            self.send(each, msg)

    def receiveMsg_ChildActorExited(self, msg, sender):
        for each in [ k
                      for k in self.gitinfo_actors
                      if self.gitinfo_actors[k] == msg.childAddress ]:
            del self.gitinfo_actors[each]
        for each in [ k
                      for k in self.gitinfo_actors_by_url
                      if self.gitinfo_actors_by_url[k] == msg.childAddress ]:
            del self.gitinfo_actors_by_url[each]

    def receiveMsg_DeclareRepo(self, msg, sender):
        suba = self._get_subactor(msg.reponame, msg.repo_url, msg.repolocs)
        self.send(sender, RepoDeclared(msg.reponame))

    def receiveMsg_Repo__ReqMsg(self, msg, sender):
        suba = self._get_subactor(msg.reponame)
        msg.orig_sender = sender
        self.send(suba, msg)

    def receiveMsg_Repo_AltLoc_ReqMsg(self, msg, sender):
        """Send a message to an alternate repo URL; the repo URL must already
           have been normalized and translated (by to_http_url).
        """
        loc = msg.api_repo_loc.apiloc
        suba = self.gitinfo_actors_by_url.get(loc, None)
        if not suba:
            suba = self.createActor(GitRepoInfo)
            self.gitinfo_actors_by_url[loc] = suba
            # No self.gitinfo_actors entry: all primary requests are
            # routed by reponame to the main GitRepoInfo actor; this
            # is just for alternate locations (e.g. source of
            # pullreqs)
            self.send(suba, RepoRemoteSpec(msg.api_repo_loc))
        msg.altloc_reqmsg.orig_sender = sender
        self.send(suba, msg.altloc_reqmsg)

    def receiveMsg_str(self, msg, sender):
        if msg == "status":
            self.send(sender, self.gitinfo_actors)


# ----------------------------------------------------------------------
# Support functions

def _remove_trailer(path, trailer):
    trailer_len = len(trailer)
    return path[:-trailer_len] if path[-trailer_len:] == trailer else path

def _changeloc(url, repolocs):
    parsed = urlparse(url)
    for each in repolocs:
        if parsed.netloc == each.repo_loc:
            return urlunparse(parsed._replace(netloc=each.api_host)), each.api_host, parsed.netloc
    return url, parsed.netloc, parsed.netloc

def to_http_url(url, repolocs):
    """Converts git clone access specification
    (e.g. "git@foo.com:group/proj") to the corresponding HTTP forge
    reference RepoAPI_URL (e.g. "https://foo.com/group/proj").  Also
    works if the source ends with ".git".

    Performs any network location translations specified in the xlate
    list (which has (from, to) pairs in it as commonly specified by
    the RepoLoc input specification.

    Returns the translated URL along with any access token for that
    URL (as extracted from the BRIAREUS_PAT environment variable).

    """
    if url.startswith("git@"):
        trimmed_url = _remove_trailer(url[len('git@'):], '.git')
        spl = trimmed_url.split(':')
        return to_http_url('https://%s/%s' % (spl[0], ':'.join(spl[1:])), repolocs)

    returl, for_remote, orig_remote_spec = _changeloc(_remove_trailer(url, '.git'), repolocs)

    patspec = os.getenv('BRIAREUS_PAT')
    if patspec is None:
        return RepoAPI_Location(returl, None)
    # The BRIAREUS_PAT format: "remote=PATSPEC;...", where PATSPEC
    # varies by the type of forge.  For Github, the PATSPEC is
    # "user:token".  For Gitlab, the PATSPEC is simply "token".
    patlist = patspec.split(';')

    # First try finding a PAT using the original target specification,
    # in case there is a specific PAT associated with a specific
    # remote.
    for pat in patlist:
        if pat.startswith(orig_remote_spec + '='):
            patval = pat[len(for_remote)+1:]
            return RepoAPI_Location(returl, patval)

    # Now try with the target remote to get a general translation
    for pat in patlist:
        if pat.startswith(for_remote + '='):
            patval = pat[len(for_remote)+1:]
            return RepoAPI_Location(returl, patval)

    return RepoAPI_Location(returl, None)

def to_access_url(url, for_repo, repolocs): # KWQ: use for_repo to get "git@" portion instead of https portion...
    """The Repo specification in the input may use a git ssh reference to
       a repo (e.g. "git@myproj-github:foo/bar") which indicates that
       an SSH deploy key is being used by the Builder (e.g. Hydra) to
       access the repository.

       This function should be called with any URL that the builder
       might use to access a version of that repository (e.g. a pull
       request or merge request reference, or a submodule), and it
       will translate the URL *back* into the form that the builder
       will need to use to access that repository.  If no translation
       is needed, the input URL is returned untouched.

    """
    if not for_repo:
        # URL is not for a primary input repo.  It is probably a
        # subrepo.  Because it is not a primary, there is no
        # translation information available.
        return url

    if not for_repo.repo_url.startswith('git@'):
        # Primary input repo doesn't use SSH access, so presumably
        # repo is publicly accessible and the URL will work
        return url

    # The for_repo specification indicates that SSH access is needed,
    # so extract the hostname so that the same hostname can be used in
    # the input URL to ensure the same Builder's .ssh/config entry is
    # used.

    trimmed_url = _remove_trailer(for_repo.repo_url[len('git@'):], '.git')
    ssh_host = trimmed_url.split(':')[0]

    # The input URL can be in http form or already in ssh form.
    if url.startswith("git@"):
        url_path = _remove_trailer(url[len('git@'):], '.git').split(':')[1]
    else:
        parsed = urlparse(url)
        # n.b. assumes there are no params, query, or fragment
        # portions of a git http URL.  Remove the initial slash on the
        # path part as well.
        url_path = parsed.path[1:]

    return "git@" + ssh_host + ":" + url_path
