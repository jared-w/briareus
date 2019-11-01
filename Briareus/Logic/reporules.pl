/* Rules and reasoning -------------------------------------------------------------- */

%% Test if an argument is a Project Repo
is_project_repo(R) :- repo(R), project(R).

has_gitmodules(R, B) :-
    bagof(B, V^S^(is_project_repo(R), (branchreq(R,B); pullreq(R,_,B)), submodule(R, B, S, V)), BHG),
    \+ length(BHG, 0).

all_repos_no_subs(ALLR) :- findall(R, repo(R), ALLR).
all_repos(ALLR) :- findall(R, (repo(R) ; subrepo(R)), ALLR).
all_vars(ProjRepo, ALLV) :- findall(VN, varname(ProjRepo, VN), ALLV).

build_config(bldcfg(ProjRepo, BranchType, Branch, Strategy, BLDS, VARS)) :-
    branch_type(BranchType, Branch),
    is_project_repo(ProjRepo),
    strategy(Strategy, ProjRepo, Branch),
    all_repos(RL),
    all_vars(ProjRepo, VL),
    varcombs(ProjRepo, VL, VARS),

    % If submodules and not master branch and the branch doesn't exist
    % in master, don't generate the configuration because the
    % submodules dictate all configurations so there's no way the
    % indicated branch can be referenced.
    (Branch == "master";
     BranchType == pullreq;
     Strategy == heads;
     Strategy == main;
     (Branch \== "master",
      BranchType==regular,
      Strategy == submodules,
      all_repos_no_subs(TLR),
      branch_in_any(TLR, Branch)
     )),

    reporevs(RL, ProjRepo, BranchType, Branch, Strategy, BLDS)
.

branch_in_any([], _Branch) :- false.
branch_in_any([R|RL], Branch) :-
    branch(R, Branch) ; branch_in_any(RL, Branch).

varcombs(_, [], []).
varcombs(ProjRepo, [VN|VNS], [varvalue(ProjRepo,VN,VVS)|VNSVS]) :-
    varname(ProjRepo, VN),
    varvalue(ProjRepo, VN,VVS),
    varcombs(ProjRepo, VNS, VNSVS).

branch_type(pullreq, B) :- setof(X, R^I^pullreq(R, I, X), XS), member(B, XS).
branch_type(regular, B) :- branchreq(R, B), is_project_repo(R).

useable_submodules(R, B) :- (branch(R, B), has_gitmodules(R, B));
                            (has_gitmodules(R, "master"), \+ branch(R, B)).  % KWQ: this doesn't work if reversed.

strategy(submodules, R, B) :- (branch_type(pullreq, B) ; branchreq(R, B)), useable_submodules(R, B).
strategy(heads,      R, B) :- (branch_type(pullreq, B) ; branchreq(R, B)), useable_submodules(R, B).
strategy(main,       R, B) :- (branch_type(pullreq, B) ; branchreq(R, B)), \+ useable_submodules(R, B).


%% if pullreq changes submodules, don't have that data available
%% defaulting to master if unknown, but should default to origin of branch

reporevs([], _, _, _, _, []).
reporevs([R|Rs], ProjRepo, BranchType, Branch, Strategy, Result) :-
    (repo(R) ; subrepo(R)),
    reporevs(Rs, ProjRepo, BranchType, Branch, Strategy, RevSpecs),
    reporev(R, ProjRepo, BranchType, Branch, Strategy, RevSpec),
    build_revspecs(RevSpec, RevSpecs, Result),
    !  %% cut so that the reporevs below with build_revspecs(skip, ...) isn't used to skip this R.
.
%% If this is a subrepo that is not utilized on this ProjRepo branch, skip it
reporevs([R|Rs], ProjRepo, BranchType, Branch, Strategy, Result) :-
    subrepo(R),
    reporevs(Rs, ProjRepo, BranchType, Branch, Strategy, RevSpecs),
    build_revspecs(skip, RevSpecs, Result).


build_revspecs(RevSpec, RevSpecs, RevSpecs) :- RevSpec = skip.
build_revspecs(RevSpec, RevSpecs, [RevSpec|RevSpecs]) :- RevSpec \= skip.


%% branch_type = pullreq | regular
%% strategy = submodules | heads | main

reporev(R, ProjRepo, pullreq, B, submodules, RepoRev) :-
    submodule(ProjRepo, B, R, SubRev),
    pullreq(_, _I, B),
    bldwith(RepoRev, R, SubRev, brr(09)).

reporev(R, ProjRepo, pullreq, B, heads, RepoRev) :-
    submodule(ProjRepo, B, R, _),
    pullreq(_, _I, B),
    branch(R, B),
    bldwith(RepoRev, R, B, brr(08)).

reporev(R, ProjRepo, pullreq, B, heads, RepoRev) :-
    submodule(ProjRepo, B, R, _),
    pullreq(_, _I, B),
    \+ branch(R, B),
    bldwith(RepoRev, R, "master", brr(07)).

reporev(R, ProjRepo, _BType,  B, submodules, RepoRev) :-
    submodule(ProjRepo, B, R, SubRev),
    bldwith(RepoRev, R, SubRev, brr(04)).

reporev(R, ProjRepo, _BType,  B, heads, RepoRev) :-
    submodule(ProjRepo, B, R, _),
    branch(R, B),
    bldwith(RepoRev, R, B, brr(05)).

reporev(R, ProjRepo, _BType,  B, heads, RepoRev) :-
    submodule(ProjRepo, B, R, _),
    \+ branch(R, B),
    branchreq(ProjRepo,B),
    bldwith(RepoRev, R, "master", brr(06)).

reporev(R, _ProjRepo, pullreq, B, _Strategy, RepoRev) :-
    repo(R),
    pullreq(R, _I, B),
    bldwith(RepoRev, R, B, brr(03)).

reporev(R, ProjRepo, pullreq, B, _Strategy,  RepoRev) :-
    submodule(ProjRepo, "master", R, _),
    \+ pullreq(ProjRepo, _, B),
    pullreq(R, _, B),
    bldwith(RepoRev, R, B, brr(10)).

reporev(R, ProjRepo, pullreq, B, submodules, RepoRev) :-
    submodule(ProjRepo, "master", R, SubRev),
    \+ pullreq(ProjRepo, _, B),
    \+ pullreq(R, _, B),
    bldwith(RepoRev, R, SubRev, brr(11)).

reporev(R, ProjRepo, pullreq, B, heads, RepoRev) :-
    submodule(ProjRepo, "master", R, _),
    \+ pullreq(ProjRepo, _, B),
    \+ pullreq(R, _, B),
    bldwith(RepoRev, R, "master", brr(12)).

reporev(R, ProjRepo, regular, B, submodules, RepoRev) :-
    \+ submodule(ProjRepo, B, R, _),
    submodule(ProjRepo, "master", R, SubRev),
    \+ branch(R, B),
    bldwith(RepoRev, R, SubRev, brr(13)),
    !.

reporev(R, ProjRepo, regular, B, heads, RepoRev) :-
    \+ submodule(ProjRepo, B, R, _),
    submodule(ProjRepo, "master", R, _),
    branch(R, B),
    bldwith(RepoRev, R, B, brr(15)),
    !.

reporev(R, ProjRepo, regular, B, heads, RepoRev) :-
    \+ submodule(ProjRepo, B, R, _),
    submodule(ProjRepo, "master", R, _),
    \+ branch(R, B),
    bldwith(RepoRev, R, "master", brr(14)),
    !.

reporev(R, ProjRepo, _BType,  B, _Strategy,  RepoRev) :-
    repo(R),
    \+ submodule(ProjRepo, B, R, _),
    branch(R, B),
    bldwith(RepoRev, R, B, brr(01)).

reporev(R, ProjRepo, _BType,  B, _Strategy,  RepoRev) :-
    repo(R),
    \+ submodule(ProjRepo, B, R, _),
    \+ branch(R, B),
    bldwith(RepoRev, R, "master", brr(02)).

bldwith(bld(R, B, I), R, B, I).
