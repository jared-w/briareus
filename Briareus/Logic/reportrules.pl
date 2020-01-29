%% Input facts are VCS facts plus build results (generated by the Builder):
%%
%% bldres(PName, branchtype, "branchname", strategy, ?bldcfg?,
%%        [varvalue("PName", "vname", "value"), ...],
%%        builderCfgName, njobs, nsucceeded, nfailed, nscheduled, cfgstatus)
%%
%%   branchtype = pullreq | regular
%%   strategy   = standard | heads | submodules
%%   cfgstatus  = configValid | configError
%%
%% The rules here form the first layer of results: reporting based on build configurations and results

good_status(succeeded).
good_status(initial_success).
good_status(fixed).

bad_status(failed).
bad_status(N) :- integer(N).
bad_status(badconfig).
bad_status(pending).  % as in not good_status

listcmp([A|AS], BS) :- member(A, BS), listcmp(AS, BS).
listcmp([], _).

report(status_report(succeeded, project(PName), Strategy, BranchType, Branch, Bldname, Vars)) :-
    project(PName, _),
    strategy(Strategy, PName, Branch),
    branch_type(BranchType, Branch, _),
    bldres(PName, BranchType, Branch, Strategy, Vars, Bldname, N, N, 0, 0, configValid),
    prior_status(Status, project(PName), Strategy, BranchType, Branch, Bldname, PriorVars),
    good_status(Status),
    listcmp(Vars, PriorVars).

report(status_report(fixed, project(PName), Strategy, BranchType, Branch, Bldname, Vars)) :-
    project(PName, _),
    strategy(Strategy, PName, Branch),
    branch_type(BranchType, Branch, _),
    bldres(PName, BranchType, Branch, Strategy, Vars, Bldname, N, N, 0, 0, configValid),
    prior_status(PrevSts, project(PName), Strategy, BranchType, Branch, Bldname, PriorVars),
    bad_status(PrevSts),
    listcmp(Vars, PriorVars).

report(status_report(initial_success, project(PName), Strategy, BranchType, Branch, Bldname, Vars)) :-
    project(PName, _),
    strategy(Strategy, PName, Branch),
    branch_type(BranchType, Branch, _),
    bldres(PName, BranchType, Branch, Strategy, Vars, Bldname, N, N, 0, 0, configValid),
    findall(S, (prior_status(S, project(PName), Strategy, BranchType, Branch, Bldname, PriorVars),
                listcmp(Vars, PriorVars)), PS),
    length(PS, 0).

report(status_report(N, project(PName), Strategy, BranchType, Branch, Bldname, Vars)) :-
    project(PName, _),
    strategy(Strategy, PName, Branch),
    branch_type(BranchType, Branch, _),
    bldres(PName, BranchType, Branch, Strategy, Vars, Bldname, _, _, N, 0, configValid),
    N > 0.

report(status_report(badconfig, project(PName), Strategy, BranchType, Branch, Bldname, Vars)) :-
    project(PName, _),
    strategy(Strategy, PName, Branch),
    branch_type(BranchType, Branch, _),
    bldres(PName, BranchType, Branch, Strategy, Vars, Bldname, _, _, _, _, configError).

% Note, pending_status is different than status_report because
% status_report wants to track transitions (fixed v.s. initial vis
% still good) and with only one layer of history, introducing a
% status_report(pending, ...) would obscure the previous results.
report(pending_status(project(PName), Strategy, BranchType, Branch, Bldname, Vars)) :-
    project(PName, _),
    strategy(Strategy, PName, Branch),
    branch_type(BranchType, Branch, _),
    bldres(PName, BranchType, Branch, Strategy, Vars, Bldname, _, _, _, N, configValid),
    N > 0.

% This preserves the previous status for a pending build
report(status_report(Sts, project(PName), Strategy, BranchType, Branch, Bldname, Vars)) :-
    project(PName, _)
    , strategy(Strategy, PName, Branch)
    , branch_type(BranchType, Branch, _)
    , bldres(PName, BranchType, Branch, Strategy, Vars, Bldname, _, _, _, N, configValid)
    , N > 0
    , prior_status(Sts, project(PName), Strategy, BranchType, Branch, Bldname, PriorVars)
    , listcmp(Vars, PriorVars)
    .

report(complete_failure(PName)) :-
    project(PName, _),
    findall(X, (report(status_report(S,project(PName),_,_,_,X,_)),
                good_status(S)),
            Res),
    length(Res, 0).

report(var_failure(PName, N, V)) :-
    varvalue(PName, N, V),
    findall(X, (report(status_report(S,project(PName),_,_,_,X,Vars)),
                good_status(S),
                member(varvalue(PName, N, V), Vars)),
            Res),
    length(Res, 0),
    \+ report(complete_failure(PName)).


%% ------------------------------------------------------------
%% PR assessments

report(pr_success(Branch, RIS)) :-
    pr_failures(Branch, RIS, Cfgs),
    length(Cfgs, 0).

report(pr_failure(Branch, RIS)) :-
    pr_failures(Branch, RIS, Cfgs),
    length(Cfgs, N), N > 0.

report(pr_failing(PName, Branch, "strategy-TBD", Cfgs)) :-
    project(PName, _),
    branch_type(pullreq, Branch, _),
    findall(X, (report(status_report(S,project(PName),_,pullreq,Branch,X,_)),
                bad_status(S)),
            Cfgs).

pr_failures(Branch, RIS, Cfgs) :-
    branch_type(pullreq, Branch, _),
    findall(X, (project(PName, _),
                report(status_report(S,project(PName),_,pullreq,Branch,X,_)),
                bad_status(S)),
            Cfgs),
    findall((R,I), pullreq(R,I,Branch), RIS).
