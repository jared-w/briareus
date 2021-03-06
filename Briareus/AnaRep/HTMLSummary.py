"Generate an HTML summary of a build report"

from collections import defaultdict
from Briareus.KVITable import KVITable
from Briareus.Types import (StatusReport, PendingStatus, NewPending, Notify)
from Briareus.BuildSys import buildcfg_name
from Briareus.AnaRep.TextSummary import tbl_branch, tbl_branch_

_inc = lambda n: n + 1
_dec = lambda n: n - 1

class TCell_Bld(object):
    def __init__(self, project, bldname):
        self._project = project
        self._bldname = bldname
    def render(self, make_builder_url=None):
        if make_builder_url:
            url = make_builder_url(self._project, self._bldname)
            return ('<a href="%(url)s" class="bldsts %(ststype)s">%(cell)s</a>'
                    %
                    { 'url': url,
                      'ststype': self.ststype,
                      'cell': str(self),
                    })
        return str(self)
    def __call__(self, orig):
        # Callable for combining with previous entry at this location in the table
        if orig is None:
            return self
        if isinstance(orig, TCell_PendingBld):
            orig.set_prev(self)
            return orig
        return None


class TCell_GoodBld(TCell_Bld):
    ststype = "good"
    def __str__(self): return 'ok'

class TCell_BadCfgBld(TCell_Bld):
    ststype = "badcfg"
    def __str__(self): return '-CFG'

class TCell_FailBld(TCell_Bld):
    ststype = "fail"
    def __init__(self, project, bldname, failcnt):
        super(TCell_FailBld, self).__init__(project, bldname)
        self._failcnt = int(failcnt)
    def __call__(self, orig):
        # Callable for combining with previous entry at this location in the table
        r = super(TCell_FailBld, self).__call__(orig)
        if r is not None:
            return r
        if isinstance(orig, TCell_FailBld):
            self._failcnt += orig.cnt()
            return self
        if not isinstance(orig, TCell_FailBld):
            raise ValueError('Combine TCell_FailBld with old %s: unsupported' %
                             str(type(orig)))
    def cnt(self):
        return self._failcnt
    def __str__(self): return 'FAIL:%d' % self.cnt()

class TCell_PendingBld(TCell_Bld):
    ststype = "pending"
    def __init__(self, project, bldname):
        super(TCell_PendingBld, self).__init__(project, bldname)
        self._prev = None
    def set_prev(self, prev):
        self._prev = prev
    def __str__(self):
        if self._prev:
            return '(' + str(self._prev) + ')?'
        return '??'

def tcell_entshow(base_builder_url):
    def _t_es(path, ent):
        if isinstance(ent, TCell_Bld):
            if base_builder_url:
                mkurl = lambda p, n: "/".join([base_builder_url, "jobset", p, n])
                return ent.render(mkurl)
            return ent.render()
        return str(ent)
    return _t_es

def html_summary(repdata, base_builder_url=None):
    section_hdrfun = lambda msg: '<br/><hr class="section_line"/><br/><h2>' + msg + '</h2><br/>'
    subsection_hdrfun = lambda msg: '<br/><h3>' + msg + '</h3>'
    entshow_fun = tcell_entshow(base_builder_url)

    projects = set([ sr.project for sr in repdata if isinstance(sr, StatusReport) ])

    summary = KVITable(default_factory=int, valuecol_name='Total')
    summary.add(len(projects), Element='Projects')
    summary.add(len(set([sr.branch for sr in repdata
                         if isinstance(sr, StatusReport) and sr.branchtype=='pullreq'])), Element='Pull Requests')

    projtable = KVITable({
        'Project': sorted(list(set([ sr.project
                                     for sr in repdata
                                     if isinstance(sr, StatusReport) ]))),
        'Status': [ 'TOTAL', 'ok', 'FAIL', 'pending' ],
    },
                         valuecol_name='Number',
                         kv_frozen=False,
                         default_factory=int)

    fulltable = KVITable({
        'Branch': [],
        'system': ['x86-64_linux'],
        'Strategy': ['regular', 'submodules', 'HEADs'],
        'Project': [],
    },
                         valuecol_name='Build Status',
                         default_factory=lambda: None,
                         keyval_factory=lambda key: 'x86_64-linux' if key == 'system' else 'n/a',
                         kv_frozen=False)

    mkDetailTable = lambda: KVITable({
        'system': ['x86-64_linux'],
        'Branch': [],
        'Strategy': ['regular', 'submodules', 'HEADs'],
    },
                                     valuecol_name='Build Status',
                                     default_factory=lambda: None,
                                     keyval_factory=lambda key: 'x86_64-linux' if key == 'system' else '',
                                     kv_frozen=False)
    detailtables = defaultdict(mkDetailTable)
    projtable_sts = lambda s: { 'initial_success': 'ok',
                                'succeeded': 'ok',
                                # 'pending': 'pending',
    }.get(s, 'FAIL')

    for sr in repdata:

        if isinstance(sr, Notify):
            summary.add(_inc, Element='Notifications')

        elif isinstance(sr, PendingStatus):
            prev = [ r for r in repdata
                     if isinstance(r, StatusReport)
                     and r.project == sr.project
                     and r.buildname == sr.buildname ]
            if not prev:
                summary.add(_inc, Element='Builds')
                projtable.add(_inc, Project=sr.project, Status="TOTAL")
            else:
                projtable.add(_dec, Project=sr.project, Status=projtable_sts(prev[0].status))
            projtable.add(_inc, Project=sr.project, Status="pending")
            vars = tuple([ (v.varname, v.varvalue) for v in sr.bldvars ])

            fulltable.add(TCell_PendingBld(sr.project, sr.buildname),
                          *vars,
                          Project=sr.project,
                          Branch=tbl_branch(sr),
                          Strategy=sr.strategy)
            detailtables[sr.project].add(TCell_PendingBld(sr.project, sr.buildname),
                                         *vars,
                                         Branch=tbl_branch(sr),
                                         Strategy=sr.strategy)

        elif isinstance(sr, NewPending):
            summary.add(_inc, Element='Builds')
            projectname = sr.bldcfg.projectname
            buildname = buildcfg_name(sr.bldcfg)
            tbl_brname = tbl_branch_(buildname, sr.bldcfg.branchname)
            projtable.add(_inc, Project=projectname, Status="TOTAL")
            projtable.add(_inc, Project=projectname, Status="pending")
            vars = tuple([ (v.varname, v.varvalue) for v in sr.bldcfg.bldvars ])

            fulltable.add(TCell_PendingBld(projectname, buildname),
                          *vars,
                          Project=projectname,
                          Branch=tbl_brname,
                          Strategy=sr.bldcfg.strategy)
            detailtables[sr.bldcfg.projectname].add(
                TCell_PendingBld(projectname, buildname),
                *vars,
                Branch=tbl_brname,
                Strategy=sr.bldcfg.strategy)

        elif isinstance(sr, StatusReport):
            summary.add(_inc, Element='Builds')

            projtable.add(_inc, Project=sr.project, Status=projtable_sts(sr.status))
            projtable.add(_inc, Project=sr.project, Status='TOTAL')

            bldres = { 'initial_success' : TCell_GoodBld,
                       'succeeded' : TCell_GoodBld,
                       'fixed' : TCell_GoodBld,
                       'bad_config' : TCell_BadCfgBld,
            }.get(sr.status,
                  lambda proj, name: TCell_FailBld(proj, name, sr.status)
            )(sr.project, sr.buildname)

            fulltable.add(bldres,
                          *tuple([ (v.varname, v.varvalue) for v in sr.bldvars ]),
                          Project=sr.project,
                          Branch=tbl_branch(sr),
                          Strategy=sr.strategy)

            detailtables[sr.project].add(bldres,
                                         *tuple([ (v.varname, v.varvalue) for v in sr.bldvars ]),
                                         Branch=tbl_branch(sr),
                                         Strategy=sr.strategy)

    return '\n\n'.join([
        summary.render(as_format='html', sort_vals=True),
        section_hdrfun('Per-project Build Status Summary ::'),
        projtable.render(row_group=['Project'],
                         row_repeat=False,
                         sort_vals=False,
                         as_format='html',
                         caption='Per-project Build Status Summary',
                         colstack_at='Status'),
        section_hdrfun('Combined Details ::'),
        fulltable.render(row_group=['system', 'Branch', 'Strategy'],
                         row_repeat=False,
                         sort_vals=True,
                         entrystr=entshow_fun,
                         as_format='html',
                         caption='Combined Details',
                         colstack_at=(list(fulltable.keyvals().keys()) + [None])[4],),
        section_hdrfun('Individual Project Summaries ::'),
        '\n\n'.join([subsection_hdrfun('Project %s:\n' % p) +
                     detailtables[p].render(row_repeat=False,
                                            as_format='html',
                                            caption='Project %s' % p,
                                            sort_vals=True,
                                            colstack_at=(list(detailtables[p].keyvals().keys()) + [None])[3],
                                            row_group=['system', 'Branch'],
                                            entrystr=entshow_fun,
                     )
                     for p in sorted(projects)])
        ])
