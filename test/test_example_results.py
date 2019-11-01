import Briareus.AnaRep.Operations as AnaRep
import Briareus.BCGen.Operations as BCGen
from Briareus.Types import (BldConfig, BldRepoRev, BldVariable,
                            ProjectSummary, StatusReport, VarFailure)
import Briareus.Input.Operations as BInput
import Briareus.BCGen.Generator as Generator
import Briareus.BuildSys.Hydra as BldSys
from thespian.actors import *
from git_example1 import GitExample1
import json
import pytest
from test_example import input_spec


@pytest.fixture(scope="module")
def example_hydra_results():
    asys = ActorSystem('simpleSystemBase', transientUnique=True)
    try:
        # Generate canned info instead of actually doing git operations
        asys.createActor(GitExample1, globalName="GetGitInfo")
        inp_desc, repo_info = BInput.input_desc_and_VCS_info(input_spec,
                                                             actor_system=asys,
                                                             verbose=True)
        builder = BldSys.HydraBuilder(None)
        bcgen = BCGen.BCGen(builder, actor_system=asys, verbose=True)
        config_results = bcgen.generate(inp_desc, repo_info)
        builder_cfgs, build_cfgs = config_results
        anarep = AnaRep.AnaRep(builder, verbose=True, actor_system=asys)
        # n.b. the name values for build_results come from
        # builder._jobset_name, which is revealed by this print loop.
        for each in build_cfgs.cfg_build_configs:
            print(builder._jobset_name(each))
        builder._build_results = [
            { "name": n,
              "nrtotal" : 10,
              "nrsucceeded": 8 if '-clang-' in n else 10,
              "nrfailed": 2 if '-clang-' in n else 0,
              "nrscheduled": 0,
              "haserrormsg": False,
            }
            for n in [
                    "PR-blah.HEADs-clang-ghc844",
                    "PR-blah.HEADs-gnucc-ghc844",
                    "PR-blah.HEADs-clang-ghc865",
                    "PR-blah.HEADs-gnucc-ghc865",
                    "PR-blah.HEADs-clang-ghc881",
                    "PR-blah.HEADs-gnucc-ghc881",
                    "PR-blah.submodules-clang-ghc844",
                    "PR-blah.submodules-gnucc-ghc844",
                    "PR-blah.submodules-clang-ghc865",
                    "PR-blah.submodules-gnucc-ghc865",
                    "PR-blah.submodules-clang-ghc881",
                    "PR-blah.submodules-gnucc-ghc881",
                    "PR-bugfix9.HEADs-clang-ghc844",
                    "PR-bugfix9.HEADs-gnucc-ghc844",
                    "PR-bugfix9.HEADs-clang-ghc865",
                    "PR-bugfix9.HEADs-gnucc-ghc865",
                    "PR-bugfix9.HEADs-clang-ghc881",
                    "PR-bugfix9.HEADs-gnucc-ghc881",
                    "PR-bugfix9.submodules-clang-ghc844",
                    "PR-bugfix9.submodules-gnucc-ghc844",
                    "PR-bugfix9.submodules-clang-ghc865",
                    "PR-bugfix9.submodules-gnucc-ghc865",
                    "PR-bugfix9.submodules-clang-ghc881",
                    "PR-bugfix9.submodules-gnucc-ghc881",
                    "dev.HEADs-clang-ghc844",
                    "dev.HEADs-gnucc-ghc844",
                    "dev.HEADs-clang-ghc865",
                    "dev.HEADs-gnucc-ghc865",
                    "dev.HEADs-clang-ghc881",
                    "dev.HEADs-gnucc-ghc881",
                    "dev.submodules-clang-ghc844",
                    "dev.submodules-gnucc-ghc844",
                    "dev.submodules-clang-ghc865",
                    "dev.submodules-gnucc-ghc865",
                    "dev.submodules-clang-ghc881",
                    "dev.submodules-gnucc-ghc881",
                    "feat1.HEADs-clang-ghc844",
                    "feat1.HEADs-gnucc-ghc844",
                    "feat1.HEADs-clang-ghc865",
                    "feat1.HEADs-gnucc-ghc865",
                    "feat1.HEADs-clang-ghc881",
                    "feat1.HEADs-gnucc-ghc881",
                    "feat1.submodules-clang-ghc844",
                    "feat1.submodules-gnucc-ghc844",
                    "feat1.submodules-clang-ghc865",
                    "feat1.submodules-gnucc-ghc865",
                    "feat1.submodules-clang-ghc881",
                    "feat1.submodules-gnucc-ghc881",
                    "master.HEADs-clang-ghc844",
                    "master.HEADs-gnucc-ghc844",
                    "master.HEADs-clang-ghc865",
                    "master.HEADs-gnucc-ghc865",
                    "master.HEADs-clang-ghc881",
                    "master.HEADs-gnucc-ghc881",
                    "master.submodules-clang-ghc844",
                    "master.submodules-gnucc-ghc844",
                    "master.submodules-clang-ghc865",
                    "master.submodules-gnucc-ghc865",
                    "master.submodules-clang-ghc881",
                    "master.submodules-gnucc-ghc881",
            ]
        ]
        prior = [
            StatusReport(status='initial_success', project='R1', projrepo='R1',
                         strategy="submodules", buildname='master.submodules-gnucc-ghc844',
                         bldvars=[BldVariable(projrepo='R1', varname='ghcver', varvalue='ghc844'),
                                  BldVariable(projrepo='R1', varname='c_compiler', varvalue='gnucc'),
                         ]),
            StatusReport(status='failed', project='R1', projrepo='R1',
                         strategy="HEADs", buildname='master.HEADs-gnucc-ghc865',
                         bldvars=[BldVariable(projrepo='R1', varname='ghcver', varvalue='ghc865'),
                                  BldVariable(projrepo='R1', varname='c_compiler', varvalue='gnucc'),
                         ]),
            StatusReport(status='succeeded', project='R1', projrepo='R1',
                         strategy="HEADs", buildname='master.HEADs-gnucc-ghc844',
                         bldvars=[BldVariable(projrepo='R1', varname='ghcver', varvalue='ghc844'),
                                  BldVariable(projrepo='R1', varname='c_compiler', varvalue='gnucc'),
                         ]),
        ]
        report = anarep.report_on(inp_desc, repo_info, build_cfgs, prior)
        assert report[0] == 'report'
        yield (builder_cfgs, report[1])
        asys.shutdown()
        asys = None
    finally:
        if asys:
            asys.shutdown()


def test_example_report(example_hydra_results):
    bldcfgs, reps = example_hydra_results

    for each in reps:
        print('')
        print(each)
    print('')
    print(len(reps))
    assert ProjectSummary(project_name='R1',
                          bldcfg_count=60, subrepo_count=2, pullreq_count=3) in reps

    # Check for a single entry
    assert StatusReport(status='failed', project='R1', projrepo='R1',
                        strategy="HEADs", buildname='PR-blah.HEADs-clang-ghc844',
                        bldvars=[BldVariable(projrepo='R1', varname='ghcver', varvalue='ghc844'),
                                 BldVariable(projrepo='R1', varname='c_compiler', varvalue='clang'),
                        ]) in reps

    # Check for all entries that should be present
    CS = [ 'clang', 'gnucc' ]
    GS = [ 'ghc844', 'ghc865', 'ghc881' ]
    SS = [ 'HEADs', 'submodules' ]
    BS = [ 'PR-blah', 'PR-bugfix9', "feat1", "master", "dev",]
    for C in CS:
        for G in GS:
            for S in SS:
                for B in BS:
                    assert StatusReport(
                        status=('succeeded'
                                if C == 'gnucc' and G == 'ghc844' and S == 'submodules' and B == 'master'
                                else 'fixed'
                                if C == 'gnucc' and G == 'ghc865' and S == 'HEADs' and B == 'master'
                                else 'succeeded'
                                if C == 'gnucc' and G == 'ghc844' and S == 'HEADs' and B == 'master'
                                else 'failed'
                                if C == 'clang'
                                else 'initial_success'),
                        project='R1', projrepo='R1',
                        strategy=S,
                        buildname='-'.join(['.'.join([B,S]),C,G]),
                        bldvars=[BldVariable(projrepo='R1', varname='ghcver', varvalue=G),
                                 BldVariable(projrepo='R1', varname='c_compiler', varvalue=C),
                        ]) in reps


    assert VarFailure('R1', 'c_compiler', 'clang') in reps

    # Verify that there are no unexpected additional entries
    assert (len(CS) * len(GS) * len(SS) * len(BS) + 2) == len(reps)