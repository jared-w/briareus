'''Manages interaction with a Git repository via a forge access,
either as Github or Gitlab.

There are various small differences between the API interactions of
github and gitlab.

Functionally, there are differences between a Github Pull Request
and a Gitlab Merge Request.

 * For a Github Pull request, the PR is an element fetched from the
   main (destination) repository, and the source is identified as a
   specific branch in a separate (forked) repo.

 * For a Gitlab Merge Request, the MR is an element fetched from the
   main (destination) repository, and the source is identified by
   explicit sha reference in a source_project_id, so there is no
   namespace collision concern.

      { "id": 339,
        "project_id": 413,
        "target_branch": "master",
        "source_branch": "master",
        "source_project_id": 414,
        "target_project_id": 413,
        "sha": "33865bc...b1fd8",
        "upvotes": 0,
        "downvotes": 0,
        "work_in_progress": false,
        ...
      }

 * The Gitlab Merge Request may specify either a "source_project_id"
   or a "source_url".

'''

import os
import logging
import hashlib
import subprocess
import requests
import json
import base64
import configparser
from urllib.parse import urlparse, urlunparse
from thespian.actors import *
from thespian.initmsgs import initializing_messages
from Briareus.VCS.InternalMessages import *
import datetime

LocalCachePeriod = datetime.timedelta(minutes=1, seconds=35)


def transient_idle(exit_delay=datetime.timedelta(seconds=20)):
    def _TrIdAc(actor_class):
        def rmsg(self, msg, sender):
            if not getattr(self, '_TIES', None):
                self.wakeupAfter(exit_delay)
                self._TIES = datetime.datetime.now() + exit_delay
            if isinstance(msg, WakeupMessage):
                if datetime.datetime.now() >= self._TIES:
                    self.send(self.myAddress, ActorExitRequest())
                else:
                    self.wakeupAfter(self._TIES - datetime.datetime.now())
            elif not isinstance(msg, ActorSystemMessage):
                self._TIES = datetime.datetime.now() + exit_delay
            return self._TIA_rmsg(msg, sender)
        actor_class._TIA_rmsg = actor_class.receiveMessage
        actor_class.receiveMessage = rmsg
        return actor_class
    return _TrIdAc


@initializing_messages([('repospec', RepoRemoteSpec)], init_passthru=True)
@transient_idle(datetime.timedelta(hours=12))
class GitRepoInfo(ActorTypeDispatcher):
    def __init__(self, *args, **kw):
        super(GitRepoInfo, self).__init__(*args, **kw)
        self._ghinfo = None
        self.repospec = RepoRemoteSpec(RepoAPI_Location("no-url", None))

    def receiveMsg_RepoRemoteSpec(self, msg, sender):
        self._ghinfo = (GitHubInfo(msg.repo_api_loc)
                        if 'github' in self.repospec.repo_api_loc.apiloc else
                        (GitLabInfo(msg.repo_api_loc)
                         if 'gitlab' in self.repospec.repo_api_loc.apiloc else
                         None))
        if not self._ghinfo:
            raise ValueError('Cannot determine type of remote repo at %s'
                             % self.repospec.repo_api_loc.apiloc)

    def receiveMsg_GetPullReqs(self, msg, sender):
        try:
            rsp = self._ghinfo.get_pullreqs(msg.reponame)
        except Exception as err:
            logging.critical('GetPullReqs err: %s', err, exc_info=True)
            self.send(msg.orig_sender,
                      InvalidRepo(msg.reponame, 'git', self.repospec.repo_api_loc.apiloc,
                                  getattr(self._ghinfo, '_url', str(self._ghinfo)),
                                  'GetPullReqs - ' + str(err)))
        else:
            self.send(msg.orig_sender, rsp)

    def receiveMsg_HasBranch(self, msg, sender):
        branch = msg.branch_name
        try:
            rsp = self._ghinfo.get_branches()
        except Exception as err:
            logging.critical('HasBranch: %s', err, exc_info=True)
            self.send(msg.orig_sender,
                      InvalidRepo(msg.reponame, 'git', self.repospec.repo_api_loc.apiloc,
                                  getattr(self._ghinfo, '_url', str(self._ghinfo)),
                                  'HasBranch - ' + str(err)))
        else:
            blist = [ b['name'] for b in rsp ]
            chk = branch in blist
            self.send(msg.orig_sender, BranchPresent(msg.reponame, branch, chk,
                                                     known_branches=blist))


    def receiveMsg_GitmodulesData(self, msg, sender):
        branch = msg.branch_name
        try:
            rval = self._ghinfo.get_gitmodules(msg.reponame, branch, msg.pullreq_id)
        except Exception as err:
            logging.critical('GitmodulesData err: %s', err, exc_info=True)
            self.send(msg.orig_sender,
                      InvalidRepo(msg.reponame, 'git', self.repospec.repo_api_loc.apiloc,
                                  getattr(self._ghinfo, '_url', str(self._ghinfo)),
                                  'GitmodulesData - ' + str(err)))
        else:
            self.send(msg.orig_sender, rval)


    def receiveMsg_ReadFileFromVCS(self, msg, sender):
        filepath = msg.file_path
        branch = msg.branch or "master"
        try:
            rval = self._ghinfo.get_file_contents_raw(filepath, branch)
        except Exception as err:
            logging.critical('ReadFileFromVCS err: %s', err, exc_info=True)
            if hasattr(err, 'response'):
                ecode = getattr(err.response, 'status_code', -1)
            else:
                ecode = getattr(err, 'errno', -2)
            self.send(msg.orig_sender, FileReadData(req=msg, error_code=ecode))
        else:
            self.send(msg.orig_sender, FileReadData(req=msg, file_data=rval))


    def receiveMsg_str(self, msg, sender):
        if msg == "status":
            self.send(sender, self._ghinfo.stats() if self._ghinfo else
                      { "url": str(self.repospec.repo_api_loc.apiloc) + " (never accessed)",
                      })


class RemoteGit__Info(object):
    """Common functionality for remote Git retrieval (Github or Gitlab)."""
    def __init__(self, api_url):
        self._url = api_url
        self._request_session = requests.Session()
        self._rsp_cache = {}
        self._rsp_fetched = {}
        self._get_count = 0
        self._req_count = 0
        self._refresh_count = 0

    NotFound = 404

    def stats(self):
        return { "url": self._url,
                 "rsp_cache_keys": list(self._rsp_cache.keys()),
                 "get_info_reqs": self._get_count,
                 "remote_reqs": self._req_count,
                 "remote_refreshes": self._refresh_count
                 # n.b. get_info_reqs - remote_reqs - len(rsp_cache_keys) = error or 404 responses
        }

    trailer = '.git'
    trailer_len = len(trailer)

    @staticmethod
    def repo_url(self, url):
        "Drops any additional path elements beyond the first two: owner and repo"
        parsed = urlparse(url)
        return urlunparse(
            parsed._replace(path = '/'.join(parsed.path.split('/')[:3]) ))

    def api_req(self, reqtype, notFoundOK=False, raw=False):
        self._get_count += 1
        if reqtype.startswith('//'):
            # Drop the owner/repo at the tail of the url
            parsed = urlparse(self._url)
            req_url = urlunparse(parsed._replace(path='/'.join(parsed.path.split('/')[:-2] + [reqtype])))
        else:
            req_url = self._url + reqtype
        return self._get_cached_links_pageable_url(req_url, notFoundOK=notFoundOK, raw=raw)

    def _get_cached_links_pageable_url(self, req_url, notFoundOK, raw):
        rsp = self._get_cached_url(req_url, notFoundOK=notFoundOK, raw=raw)
        if rsp == self.NotFound:
            return rsp
        if 'Link' not in rsp.headers or not rsp.links.get('next', None):
            return rsp.text if raw else rsp.json()
        # $ curl -v https://api.github.com/repos/matterhorn-chat/matterhorn/branches
        # ...
        # Link: <https://api.github.com/repositories/66096261/branches?page=2>; rel="next", \
        #       <https://api.github.com/repositories/66096261/branches?page=2>; rel="last"
        # ...
        #
        # [Line continuation added for readability]
        #
        # Used by both github and gitlab APIs.  Supported easily by
        # requests
        # https://2.python-requests.org/en/master/user/advanced/#link-headers
        nextrsp = self._get_cached_links_pageable_url(rsp.links['next']['url'],
                                                      notFoundOK=notFoundOK, raw=raw)
        if raw:
            return rsp.text + nextrsp
        if isinstance(nextrsp, dict):
            nextrsp.update(rsp.json())
            return nextrsp
        elif isinstance(nextrsp, list):
            return rsp.json() + nextrsp
        else:
            logging.error('Unable to join nextrsp type %s to this response type %s',
                          type(nextrsp), type(rsp.json()))

    def _get_cached_url(self, req_url, notFoundOK, raw):
        last_one = self._rsp_cache.get(req_url, None)
        if last_one:
            # If fetched within the local cache period, just re-use
            # the same response
            last = self._rsp_fetched.get(req_url, None)
            if last:
                if datetime.datetime.now() - last < LocalCachePeriod:
                    return self._rsp_cache[req_url]
        # If already fetched, pass the header tags to the server in
        # the request so that the server can respond with either a 304
        # "Not Modified" or the new data (the 304 does not count
        # against the server's rate limit).
        hdrs = {}
        if last_one and last_one != self.NotFound:
            if 'ETag' in last_one.headers:
                hdrs = { "If-None-Match": last_one.headers['ETag'] }
            elif last_one and 'Last-Modified' in last_one.headers:
                hdrs = { "If-Modified-Since": last_one.headers['Last-Modified'] }
        self._req_count += 1
        rsp = self._request_session.get(req_url, headers = hdrs)
        if rsp.status_code == 304:  # Not Modified
            self._refresh_count += 1
            rsp = self._rsp_cache[req_url]
            self._rsp_fetched[req_url] = datetime.datetime.now()
        elif rsp.status_code == 200:
            self._rsp_cache[req_url] = rsp
            self._rsp_fetched[req_url] = datetime.datetime.now()
        elif rsp.status_code == 404 and notFoundOK:
            self._rsp_cache[req_url] = self.NotFound
            self._rsp_fetched[req_url] = datetime.datetime.now()
            return self.NotFound
        else:
            rsp.raise_for_status()
        return rsp

    def get_file_contents_raw(self, target_filepath, branch):
        rsp = self._get_file_contents_info(target_filepath, branch)
        if rsp != self.NotFound:
            if rsp['encoding'] != 'base64':
                logging.error('Unknown encoding for %s, branch %s, repo %s: %s',
                              target_filepath, branch, self._url)
                return self.NotFound
            return base64.b64decode(rsp['content']).decode('utf-8')
        return rsp

    def get_gitmodules(self, reponame, branch, pullreq_id):
        rsp = self.get_file_contents_raw('.gitmodules', branch)
        if rsp == self.NotFound:
            return GitmodulesRepoVers(reponame, branch, pullreq_id, [])
        return self.parse_gitmodules_contents(reponame, branch, pullreq_id, rsp)

    def parse_gitmodules_contents(self, reponame, branch, pullreq_id, gitmodules_contents):
        gitmod_cfg = configparser.ConfigParser()
        gitmod_cfg.read_string(gitmodules_contents)
        ret = []
        for remote in gitmod_cfg.sections():
            # Note: if the URL of a repo moves, need a new name for the moved location?  Or choose not to track these changes?
            submod_info = self._get_file_contents_info(gitmod_cfg[remote]['path'], branch)
            if submod_info == self.NotFound:
                # Is the repo in .gitmodules valid?
                valid_repo = self.api_req('', notFoundOK=True)
                if valid_repo == self.NotFound:
                    logging.warning('Invalid URL for submodule %s, %s: using "%s"',
                                    remote, self._url, os.path.split(gitmod_cfg[remote]['path'])[-1])
                    # The submodule added to .gitmodules specified an
                    # invalid repository.  Have to assume the name is
                    # the last component of the path.
                    ret.append(SubRepoVers(os.path.split(gitmod_cfg[remote]['path'])[-1],
                                           'invalid_remote_repo',
                                           'unknownRemoteRefForPullReq'))
                else:
                    # The submodule was added to .gitmodules, but no
                    # actual version of the remote repo was committed, so
                    # no reference SHA can be known.  Instead, use a
                    # reference sha that is completely invalid, which
                    # should cause a build failure, as long as the remote
                    # URL itself seems to be valid.
                    logging.warning('in %s branch %s, there is no submodule commit for .gitmodule'
                                    ' path %s, url %s',
                                    self._url, branch,
                                    gitmod_cfg[remote]['path'],
                                    gitmod_cfg[remote]['url'])
                    # Generate an invalid revision that will cause this build to fail on fetch of source
                    ret.append(SubRepoVers(gitmod_cfg[remote]['path'].split('/')[-1],
                                           gitmod_cfg[remote]['url'],
                                           'unknownRemoteRefForPullReq'))
            else:
                ret.append(self._subrepo_version(remote, gitmod_cfg[remote], submod_info))
        return GitmodulesRepoVers(reponame, branch, pullreq_id, ret)

# ----------------------------------------------------------------------
#
# Gitlab access
#
# Examples:
#
# $ CURL="curl -H 'Content-type: application/json' -H 'Private-token: TOKVAL' -L -v"
# $ ${CURL} https://gitlab.mycompany.com/api/v4/groups
# $ ${CURL} https://gitlab.mycompany.com/api/v4/groups/239
# $ ${CURL} https://gitlab.mycompany.com/api/v4/projects
# $ ${CURL} https://gitlab.mycompany.com/api/v4/projects/32
#     look at _links in response for other options
# $ ${CURL} https://gitlab.mycompany.com/api/v4/projects/32/merge_requests


class GitLabInfo(RemoteGit__Info):
    """Retrieve information from gitlab via API with cacheing.  Note that
       this object does not maintain a "name" for the repo because
       several projects may share the same repo.
    """
    def __init__(self, repo_api_location):
        super(GitLabInfo, self).__init__(self.get_api_url(repo_api_location.apiloc))
        if repo_api_location.apitoken:
            self._request_session.headers.update({'Private-Token': repo_api_location.apitoken})

    def get_api_url(self, url):
        parsed = urlparse(url)
        return urlunparse(
            parsed._replace(path = 'api/v4/projects/' + parsed.path[1:].replace('/', '%2F')))


    def _src_repo_url(self, mergereq):
        if 'source_project_url' in mergereq:
            return mergereq['source_project_url']
        # It's a source_project_id, but since it's on this gitlab
        # forge, it's in this repo as a local branch.  The proper URL
        # is not known here, only the forge API url, so defer the
        # actual URL to the caller who does have that information.
        if mergereq.get('source_project_id', "no_spid") == mergereq.get('target_project_id', "no_tpid"):
            return "SameProject"
        rsp = self.api_req(mergereq.get('source_project_id', "no_spid"))
        return ("DifferentProject", rsp.name)

    def get_pullreqs(self, reponame):
        rsp = self.api_req('/merge_requests')
        # Gather {"upvotes": 0, "downvotes": 0, "approvals_before_merge": 0} for analysis phase
        # Use {"work_in_progress": true} to ignore the PR
        # Use {"merge_status": "can_be_merged"} for analysis phase?

        # n.b. GitLab pullreqs have an id and and iid.  The iid is the
        # one that is presented to the user on the Web page.

        preqs = [ PullReqInfo(str(pr["iid"]),   # for user reference
                              pullreq_title=pr["title"],    # for user reference
                              pullreq_srcurl=self._src_repo_url(pr),  # source repo URL
                              pullreq_branch=pr["source_branch"],          # source repo branch
                              pullreq_ref=pr["sha"],
                              pullreq_user=pr['author']['username'],
                              pullreq_email=self.get_user_email(pr['author']['id']),
                              pullreq_mergeref=None)
                  for pr in rsp if pr["state"] == "opened" and not pr["merged_at"] ]
        return PullReqsData(reponame, preqs)

    def get_user_email(self, userid):
        userinfo = self.api_req('//users/' + str(userid), notFoundOK=True)
        if userinfo == self.NotFound:
            return ''
        return userinfo['public_email']

    def get_branches(self):
        return self.api_req('/repository/branches')

    def _get_file_contents_info(self, target_filepath, branch):
        return self.api_req('/repository/files/' + target_filepath.replace('/', '%2F') + '?ref=' + branch)

    def get_file_contents_raw(self, target_filepath, branch):
        return self.api_req('/repository/files/' + target_filepath.replace('/', '%2F') + '/raw?ref=' + branch,
                            # Sometimes this cannot be accessed, and
                            # the higher levels handle this.  This
                            # will frequently happen when someone
                            # forks a Private repo where a PAT has
                            # been added for the Private repo but the
                            # user's fork doesn't propagate the PAT.
                            notFoundOK=True,
                            raw=True)

    def _subrepo_version(self, remote_name, remote_info, submod_info):
        return SubRepoVers(submod_info['file_name'],
                           remote_info['url'],
                           submod_info['blob_id'])


# ----------------------------------------------------------------------
#
# Github access


class GitHubInfo(RemoteGit__Info):
    """Retrieve information from github via API with cacheing.  Note that
       this object does not maintain a "name" for the repo because
       several projects may share the same repo.
    """
    def __init__(self, repo_api_location):
        super(GitHubInfo, self).__init__(self.get_api_url(repo_api_location.apiloc))
        if repo_api_location.apitoken:
            self._request_session.auth = requests.auth.HTTPBasicAuth(
                *tuple(repo_api_location.apitoken.split(':')))

    def get_api_url(self, url):
        """Converts a remote repository URL into a form that is useable for
           the Github API (https://developer.github.com/v3) to allow
           API-related requests.
        """
        parsed = urlparse(url)
        if parsed.netloc == 'github.com':
            return urlunparse(
                parsed._replace(netloc = 'api.github.com',
                                path = 'repos' + parsed.path))
        raise RuntimeError("No API URL parsing for: %s [ %s ]" % (url, str(parsed)))

    def get_pullreqs(self, reponame):
        rsp = self.api_req('/pulls')
        # May want to filter on ["state"] == "open"
        # May want to echo either ["number"] or ["title"]
        # ["base"]["ref"] is the fork point the pull req is related to (e.g. matterhorn "develop")  # constrains merge command, but not build config...
        # ["head"]["repo"]["url"] is the github repo url for the source repo of the PR
        # ["base"]["ref"] is the fork point the pull req is related to (e.g. matterhorn "develop")  # constrains merge command, but not build config...
        preqs = [ PullReqInfo(str(pr["number"]),   # for user reference
                              pullreq_title=pr["title"],    # for user reference
                              pullreq_srcurl=pr["head"]["repo"]["html_url"],  # source repo URL
                              pullreq_branch=pr["head"]["ref"],          # source repo branch
                              pullreq_ref=pr["head"]["sha"],         # for github, can also use branch ^
                              pullreq_user=pr["user"]["login"],
                              pullreq_email=self.get_user_email(pr["user"]["login"]),
                              pullreq_mergeref=pr["merge_commit_sha"])
                  for pr in rsp if pr["state"] == "open" and not pr["merged_at"] ]
        return PullReqsData(reponame, preqs)

    def get_user_email(self, username):
        userinfo = self.api_req('//user/' + username, notFoundOK=True)
        if userinfo == self.NotFound:
            return ''
        return userinfo['email'] or ''

    def get_branches(self):
        return self.api_req('/branches')

    def _get_file_contents_info(self, target_filepath, branch):
        return self.api_req('/contents/' + target_filepath + '?ref=' + branch, notFoundOK=True)

    def _subrepo_version(self, remote_name, remote_info, submod_info):
        if submod_info['type'] != 'submodule':
            logging.warning('Found %s at %s, but expected a submodule',
                            submod_info['type'], gitmod_cfg[remote]['path'])
            return None # ignore this submodule entry
        return SubRepoVers(submod_info['name'],
                           submod_info['submodule_git_url'],
                           submod_info['sha'])
