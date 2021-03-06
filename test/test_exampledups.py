from Briareus.Types import (BldConfig, BldRepoRev, BldVariable,
                            PR_Grouped, PR_Solo, BranchReq, MainBranch,
                            ProjectSummary, StatusReport, VarFailure)
from git_exampledups import GitExample
import json
import pytest
from datetime import timedelta


# This test is similar to the small test_example2, except:
#
#  * There are PR's and requested branches with the same names.
#
#  * There are no submodules
#
# This test suite ensures that the PR's do not mask the requested
# branches, and vice-versa.  This test suite also validates operation
# without submodules.
#
# A Pull request or merge request comes from a separate repository and
# should therefore be treated as effectively a *different* branch than
# a local branch.  If a PR has the same name as a local branch in a
# specific repository, that should result in two separate build
# configurations.
#


input_spec = '''
{
  "Repos" : [ ("Repo1", "r1_url"),
              ("Repo2", "r2_url"),
              ("Repo3", "r3_url"),
            ]
, "Branches" : [ "master", "develop" ]
, "Variables" : {
      "ghcver" : [ "ghc865", "ghc881" ],
  }
, "Reporting" : {
      "logic": """
project_owner("Repo1", "george@_company.com").

project_owner("Repo3", "john@not_a_company.com").

enable(email, "fred@nocompany.com", notify(_, "Repo1", _)).
enable(email, "anne@nocompany.com", notify(main_submodules_broken, "Repo1", _)).
      """
  }
}
'''

gitactor = GitExample


@pytest.fixture(scope="module")
def example_hydra_jobsets(generated_hydra_builder_output):
    return generated_hydra_builder_output[0][None]

build_results = [
            { "name" : "develop.standard-ghc865",
              "nrtotal" : 4,
              "nrsucceeded": 3,
              "nrfailed": 0,
              "nrscheduled": 1,
              "haserrormsg": False,
            },
            { "name" : "develop.standard-ghc881",
              "nrtotal" : 4,
              "nrsucceeded": 3,
              "nrfailed": 1,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "master.standard-ghc865",
              "nrtotal" : 4,
              "nrsucceeded": 4,
              "nrfailed": 0,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "master.standard-ghc881",
              "nrtotal" : 4,
              "nrsucceeded": 3,
              "nrfailed": 1,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR1-master.standard-ghc865",
              "nrtotal" : 4,
              "nrsucceeded": 4,
              "nrfailed": 0,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR1-master.standard-ghc881",
              "nrtotal" : 4,
              "nrsucceeded": 3,
              "nrfailed": 1,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR2-master.standard-ghc865",
              "nrtotal" : 4,
              "nrsucceeded": 4,
              "nrfailed": 0,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR2-master.standard-ghc881",
              "nrtotal" : 4,
              "nrsucceeded": 3,
              "nrfailed": 1,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR-develop.standard-ghc865",
              "nrtotal" : 0,
              "nrsucceeded": 0,
              "nrfailed": 0,
              "nrscheduled": 0,
              "haserrormsg": True,
            },
            { "name" : "PR-develop.standard-ghc881",
              "nrtotal" : 4,
              "nrsucceeded": 3,
              "nrfailed": 1,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR-foo.standard-ghc865",
              "nrtotal" : 9,
              "nrsucceeded": 9,
              "nrfailed": 0,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR-foo.standard-ghc881",
              "nrtotal" : 4,
              "nrsucceeded": 3,
              "nrfailed": 1,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR9-master.standard-ghc865",
              "nrtotal" : 9,
              "nrsucceeded": 9,
              "nrfailed": 0,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR9-master.standard-ghc881",
              "nrtotal" : 4,
              "nrsucceeded": 3,
              "nrfailed": 1,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR-dog.standard-ghc865",
              "nrtotal" : 9,
              "nrsucceeded": 9,
              "nrfailed": 0,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
            { "name" : "PR-dog.standard-ghc881",
              "nrtotal" : 4,
              "nrsucceeded": 3,
              "nrfailed": 1,
              "nrscheduled": 0,
              "haserrormsg": False,
            },
        ]

prior = [
    StatusReport(status='initial_success', project='Repo1',
                 strategy='standard', branchtype="pullreq", branch="foo",
                 buildname='PR-foo.standard-ghc881',
                 bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc881')
                 ],
                 blddesc=PR_Grouped('foo'),
    ),
    StatusReport(status='initial_success', project='Repo1',
                 strategy='standard', branchtype="pullreq", branch="foo",
                 buildname='PR-foo.standard-ghc865',
                 bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc865')
                 ],
                 blddesc=PR_Grouped('foo'),
    ),
    StatusReport(status='failed', project='Repo1',
                 strategy='standard', branchtype="pullreq", branch="master",
                 buildname='PR1-master.standard-ghc865',
                 bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc865')
                 ],
                 blddesc=PR_Solo('master', '1'),
    ),
    StatusReport(status='succeeded', project='Repo1',
                 strategy='standard', branchtype="regular", branch="master",
                 buildname='master.standard-ghc881',
                 bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc881')
                 ],
                 blddesc=BranchReq('Repo1', 'master'),
    ),
]

@pytest.fixture(scope="module")
def example_hydra_results(generate_hydra_results):
    return generate_hydra_results(build_results=build_results, prior=prior)

analysis_time_budget = timedelta(seconds=1, milliseconds=500)  # avg 1.03s

GS = [ "ghc865", "ghc881" ]
top_level = [
    "regular develop standard",
    "regular master standard",
    "pullreq 1 R1 master",
    "pullreq 2 R1 master",
    "pullreq [2] R3 develop",
    "pullreq R3 foo",
    "pullreq R3 master",
    "pullreq [101 Req8] dog",
]

def test_example_facts(generated_facts):
    assert expected_facts == list(map(str, generated_facts))


expected_facts = sorted(filter(None, '''
:- discontiguous project/2.
:- discontiguous repo/2.
:- discontiguous subrepo/2.
:- discontiguous main_branch/2.
:- discontiguous submodule/5.
:- discontiguous branchreq/2.
:- discontiguous branch/2.
:- discontiguous pullreq/5.
:- discontiguous varname/2.
:- discontiguous varvalue/3.
project("Repo1", "Repo1").
default_main_branch("master").
repo("Repo1", "Repo1").
repo("Repo1", "Repo2").
repo("Repo1", "Repo3").
branchreq("Repo1", "master").
branchreq("Repo1", "develop").
pullreq("Repo1", "1", "master", "jdoe", "jdoe@nocompany.com").
pullreq("Repo1", "2", "master", "jdoe", "jdoe@nocompany.com").
pullreq("Repo3", "2", "develop", "frank", "frank@stein.co").
pullreq("Repo3", "1", "foo", "earl", "earl@king.wild").
pullreq("Repo3", "9", "master", "frank", "frank@stein.co").
pullreq("Repo1", "Req8", "dog", "r.user", "").
pullreq("Repo3", "101", "dog", "fido", "fido@woof.grr").
branch("Repo3", "develop").
branch("Repo1", "develop").
branch("Repo2", "master").
branch("Repo3", "master").
branch("Repo2", "develop").
branch("Repo1", "master").
branch("Repo2", "foo").
varname("Repo1", "ghcver").
varvalue("Repo1", "ghcver", "ghc865").
varvalue("Repo1", "ghcver", "ghc881").
'''.split('\n')))


def test_example_internal_count(generated_bldconfigs):
    assert len(GS) * len(top_level) == len(generated_bldconfigs.cfg_build_configs)


def test_example_internal_regular_master_standard(generated_bldconfigs):
    for each in [ BldConfig(projectname="Repo1",
                            branchtype="regular",
                            branchname="master",
                            strategy="standard",
                            description=BranchReq("Repo1", "master"),
                            blds=[BldRepoRev("Repo1", "master", "project_primary"),
                                  BldRepoRev("Repo2", "master", "project_primary"),
                                  BldRepoRev("Repo3", "master", "project_primary"),
                            ],
                            bldvars=[BldVariable("Repo1", "ghcver", G)])
                  for G in GS]:
        assert each in generated_bldconfigs.cfg_build_configs

def test_example_internal_regular_develop_standard(generated_bldconfigs):
    for each in [ BldConfig(projectname="Repo1",
                            branchtype="regular",
                            branchname="develop",
                            strategy="standard",
                            description=BranchReq("Repo1", "develop"),
                            blds=[BldRepoRev("Repo1", "develop", "project_primary"),
                                  BldRepoRev("Repo2", "develop", "project_primary"),
                                  BldRepoRev("Repo3", "develop", "project_primary"),
                            ],
                            bldvars=[BldVariable("Repo1", "ghcver", G)])
                  for G in GS]:
        assert each in generated_bldconfigs.cfg_build_configs

def test_example_internal_pr1_standard(generated_bldconfigs):
    for each in [ BldConfig(projectname="Repo1",
                            branchtype="pullreq",
                            branchname="master",
                            strategy="standard",
                            description=PR_Solo("Repo1", "1"),
                            blds=[BldRepoRev("Repo1", "master", "1"),
                                  BldRepoRev("Repo2", "master", "project_primary"),
                                  BldRepoRev("Repo3", "master", "project_primary"),
                            ],
                            bldvars=[BldVariable("Repo1", "ghcver", G)])
                  for G in GS]:
        assert each in generated_bldconfigs.cfg_build_configs

def test_example_internal_pr2r1_standard(generated_bldconfigs):
    for each in [ BldConfig(projectname="Repo1",
                            branchtype="pullreq",
                            branchname="master",
                            strategy="standard",
                            description=PR_Solo("Repo1", "2"),
                            blds=[BldRepoRev("Repo1", "master", "2"),
                                  BldRepoRev("Repo2", "master", "project_primary"),
                                  BldRepoRev("Repo3", "master", "project_primary"),
                            ],
                            bldvars=[BldVariable("Repo1", "ghcver", G)])
                  for G in GS]:
        assert each in generated_bldconfigs.cfg_build_configs

def test_example_internal_pr2r3_standard(generated_bldconfigs):
    for each in [ BldConfig(projectname="Repo1",
                            branchtype="pullreq",
                            branchname="develop",
                            strategy="standard",
                            description=PR_Grouped("develop"),
                            blds=[BldRepoRev("Repo1", "develop", "project_primary"),
                                  BldRepoRev("Repo2", "develop", "project_primary"),
                                  BldRepoRev("Repo3", "develop", "2"),
                            ],
                            bldvars=[BldVariable("Repo1", "ghcver", G)])
                  for G in GS]:
        assert each in generated_bldconfigs.cfg_build_configs

def test_example_internal_pr1r3_standard(generated_bldconfigs):
    for each in [ BldConfig(projectname="Repo1",
                            branchtype="pullreq",
                            branchname="foo",
                            strategy="standard",
                            description=PR_Grouped("foo"),
                            blds=[BldRepoRev("Repo1", "master", "project_primary"),
                                  BldRepoRev("Repo2", "foo", "project_primary"),
                                  BldRepoRev("Repo3", "foo", "1"),
                            ],
                            bldvars=[BldVariable("Repo1", "ghcver", G)])
                  for G in GS]:
        assert each in generated_bldconfigs.cfg_build_configs

def test_example_internal_pr9r3_standard(generated_bldconfigs):
    for each in generated_bldconfigs.cfg_build_configs:
        print(each)
        print('')
    for each in [ BldConfig(projectname="Repo1",
                            branchtype="pullreq",
                            branchname="master",
                            strategy="standard",
                            description=PR_Solo("Repo3", "9"),
                            blds=[BldRepoRev("Repo1", "master", "project_primary"),
                                  BldRepoRev("Repo2", "master", "project_primary"),
                                  BldRepoRev("Repo3", "master", "9"),
                            ],
                            bldvars=[BldVariable("Repo1", "ghcver", G)])
                  for G in GS]:
        assert each in generated_bldconfigs.cfg_build_configs

def test_example_internal_pr101r3_prReq8r1_standard(generated_bldconfigs):
    for each in [ BldConfig(projectname="Repo1",
                            branchtype="pullreq",
                            branchname="dog",
                            strategy="standard",
                            description=PR_Grouped("dog"),
                            blds=[BldRepoRev("Repo1", "dog", "Req8"),
                                  BldRepoRev("Repo2", "master", "project_primary"),
                                  BldRepoRev("Repo3", "dog", "101"),
                            ],
                            bldvars=[BldVariable("Repo1", "ghcver", G)])
                  for G in GS]:
        assert each in generated_bldconfigs.cfg_build_configs


def test_example_hydra_count(example_hydra_jobsets):
    print('##### OUTPUT:')
    print(example_hydra_jobsets)
    assert len(GS) * len(top_level) == len(json.loads(example_hydra_jobsets))

def test_example_hydra_master(example_hydra_jobsets):
    expected = dict([
        ( "master.standard-%s" % (G), {
            "checkinterval": 600,
            "description": "Build configuration: brr33:Repo1, brr33:Repo2, brr33:Repo3, ghcver=%s" % (G),
            "emailoverride": "",
            "enabled": 1,
            "enableemail": False,
            "hidden": False,
            "inputs": {
                "Repo1-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r1_url master"
                },
                "Repo2-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r2_url master"
                },
                "Repo3-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r3_url master"
                },
                "ghcver": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": G
                },
                "variant": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": "|branch=master|strategy=standard"
                },
            },
            "keepnr": 3,
            "nixexprinput": "Repo1-src",
            "nixexprpath": "./release.nix",
            "schedulingshares": 1
        }) for G in GS ])
    for each in expected:
        print(each)
        actual = json.loads(example_hydra_jobsets)
        assert each in actual
        assert expected[each] == actual[each]

def test_example_hydra_develop(example_hydra_jobsets):
    expected = dict([
        ( "develop.standard-%s" % (G), {
            "checkinterval": 600,
            "description": "Build configuration: brr33:Repo1, brr33:Repo2, brr33:Repo3, ghcver=%s" % (G),
            "emailoverride": "",
            "enabled": 1,
            "enableemail": False,
            "hidden": False,
            "inputs": {
                "Repo1-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r1_url develop"
                },
                "Repo2-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r2_url develop"
                },
                "Repo3-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r3_url develop"
                },
                "ghcver": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": G
                },
                "variant": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": "|branch=develop|strategy=standard"
                },
            },
            "keepnr": 3,
            "nixexprinput": "Repo1-src",
            "nixexprpath": "./release.nix",
            "schedulingshares": 1
        }) for G in GS ])
    for each in expected:
        print(each)
        actual = json.loads(example_hydra_jobsets)
        assert each in actual
        assert expected[each] == actual[each]

def test_example_hydra_R1PR1(example_hydra_jobsets):
    expected = dict([
        ( "PR1-master.standard-%s" % (G), {
            "checkinterval": 600,
            "description": "Build configuration: PR1-brr31:Repo1, brr33:Repo2, brr33:Repo3, ghcver=%s" % (G),
            "emailoverride": "",
            "enabled": 1,
            "enableemail": False,
            "hidden": False,
            "inputs": {
                "Repo1-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "remote_Repo1 master"
                },
                "Repo2-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r2_url master"
                },
                "Repo3-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r3_url master"
                },
                "ghcver": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": G
                },
                "variant": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": "|branch=master|strategy=standard|PR"
                },
            },
            "keepnr": 3,
            "nixexprinput": "Repo1-src",
            "nixexprpath": "./release.nix",
            "schedulingshares": 1
        }) for G in GS ])
    for each in expected:
        print(each)
        actual = json.loads(example_hydra_jobsets)
        assert each in actual
        assert expected[each] == actual[each]

def test_example_hydra_R1PR2(example_hydra_jobsets):
    expected = dict([
        ( "PR2-master.standard-%s" % (G), {
            "checkinterval": 600,
            "description": "Build configuration: PR2-brr31:Repo1, brr33:Repo2, brr33:Repo3, ghcver=%s" % (G),
            "emailoverride": "",
            "enabled": 1,
            "enableemail": False,
            "hidden": False,
            "inputs": {
                "Repo1-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "remote_Repo1_pr2 master"
                },
                "Repo2-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r2_url master"
                },
                "Repo3-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r3_url master"
                },
                "ghcver": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": G
                },
                "variant": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": "|branch=master|strategy=standard|PR"
                },
            },
            "keepnr": 3,
            "nixexprinput": "Repo1-src",
            "nixexprpath": "./release.nix",
            "schedulingshares": 1
        }) for G in GS ])
    for each in expected:
        print(each)
        actual = json.loads(example_hydra_jobsets)
        assert each in actual
        assert expected[each] == actual[each]

def test_example_hydra_R3PR1(example_hydra_jobsets):
    expected = dict([
        ( "PR-foo.standard-%s" % (G), {
            "checkinterval": 600,
            "description": "Build configuration: brr33:Repo1, brr30:Repo2, PR1-brr31:Repo3, ghcver=%s" % (G),
            "emailoverride": "",
            "enabled": 1,
            "enableemail": False,
            "hidden": False,
            "inputs": {
                "Repo1-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r1_url master"
                },
                "Repo2-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r2_url foo"
                },
                "Repo3-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "remote_Repo3_2 foo"
                },
                "ghcver": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": G
                },
                "variant": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": "|branch=foo|strategy=standard|PR"
                },
            },
            "keepnr": 3,
            "nixexprinput": "Repo1-src",
            "nixexprpath": "./release.nix",
            "schedulingshares": 1
        }) for G in GS ])
    for each in expected:
        print(each)
        actual = json.loads(example_hydra_jobsets)
        assert each in actual
        assert expected[each] == actual[each]

def test_example_hydra_R3PR2(example_hydra_jobsets):
    expected = dict([
        ( "PR-develop.standard-%s" % (G), {
            "checkinterval": 600,
            "description": "Build configuration: brr30:Repo1, brr30:Repo2, PR2-brr31:Repo3, ghcver=%s" % (G),
            "emailoverride": "",
            "enabled": 1,
            "enableemail": False,
            "hidden": False,
            "inputs": {
                "Repo1-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r1_url develop"
                },
                "Repo2-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r2_url develop"
                },
                "Repo3-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "remote_Repo3 develop"
                },
                "ghcver": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": G
                },
                "variant": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": "|branch=develop|strategy=standard|PR"
                },
            },
            "keepnr": 3,
            "nixexprinput": "Repo1-src",
            "nixexprpath": "./release.nix",
            "schedulingshares": 1
        }) for G in GS ])
    for each in expected:
        print(each)
        actual = json.loads(example_hydra_jobsets)
        assert each in actual
        assert expected[each] == actual[each]

def test_example_hydra_R3PR9(example_hydra_jobsets):
    expected = dict([
        ( "PR9-master.standard-%s" % (G), {
            "checkinterval": 600,
            "description": "Build configuration: brr33:Repo1, brr33:Repo2, PR9-brr31:Repo3, ghcver=%s" % (G),
            "emailoverride": "",
            "enabled": 1,
            "enableemail": False,
            "hidden": False,
            "inputs": {
                "Repo1-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r1_url master"
                },
                "Repo2-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r2_url master"
                },
                "Repo3-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "remote_repo3_other master"
                },
                "ghcver": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": G
                },
                "variant": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": "|branch=master|strategy=standard|PR"
                },
            },
            "keepnr": 3,
            "nixexprinput": "Repo1-src",
            "nixexprpath": "./release.nix",
            "schedulingshares": 1
        }) for G in GS ])
    for each in expected:
        print(each)
        actual = json.loads(example_hydra_jobsets)
        assert each in actual
        assert expected[each] == actual[each]

def test_example_hydra_R3PR101_R1_PRReq8(example_hydra_jobsets):
    expected = dict([
        ( "PR-dog.standard-%s" % (G), {
            "checkinterval": 600,
            "description": "Build configuration: PRReq8-brr31:Repo1, brr33:Repo2, PR101-brr31:Repo3, ghcver=%s" % (G),
            "emailoverride": "",
            "enabled": 1,
            "enableemail": False,
            "hidden": False,
            "inputs": {
                "Repo1-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "Repo1_Remote8 dog"
                },
                "Repo2-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "r2_url master"
                },
                "Repo3-src": {
                    "emailresponsible": False,
                    "type": "git",
                    "value": "Repo3_r3 dog"
                },
                "ghcver": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": G
                },
                "variant": {
                    "emailresponsible": False,
                    "type": "string",
                    "value": "|branch=dog|strategy=standard|PR"
                },
            },
            "keepnr": 3,
            "nixexprinput": "Repo1-src",
            "nixexprpath": "./release.nix",
            "schedulingshares": 1
        }) for G in GS ])
    for each in expected:
        print(each)
        actual = json.loads(example_hydra_jobsets)
        assert each in actual
        assert expected[each] == actual[each]



def test_example_report_summary(example_hydra_results):
    bldcfgs, reps = example_hydra_results

    for each in reps:
        print('')
        print(each)

    assert ProjectSummary(project_name='Repo1',
                          bldcfg_count=16, subrepo_count=0, pullreq_count=7) in reps

# def test_example_report_status1(example_hydra_results):
#     bldcfgs, reps = example_hydra_results
#     # This one has a bad configuration
#     assert StatusReport(status='failed', project='Repo1',
#                         strategy='standard', branchtype="pullreq", branch="develop",
#                         buildname='PR-develop.standard-ghc865',
#                         bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc865')
#                         ],
#                         blddesc=PR_Grouped('dev')) in reps

def test_example_report_status2(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    assert StatusReport(status=1, project='Repo1',
                        strategy='standard', branchtype="pullreq", branch="develop",
                        buildname='PR-develop.standard-ghc881',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc881')
                        ],
                        blddesc=PR_Grouped('develop')) in reps

def test_example_report_status3(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    assert StatusReport(status=1, project='Repo1',
                        strategy='standard', branchtype="pullreq", branch="foo",
                        buildname='PR-foo.standard-ghc881',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc881')
                        ],
                        blddesc=PR_Grouped('foo')) in reps

def test_example_report_status4(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    assert StatusReport(status=1, project='Repo1',
                        strategy='standard', branchtype="pullreq", branch="master",
                        buildname='PR1-master.standard-ghc881',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc881')
                        ],
                        blddesc=PR_Solo('Repo1', '1')) in reps

def test_example_report_status4_2(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    assert StatusReport(status=1, project='Repo1',
                        strategy='standard', branchtype="pullreq", branch="master",
                        buildname='PR2-master.standard-ghc881',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc881')
                        ],
                        blddesc=PR_Solo('Repo1', '2')) in reps

def test_example_report_status5(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    assert StatusReport(status=1, project='Repo1',
                        strategy='standard', branchtype="regular", branch="develop",
                        buildname='develop.standard-ghc881',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc881')
                        ],
                        blddesc=BranchReq('Repo1', 'develop')) in reps

def test_example_report_status6(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    assert StatusReport(status=1, project='Repo1',
                        strategy='standard', branchtype="regular", branch="master",
                        buildname='master.standard-ghc881',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc881')
                        ],
                        blddesc=BranchReq('Repo1', 'master')) in reps

def test_example_report_status7(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    assert StatusReport(status='initial_success', project='Repo1',
                        strategy='standard', branchtype="pullreq", branch="master",
                        buildname='PR9-master.standard-ghc865',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc865')
                        ],
                        blddesc=PR_Solo('Repo3', '9')) in reps

def test_example_report_status8(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    assert StatusReport(status='initial_success', project='Repo1',
                        strategy='standard', branchtype="regular", branch="master",
                        buildname='master.standard-ghc865',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc865')
                        ],
                        blddesc=BranchReq('Repo1', 'master')) in reps

def test_example_report_status9(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    assert StatusReport(status='succeeded', project='Repo1',
                        strategy='standard', branchtype="pullreq", branch="foo",
                        buildname='PR-foo.standard-ghc865',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc865')
                        ],
                        blddesc=PR_Grouped('foo')) in reps

# def test_example_report_status10(example_hydra_results):
#     bldcfgs, reps = example_hydra_results
#     # This one is in-progress
#     assert StatusReport(status='succeeded', project='Repo1',
#                         strategy='standard', branchtype="regular", branch="develop",
#                         buildname='develop.standard-ghc865',
#                         bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc865')
#                         ], blddesc=TBD) in reps

def test_example_report_status11(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    for each in reps:
        print(each)
        print('')
    assert StatusReport(status='initial_success', project='Repo1',
                        strategy='standard', branchtype="pullreq", branch="dog",
                        buildname='PR-dog.standard-ghc865',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc865')
                        ],
                        blddesc=PR_Grouped('dog')) in reps

def test_example_report_status10(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    for each in reps:
        print(each)
        print('')
    assert StatusReport(status=1, project='Repo1',
                        strategy='standard', branchtype="pullreq", branch="dog",
                        buildname='PR-dog.standard-ghc881',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc881')
                        ],
                        blddesc=PR_Grouped('dog')) in reps

def test_example_report_status12(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    for each in reps:
        print(each)
        print('')
    assert StatusReport(status='bad_config', project='Repo1',
                        strategy='standard', branchtype="pullreq", branch="develop",
                        buildname='PR-develop.standard-ghc865',
                        bldvars=[BldVariable(project='Repo1', varname='ghcver', varvalue='ghc865')
                        ],
                        blddesc=PR_Grouped('develop')) in reps


def test_example_report_varfailure(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    assert VarFailure('Repo1', 'ghcver', 'ghc881') in reps

def test_example_report_length(example_hydra_results):
    bldcfgs, reps = example_hydra_results
    prfails  = 6
    prstatus = 6 # develop, dog, foo, 1, 2, 9
    num_varfailure = 1
    num_notify = num_varfailure + prfails + 1 # main good
    num_actions = num_notify
    expected = ((len(top_level) * len(GS)) +   # 8 * 2
                len(['ProjectSummary', ])
                + prstatus
                + (num_varfailure * 2)  # VarFailure + SepHandledVar
                + num_notify + num_actions
    )
    for each in reps:
        print(each)
        print('')
    assert expected == len(reps)
