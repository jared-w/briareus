# Definitions for a Nix Hydra builder

import Briareus.BuildSys.BuilderBase as BuilderBase
from Briareus.Types import BuilderResult, PR_Solo
from Briareus.BuildSys import buildcfg_name
import requests
import json
import os


class HydraBuilder(BuilderBase.Builder):
    """Generates Hydra jobset output for each build configuration.  The
       jobset specifies each BldRepoRev as a separate input to the
       jobset (with the suffix "-src").

       The builder_conf file should be a JSON file specifying any
       overrides for jobset fields (and the inputs section will be
       supplemental to (and override similar inputs) in the
       build-config-generated inputs.

          { "jobset" : {
                ... jobset overrides ...,
                "inputs": {
                    ... additional inputs/overrides ...
                }
            }
          }
    """

    builder_type = 'hydra'

    def output_build_configurations(self, input_desc, bldcfgs, repo_info, bldcfg_fname=None):
        """Given an input description and the set of build configurations
           generated from the BCGen logic, return the Hydra-specific
           configuration of those build configurations, along with any
           auxiliary files as a dictionary, where the key is the
           filename and the value is the contents; the key should be
           None for the primary output file, which is named in the
           input specification.

           For the Hydra builder, an auxiliary file is generated that
           can be used as the declarative project description (used
           for defining the Project in Hydra), along with a helper
           function to move that auxiliary file into the nix store on
           Hydra invocation.

           input_desc :: is the Briareus.Input.Description.InpDesc
                         object describing the repos, the branches,
                         and the variables.

           repo_info :: is the probed information from the VCS as
                        returned by
                        Briareus.Input.Operations.input_desc_and_VCS_info.

           bldcfgs :: is the set of bldcfgs generated by the BCGen logic.

           bldcfg_fname :: is the filepath where the output build
                            configurations will be written.  This
                            routine does *not* write to that file, but
                            it uses the filepath in the output of
                            auxiliary files, like the project
                            configuration file.  If this argument is
                            None, then the project declarative
                            description and corresponding installation
                            nix file are not generated.

        """
        input_cfg = (json.loads(open(self._conf_file, 'r').read())
                     if self._conf_file else {})
        project_name = input_cfg.get('project_name', 'unnamed')
        out_bldcfg_json = json.dumps(
            # Sort by key output stability
            { buildcfg_name(each, input_desc, repo_info) :
              self._jobset(input_desc, bldcfgs, input_cfg, each)
              for each in bldcfgs.cfg_build_configs },
            sort_keys=True)
        if not bldcfg_fname:
            return {None: out_bldcfg_json }
        copy_hh_src_path = os.path.abspath(
            os.path.join(os.path.dirname(bldcfg_fname), 'hydra'))
        return {
            None: out_bldcfg_json,
            (project_name + '-hydra-project-config.json') :
            json.dumps(
                { 'checkinterval': 300,
                  'keepnr': 3,
                  'schedulingshares': 1,
                  'emailoverride': '',
                  'description': "Briareus-generated %s Project declaration" % project_name,
                  'nixexprinput': "copy_hh_src",
                  'nixexprpath': "copy_hh.nix",
                  'enabled': 1,
                  'hidden': False,
                  'enableemail': True,
                  'inputs': {
                      'hh_output': {
                          'type': "path",
                          'value': os.path.abspath(bldcfg_fname),
                          'emailresponsible': False,
                          },
                      'copy_hh_src': {
                          'type': 'path',
                          'value': copy_hh_src_path,
                          'emailresponsible': False,
                      },
                      'nixpkgs': {
                          'type': "git",
                          'value': "https://github.com/NixOS/nixpkgs-channels nixos-unstable",
                          'emailresponsible': False,
                      },
                  },
                }),
            os.path.join(copy_hh_src_path, 'copy_hh.nix') :
            '\n'.join([
                '{ nixpkgs, hh_output }:',
                'let pkgs = import <nixpkgs> {}; in',
                '{ jobsets = pkgs.stdenv.mkDerivation {',
                '    name = "copy_hh";',
                '    phases = [ "installPhase" ];',
                '    installPhase = "cp ${hh_output} $out";',
                '  };',
                '}',
                '',
                ]),
        }

    def _jobset(self, input_desc, bldcfgs, input_cfg, bldcfg):
        jobset_inputs = self._jobset_inputs(input_desc, bldcfgs, bldcfg)
        if 'jobset' in input_cfg and 'inputs' in input_cfg['jobset']:
            jobset_inputs.update(input_cfg['jobset']['inputs'])
        projrepo = [ r for r in input_desc.RL if r.project_repo ][0]
        jobset = {
            # These are the defaults which can be overridden by
            # input_cfg which was the passed in builder_config file.
            "checkinterval": 600,  # 5 minutes
            "description": self._jobset_desc(bldcfgs, bldcfg),
            "emailoverride": "",
            "enabled": 1,
            "enableemail": False,
            "hidden": False,
            "keepnr": 3,  # number of builds to keep
            "nixexprinput": projrepo.repo_name + "-src",  # must be an input
            "nixexprpath": "./release.nix",  # the hydra convention
            "schedulingshares": 1,
            }
        jobset.update(input_cfg.get('jobset', {}))
        jobset['inputs'] = jobset_inputs
        return jobset

    def _jobset_variant(self, bldcfg):
        # Provides a string "variant" input to the jobset to allow the
        # jobset to customize itself (e.g. selecting different
        # dependencies for a branch v.s. the master).  Provide various
        # jobset information in a regular fashion to allow easy
        # interpretation by the nix jobset expression:
        #
        #   "|key=value|key=value..."
        #
        # Variables do not need to be part of the variant because they
        # are already independently specified.
        #
        # Similarly, BldRepoRev translates into independent inputs.
        return '|' + '|'.join(
            filter(None,
                   [ 'branch=' + bldcfg.branchname,
                     'strategy=' + bldcfg.strategy,
                     'PR' if bldcfg.branchtype == "pullreq" else None,
                   ]))

    def _pullreq_for_bldcfg_and_brr(self, bldcfgs, bldcfg, brr):
        return (([ p for p in bldcfgs.cfg_pullreqs  # InternalOps.PRInfo
                   if p.pr_target_repo == brr.reponame and
                      p.pr_branch == bldcfg.branchname and
                      p.pr_ident == brr.pullreq_id
                 ] + [None])[0]
                if bldcfg.branchtype == 'pullreq' and brr.pullreq_id != 'project_primary' else None)

    def _jobset_desc(self, bldcfgs, bldcfg):
        brr_info = []
        for brr in sorted(bldcfg.blds):  # BuildConfigs.BuildRepoRev
            preq = self._pullreq_for_bldcfg_and_brr(bldcfgs, bldcfg, brr)
            if preq:
                brr_info.append( "PR%(pr_ident)s-brr%%(srcident)s:%%(reponame)s"
                                 % preq.__dict__ % brr.__dict__ )
                continue
            brr_info.append( "brr%(srcident)s:%(reponame)s" % brr.__dict__ )

        return ("Build configuration: " +
                ", ".join(brr_info +
                          [ "%(varname)s=%(varvalue)s" % v.__dict__
                            for v in sorted(bldcfg.bldvars) ]
                ))

    def _jobset_inputs(self, input_desc, bldcfgs, bldcfg):
        repo_url_maybe_pullreq = lambda brr, mbpr: \
            (mbpr.pr_srcrepo_url
             if mbpr else
             self._repo_url(input_desc, bldcfgs, brr))
        repo_url = lambda brr: \
            repo_url_maybe_pullreq(brr,
                                   self._pullreq_for_bldcfg_and_brr(bldcfgs,
                                                                    bldcfg,
                                                                    brr))
        return dict(
            [ ('variant',
               {
                   'emailresponsible': False,
                   'type': 'string',
                   'value': self._jobset_variant(bldcfg)
               }),
            ] +
            [ (each.reponame + "-src",
               {
                   "emailresponsible": False,
                   "type": "git",
                   "value": ' '.join([repo_url(each), each.repover,])
               }) for each in bldcfg.blds ] +
            [ (v.varname, {
                "emailresponsible": False,
                "type": "string",
                "value": v.varvalue
            }) for v in bldcfg.bldvars ]
        )

    def _repo_url(self, input_desc, bldcfgs, bldreporev):
        for each in input_desc.RL:
            if each.repo_name == bldreporev.reponame:
                return each.repo_url
        for each in bldcfgs.cfg_subrepos:  # RepoDesc
            if each.repo_name == bldreporev.reponame:
                return each.repo_url
        return '--<unknown URL for repo %s>--' % bldreporev.reponame

    def update(self, cfg_spec):
        print("Takes output of output_build_configurations and updates the actual remote builder")

    def _get_build_results(self):
        r = getattr(self, '_build_results', None)
        if not r:
            if not self._builder_url:
                return 'Build results cannot be retrieved without a builder URL'
            if not self._conf_file:
                return 'Build results cannot be retrieved without builder configuration information.'
            input_cfg = json.loads(open(self._conf_file, 'r').read())
            project_name = input_cfg.get('project_name', None)
            if not project_name:
                return 'Build results require a project_name for querying Hydra'
            url = self._builder_url + "/api/jobsets?project=" + project_name
            r = requests.get(url)
            if r.status_code == 404:
                return 'No build results at specified target (%s)' % url
            r.raise_for_status()
            self._build_results = r.json()
        return self._build_results


    def get_build_result(self, bldcfg, inp_desc, repo_info):
        n = buildcfg_name(bldcfg, inp_desc, repo_info)
        r = self._get_build_results()
        if isinstance(r, str):
            return r
        return ([
            BuilderResult(
                buildname=n,
                nrtotal=get_or_show(e, 'nrtotal'),
                nrsucceeded=get_or_show(e, 'nrsucceeded'),
                nrfailed=get_or_show(e, 'nrfailed'),
                nrscheduled=get_or_show(e, 'nrscheduled'),
                cfgerror=get_or_show(e, 'haserrormsg') or bool(get_or_show(e, "fetcherrormsg")),
            )
            for e in r if e['name'] == n
        ] + ['No results available for jobset ' + n])[0]

def get_or_show(obj, fieldname):
    if fieldname not in obj:
        print('Missing field "%s" in builder result: %s'
              % ( fieldname, str(obj) ))
    return obj.get(fieldname)
