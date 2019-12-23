%% This is a logic layer that uses the VCS facts, the reporules, the
%% build results, and the reportrules to perform a higher-level
%% analysis of the status.

:- discontiguous analysis/1.
                 
analysis(mergeable_pr(Branch, RIS)) :-
    report(pr_success(Branch, RIS)).

%% handle the build failures for this variable separately from other
%% analyses if the variable has completely failed and there are other
%% values for the variable that have not completely failed.
analysis(var_handled_separately(Project, VarName, VarValue)) :-
    report(var_failure(Project, VarName, VarValue)),
    findall(V, (varvalue(Project, VarName, V)), VS),
    delete(VS, VarValue, VVS),
    length(VVS, L),
    L > 0,
    other_var_failures(Project, VarName, VVS, FS),
    length(FS, LF),
    LF < L.

other_var_failures(_Project, _VarName, [], []).
other_var_failures(Project, VarName, [V|VS], Res) :-
    report(var_failure(Project, VarName, V)),
    other_var_failures(Project, VarName, VS, RSub),
    cons(V, RSub, Res).
other_var_failures(Project, VarName, [V|VS], Res) :-
    other_var_failures(Project, VarName, VS, Res),
    \+ report(var_failure(Project, VarName, V)).

cons(H, T, [H|T]).
% identity(V,V).

%% ----------------------------------------------------------------------
%% Actions


action(notify(completely_broken, Project, NBldCfgs)) :-
    report(complete_failure(Project)),
    findall(C, bldres(Project, _BType, _Br, _Strat, _Vars, C, _Ttl, _Pass, _Fail, _Pend, _Conf), Cfgs),
    length(Cfgs, NBldCfgs),
    NBldCfgs > 0.

action(notify(merge_pr, Branch, RIS)) :-  % Project
    report(mergeable_pr(Branch, RIS)).

action(notify(variable_failing, Project, varvalue(Project, VarName, VarValue))) :-
    is_project_repo(Project),
    report(var_failure(Project, VarName, VarValue)),
    analysis(var_handled_separately(Project, VarName, VarValue)).

%% generate a notification if the master_submodules is broken (the
%% most important build), ignoring any variables that are completely
%% failing.
action(notify(master_submodules_broken, Project, Configs)) :-
    is_project_repo(Project),
    \+ report(complete_failure(Project)),
    findall(C, (report(status_report(Status, project(Project), submodules, regular, "master", C, Vars)),
                bad_status(Status),
                findall((N,V), (member(varvalue(Project, N, V), Vars),
                                report(var_failure(Project, N, V))), XS),
                length(XS, 0)),
            CS),
    length(CS, N), N > 0,
    sort(CS, Configs).

action(notify(master_submodules_good, Project, CS)) :-
    is_project_repo(Project),
    \+ report(complete_failure(Project)),
    findall(C, (report(status_report(Status, project(Project), submodules, regular, "master", C, _Vars)),
                bad_status(Status)),
            CS),
    length(CS, 0).

%% ----------------------------------------------------------------------
%% Action bindings

:- discontiguous email_domain_whitelist/1.
:- discontiguous email_domain_blacklist/1.
:- discontiguous email_user_blacklist/1.

:- dynamic action_type/2.
:- dynamic action_type/4.

email_address_useable(Addr) :-
    split_string(Addr, "@", " ", [_User|[Domain|[]]]),
    findall(D, email_domain_whitelist(D), WL_Domains),
    (length(WL_Domains, 0); member(Domain, WL_Domains)),
    \+ email_domain_blacklist(Domain),
    \+ email_user_blacklist(Addr)
.

action_type(email, Email, completely_broken, Project) :- project_owner(Project, Email).
action_type(email, Email, master_submodules_broken, Project) :- project_owner(Project, Email).


do_new(What, Item, Previous) :- call(What, _, Item, Previous), !.
do_new(_, _, []).

do_notnew([]).

:- discontiguous email/3.
:- discontiguous chat/3.

do(email(Users, notify(What, P, CS), Notified)) :-
    Notification = notify(What, P, CS),
    action(Notification),
    setof(User, ((action_type(email, User) ; action_type(email, User, What, P)),
                 email_address_useable(User)
                 ), Users),
    do_new(email, Notification, Notified).

do(chat(Channels, notify(What, Item, Args), Posted)) :-
    action(notify(What, Item, Args)),
    setof(Channel, action_type(chat, Channel, What, Item), Channels),
    %% do_notnew(Posted).
    do_new(chat, notify(What, Item, Args), Posted).

