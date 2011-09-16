# commands.py - command processing for mercurial
#
# Copyright 2005-2007 Matt Mackall <mpm@selenic.com>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from node import hex, bin, nullid, nullrev, short
from lock import release
from i18n import _, gettext
import os, re, difflib, time, tempfile, errno
import hg, scmutil, util, revlog, extensions, copies, error, bookmarks
import patch, help, url, encoding, templatekw, discovery
import archival, changegroup, cmdutil, hbisect
import sshserver, hgweb, hgweb.server, commandserver
import merge as mergemod
import minirst, revset, fileset
import dagparser, context, simplemerge
import random, setdiscovery, treediscovery, dagutil

table = {}

command = cmdutil.command(table)

# common command options

globalopts = [
    ('R', 'repository', '',
     _('repository root directory or name of overlay bundle file'),
     _('REPO')),
    ('', 'cwd', '',
     _('change working directory'), _('DIR')),
    ('y', 'noninteractive', None,
     _('do not prompt, automatically pick the first choice for all prompts')),
    ('q', 'quiet', None, _('suppress output')),
    ('v', 'verbose', None, _('enable additional output')),
    ('', 'config', [],
     _('set/override config option (use \'section.name=value\')'),
     _('CONFIG')),
    ('', 'debug', None, _('enable debugging output')),
    ('', 'debugger', None, _('start debugger')),
    ('', 'encoding', encoding.encoding, _('set the charset encoding'),
     _('ENCODE')),
    ('', 'encodingmode', encoding.encodingmode,
     _('set the charset encoding mode'), _('MODE')),
    ('', 'traceback', None, _('always print a traceback on exception')),
    ('', 'time', None, _('time how long the command takes')),
    ('', 'profile', None, _('print command execution profile')),
    ('', 'version', None, _('output version information and exit')),
    ('h', 'help', None, _('display help and exit')),
]

dryrunopts = [('n', 'dry-run', None,
               _('do not perform actions, just print output'))]

remoteopts = [
    ('e', 'ssh', '',
     _('specify ssh command to use'), _('CMD')),
    ('', 'remotecmd', '',
     _('specify hg command to run on the remote side'), _('CMD')),
    ('', 'insecure', None,
     _('do not verify server certificate (ignoring web.cacerts config)')),
]

walkopts = [
    ('I', 'include', [],
     _('include names matching the given patterns'), _('PATTERN')),
    ('X', 'exclude', [],
     _('exclude names matching the given patterns'), _('PATTERN')),
]

commitopts = [
    ('m', 'message', '',
     _('use text as commit message'), _('TEXT')),
    ('l', 'logfile', '',
     _('read commit message from file'), _('FILE')),
]

commitopts2 = [
    ('d', 'date', '',
     _('record the specified date as commit date'), _('DATE')),
    ('u', 'user', '',
     _('record the specified user as committer'), _('USER')),
]

templateopts = [
    ('', 'style', '',
     _('display using template map file'), _('STYLE')),
    ('', 'template', '',
     _('display with template'), _('TEMPLATE')),
]

logopts = [
    ('p', 'patch', None, _('show patch')),
    ('g', 'git', None, _('use git extended diff format')),
    ('l', 'limit', '',
     _('limit number of changes displayed'), _('NUM')),
    ('M', 'no-merges', None, _('do not show merges')),
    ('', 'stat', None, _('output diffstat-style summary of changes')),
] + templateopts

diffopts = [
    ('a', 'text', None, _('treat all files as text')),
    ('g', 'git', None, _('use git extended diff format')),
    ('', 'nodates', None, _('omit dates from diff headers'))
]

diffopts2 = [
    ('p', 'show-function', None, _('show which function each change is in')),
    ('', 'reverse', None, _('produce a diff that undoes the changes')),
    ('w', 'ignore-all-space', None,
     _('ignore white space when comparing lines')),
    ('b', 'ignore-space-change', None,
     _('ignore changes in the amount of white space')),
    ('B', 'ignore-blank-lines', None,
     _('ignore changes whose lines are all blank')),
    ('U', 'unified', '',
     _('number of lines of context to show'), _('NUM')),
    ('', 'stat', None, _('output diffstat-style summary of changes')),
]

mergetoolopts = [
    ('t', 'tool', '', _('specify merge tool')),
]

similarityopts = [
    ('s', 'similarity', '',
     _('guess renamed files by similarity (0<=s<=100)'), _('SIMILARITY'))
]

subrepoopts = [
    ('S', 'subrepos', None,
     _('recurse into subrepositories'))
]

# Commands start here, listed alphabetically

@command('^add',
    walkopts + subrepoopts + dryrunopts,
    _('[OPTION]... [FILE]...'))
def add(ui, repo, *pats, **opts):
    """add the specified files on the next commit

    Schedule files to be version controlled and added to the
    repository.

    The files will be added to the repository at the next commit. To
    undo an add before that, see :hg:`forget`.

    If no names are given, add all files to the repository.

    .. container:: verbose

       An example showing how new (unknown) files are added
       automatically by :hg:`add`::

         $ ls
         foo.c
         $ hg status
         ? foo.c
         $ hg add
         adding foo.c
         $ hg status
         A foo.c

    Returns 0 if all files are successfully added.
    """

    m = scmutil.match(repo[None], pats, opts)
    rejected = cmdutil.add(ui, repo, m, opts.get('dry_run'),
                           opts.get('subrepos'), prefix="")
    return rejected and 1 or 0

@command('addremove',
    similarityopts + walkopts + dryrunopts,
    _('[OPTION]... [FILE]...'))
def addremove(ui, repo, *pats, **opts):
    """add all new files, delete all missing files

    Add all new files and remove all missing files from the
    repository.

    New files are ignored if they match any of the patterns in
    ``.hgignore``. As with add, these changes take effect at the next
    commit.

    Use the -s/--similarity option to detect renamed files. With a
    parameter greater than 0, this compares every removed file with
    every added file and records those similar enough as renames. This
    option takes a percentage between 0 (disabled) and 100 (files must
    be identical) as its parameter. Detecting renamed files this way
    can be expensive. After using this option, :hg:`status -C` can be
    used to check which files were identified as moved or renamed.

    Returns 0 if all files are successfully added.
    """
    try:
        sim = float(opts.get('similarity') or 100)
    except ValueError:
        raise util.Abort(_('similarity must be a number'))
    if sim < 0 or sim > 100:
        raise util.Abort(_('similarity must be between 0 and 100'))
    return scmutil.addremove(repo, pats, opts, similarity=sim / 100.0)

@command('^annotate|blame',
    [('r', 'rev', '', _('annotate the specified revision'), _('REV')),
    ('', 'follow', None,
     _('follow copies/renames and list the filename (DEPRECATED)')),
    ('', 'no-follow', None, _("don't follow copies and renames")),
    ('a', 'text', None, _('treat all files as text')),
    ('u', 'user', None, _('list the author (long with -v)')),
    ('f', 'file', None, _('list the filename')),
    ('d', 'date', None, _('list the date (short with -q)')),
    ('n', 'number', None, _('list the revision number (default)')),
    ('c', 'changeset', None, _('list the changeset')),
    ('l', 'line-number', None, _('show line number at the first appearance'))
    ] + walkopts,
    _('[-r REV] [-f] [-a] [-u] [-d] [-n] [-c] [-l] FILE...'))
def annotate(ui, repo, *pats, **opts):
    """show changeset information by line for each file

    List changes in files, showing the revision id responsible for
    each line

    This command is useful for discovering when a change was made and
    by whom.

    Without the -a/--text option, annotate will avoid processing files
    it detects as binary. With -a, annotate will annotate the file
    anyway, although the results will probably be neither useful
    nor desirable.

    Returns 0 on success.
    """
    if opts.get('follow'):
        # --follow is deprecated and now just an alias for -f/--file
        # to mimic the behavior of Mercurial before version 1.5
        opts['file'] = True

    datefunc = ui.quiet and util.shortdate or util.datestr
    getdate = util.cachefunc(lambda x: datefunc(x[0].date()))

    if not pats:
        raise util.Abort(_('at least one filename or pattern is required'))

    opmap = [('user', ' ', lambda x: ui.shortuser(x[0].user())),
             ('number', ' ', lambda x: str(x[0].rev())),
             ('changeset', ' ', lambda x: short(x[0].node())),
             ('date', ' ', getdate),
             ('file', ' ', lambda x: x[0].path()),
             ('line_number', ':', lambda x: str(x[1])),
            ]

    if (not opts.get('user') and not opts.get('changeset')
        and not opts.get('date') and not opts.get('file')):
        opts['number'] = True

    linenumber = opts.get('line_number') is not None
    if linenumber and (not opts.get('changeset')) and (not opts.get('number')):
        raise util.Abort(_('at least one of -n/-c is required for -l'))

    funcmap = [(func, sep) for op, sep, func in opmap if opts.get(op)]
    funcmap[0] = (funcmap[0][0], '') # no separator in front of first column

    def bad(x, y):
        raise util.Abort("%s: %s" % (x, y))

    ctx = scmutil.revsingle(repo, opts.get('rev'))
    m = scmutil.match(ctx, pats, opts)
    m.bad = bad
    follow = not opts.get('no_follow')
    for abs in ctx.walk(m):
        fctx = ctx[abs]
        if not opts.get('text') and util.binary(fctx.data()):
            ui.write(_("%s: binary file\n") % ((pats and m.rel(abs)) or abs))
            continue

        lines = fctx.annotate(follow=follow, linenumber=linenumber)
        pieces = []

        for f, sep in funcmap:
            l = [f(n) for n, dummy in lines]
            if l:
                sized = [(x, encoding.colwidth(x)) for x in l]
                ml = max([w for x, w in sized])
                pieces.append(["%s%s%s" % (sep, ' ' * (ml - w), x)
                               for x, w in sized])

        if pieces:
            for p, l in zip(zip(*pieces), lines):
                ui.write("%s: %s" % ("".join(p), l[1]))

@command('archive',
    [('', 'no-decode', None, _('do not pass files through decoders')),
    ('p', 'prefix', '', _('directory prefix for files in archive'),
     _('PREFIX')),
    ('r', 'rev', '', _('revision to distribute'), _('REV')),
    ('t', 'type', '', _('type of distribution to create'), _('TYPE')),
    ] + subrepoopts + walkopts,
    _('[OPTION]... DEST'))
def archive(ui, repo, dest, **opts):
    '''create an unversioned archive of a repository revision

    By default, the revision used is the parent of the working
    directory; use -r/--rev to specify a different revision.

    The archive type is automatically detected based on file
    extension (or override using -t/--type).

    Valid types are:

    :``files``: a directory full of files (default)
    :``tar``:   tar archive, uncompressed
    :``tbz2``:  tar archive, compressed using bzip2
    :``tgz``:   tar archive, compressed using gzip
    :``uzip``:  zip archive, uncompressed
    :``zip``:   zip archive, compressed using deflate

    The exact name of the destination archive or directory is given
    using a format string; see :hg:`help export` for details.

    Each member added to an archive file has a directory prefix
    prepended. Use -p/--prefix to specify a format string for the
    prefix. The default is the basename of the archive, with suffixes
    removed.

    Returns 0 on success.
    '''

    ctx = scmutil.revsingle(repo, opts.get('rev'))
    if not ctx:
        raise util.Abort(_('no working directory: please specify a revision'))
    node = ctx.node()
    dest = cmdutil.makefilename(repo, dest, node)
    if os.path.realpath(dest) == repo.root:
        raise util.Abort(_('repository root cannot be destination'))

    kind = opts.get('type') or archival.guesskind(dest) or 'files'
    prefix = opts.get('prefix')

    if dest == '-':
        if kind == 'files':
            raise util.Abort(_('cannot archive plain files to stdout'))
        dest = cmdutil.makefileobj(repo, dest)
        if not prefix:
            prefix = os.path.basename(repo.root) + '-%h'

    prefix = cmdutil.makefilename(repo, prefix, node)
    matchfn = scmutil.match(ctx, [], opts)
    archival.archive(repo, dest, node, kind, not opts.get('no_decode'),
                     matchfn, prefix, subrepos=opts.get('subrepos'))

@command('backout',
    [('', 'merge', None, _('merge with old dirstate parent after backout')),
    ('', 'parent', '', _('parent to choose when backing out merge'), _('REV')),
    ('r', 'rev', '', _('revision to backout'), _('REV')),
    ] + mergetoolopts + walkopts + commitopts + commitopts2,
    _('[OPTION]... [-r] REV'))
def backout(ui, repo, node=None, rev=None, **opts):
    '''reverse effect of earlier changeset

    Prepare a new changeset with the effect of REV undone in the
    current working directory.

    If REV is the parent of the working directory, then this new changeset
    is committed automatically. Otherwise, hg needs to merge the
    changes and the merged result is left uncommitted.

    By default, the pending changeset will have one parent,
    maintaining a linear history. With --merge, the pending changeset
    will instead have two parents: the old parent of the working
    directory and a new child of REV that simply undoes REV.

    Before version 1.7, the behavior without --merge was equivalent to
    specifying --merge followed by :hg:`update --clean .` to cancel
    the merge and leave the child of REV as a head to be merged
    separately.

    See :hg:`help dates` for a list of formats valid for -d/--date.

    Returns 0 on success.
    '''
    if rev and node:
        raise util.Abort(_("please specify just one revision"))

    if not rev:
        rev = node

    if not rev:
        raise util.Abort(_("please specify a revision to backout"))

    date = opts.get('date')
    if date:
        opts['date'] = util.parsedate(date)

    cmdutil.bailifchanged(repo)
    node = scmutil.revsingle(repo, rev).node()

    op1, op2 = repo.dirstate.parents()
    a = repo.changelog.ancestor(op1, node)
    if a != node:
        raise util.Abort(_('cannot backout change on a different branch'))

    p1, p2 = repo.changelog.parents(node)
    if p1 == nullid:
        raise util.Abort(_('cannot backout a change with no parents'))
    if p2 != nullid:
        if not opts.get('parent'):
            raise util.Abort(_('cannot backout a merge changeset without '
                               '--parent'))
        p = repo.lookup(opts['parent'])
        if p not in (p1, p2):
            raise util.Abort(_('%s is not a parent of %s') %
                             (short(p), short(node)))
        parent = p
    else:
        if opts.get('parent'):
            raise util.Abort(_('cannot use --parent on non-merge changeset'))
        parent = p1

    # the backout should appear on the same branch
    branch = repo.dirstate.branch()
    hg.clean(repo, node, show_stats=False)
    repo.dirstate.setbranch(branch)
    revert_opts = opts.copy()
    revert_opts['date'] = None
    revert_opts['all'] = True
    revert_opts['rev'] = hex(parent)
    revert_opts['no_backup'] = None
    revert(ui, repo, **revert_opts)
    if not opts.get('merge') and op1 != node:
        try:
            ui.setconfig('ui', 'forcemerge', opts.get('tool', ''))
            return hg.update(repo, op1)
        finally:
            ui.setconfig('ui', 'forcemerge', '')

    commit_opts = opts.copy()
    commit_opts['addremove'] = False
    if not commit_opts['message'] and not commit_opts['logfile']:
        # we don't translate commit messages
        commit_opts['message'] = "Backed out changeset %s" % short(node)
        commit_opts['force_editor'] = True
    commit(ui, repo, **commit_opts)
    def nice(node):
        return '%d:%s' % (repo.changelog.rev(node), short(node))
    ui.status(_('changeset %s backs out changeset %s\n') %
              (nice(repo.changelog.tip()), nice(node)))
    if opts.get('merge') and op1 != node:
        hg.clean(repo, op1, show_stats=False)
        ui.status(_('merging with changeset %s\n')
                  % nice(repo.changelog.tip()))
        try:
            ui.setconfig('ui', 'forcemerge', opts.get('tool', ''))
            return hg.merge(repo, hex(repo.changelog.tip()))
        finally:
            ui.setconfig('ui', 'forcemerge', '')
    return 0

@command('bisect',
    [('r', 'reset', False, _('reset bisect state')),
    ('g', 'good', False, _('mark changeset good')),
    ('b', 'bad', False, _('mark changeset bad')),
    ('s', 'skip', False, _('skip testing changeset')),
    ('e', 'extend', False, _('extend the bisect range')),
    ('c', 'command', '', _('use command to check changeset state'), _('CMD')),
    ('U', 'noupdate', False, _('do not update to target'))],
    _("[-gbsr] [-U] [-c CMD] [REV]"))
def bisect(ui, repo, rev=None, extra=None, command=None,
               reset=None, good=None, bad=None, skip=None, extend=None,
               noupdate=None):
    """subdivision search of changesets

    This command helps to find changesets which introduce problems. To
    use, mark the earliest changeset you know exhibits the problem as
    bad, then mark the latest changeset which is free from the problem
    as good. Bisect will update your working directory to a revision
    for testing (unless the -U/--noupdate option is specified). Once
    you have performed tests, mark the working directory as good or
    bad, and bisect will either update to another candidate changeset
    or announce that it has found the bad revision.

    As a shortcut, you can also use the revision argument to mark a
    revision as good or bad without checking it out first.

    If you supply a command, it will be used for automatic bisection.
    Its exit status will be used to mark revisions as good or bad:
    status 0 means good, 125 means to skip the revision, 127
    (command not found) will abort the bisection, and any other
    non-zero exit status means the revision is bad.

    Returns 0 on success.
    """
    def extendbisectrange(nodes, good):
        # bisect is incomplete when it ends on a merge node and
        # one of the parent was not checked.
        parents = repo[nodes[0]].parents()
        if len(parents) > 1:
            side = good and state['bad'] or state['good']
            num = len(set(i.node() for i in parents) & set(side))
            if num == 1:
                return parents[0].ancestor(parents[1])
        return None

    def print_result(nodes, good):
        displayer = cmdutil.show_changeset(ui, repo, {})
        if len(nodes) == 1:
            # narrowed it down to a single revision
            if good:
                ui.write(_("The first good revision is:\n"))
            else:
                ui.write(_("The first bad revision is:\n"))
            displayer.show(repo[nodes[0]])
            extendnode = extendbisectrange(nodes, good)
            if extendnode is not None:
                ui.write(_('Not all ancestors of this changeset have been'
                           ' checked.\nUse bisect --extend to continue the '
                           'bisection from\nthe common ancestor, %s.\n')
                         % extendnode)
        else:
            # multiple possible revisions
            if good:
                ui.write(_("Due to skipped revisions, the first "
                        "good revision could be any of:\n"))
            else:
                ui.write(_("Due to skipped revisions, the first "
                        "bad revision could be any of:\n"))
            for n in nodes:
                displayer.show(repo[n])
        displayer.close()

    def check_state(state, interactive=True):
        if not state['good'] or not state['bad']:
            if (good or bad or skip or reset) and interactive:
                return
            if not state['good']:
                raise util.Abort(_('cannot bisect (no known good revisions)'))
            else:
                raise util.Abort(_('cannot bisect (no known bad revisions)'))
        return True

    # backward compatibility
    if rev in "good bad reset init".split():
        ui.warn(_("(use of 'hg bisect <cmd>' is deprecated)\n"))
        cmd, rev, extra = rev, extra, None
        if cmd == "good":
            good = True
        elif cmd == "bad":
            bad = True
        else:
            reset = True
    elif extra or good + bad + skip + reset + extend + bool(command) > 1:
        raise util.Abort(_('incompatible arguments'))

    if reset:
        p = repo.join("bisect.state")
        if os.path.exists(p):
            os.unlink(p)
        return

    state = hbisect.load_state(repo)

    if command:
        changesets = 1
        try:
            while changesets:
                # update state
                status = util.system(command, out=ui.fout)
                if status == 125:
                    transition = "skip"
                elif status == 0:
                    transition = "good"
                # status < 0 means process was killed
                elif status == 127:
                    raise util.Abort(_("failed to execute %s") % command)
                elif status < 0:
                    raise util.Abort(_("%s killed") % command)
                else:
                    transition = "bad"
                ctx = scmutil.revsingle(repo, rev)
                rev = None # clear for future iterations
                state[transition].append(ctx.node())
                ui.status(_('Changeset %d:%s: %s\n') % (ctx, ctx, transition))
                check_state(state, interactive=False)
                # bisect
                nodes, changesets, good = hbisect.bisect(repo.changelog, state)
                # update to next check
                cmdutil.bailifchanged(repo)
                hg.clean(repo, nodes[0], show_stats=False)
        finally:
            hbisect.save_state(repo, state)
        print_result(nodes, good)
        return

    # update state

    if rev:
        nodes = [repo.lookup(i) for i in scmutil.revrange(repo, [rev])]
    else:
        nodes = [repo.lookup('.')]

    if good or bad or skip:
        if good:
            state['good'] += nodes
        elif bad:
            state['bad'] += nodes
        elif skip:
            state['skip'] += nodes
        hbisect.save_state(repo, state)

    if not check_state(state):
        return

    # actually bisect
    nodes, changesets, good = hbisect.bisect(repo.changelog, state)
    if extend:
        if not changesets:
            extendnode = extendbisectrange(nodes, good)
            if extendnode is not None:
                ui.write(_("Extending search to changeset %d:%s\n"
                         % (extendnode.rev(), extendnode)))
                if noupdate:
                    return
                cmdutil.bailifchanged(repo)
                return hg.clean(repo, extendnode.node())
        raise util.Abort(_("nothing to extend"))

    if changesets == 0:
        print_result(nodes, good)
    else:
        assert len(nodes) == 1 # only a single node can be tested next
        node = nodes[0]
        # compute the approximate number of remaining tests
        tests, size = 0, 2
        while size <= changesets:
            tests, size = tests + 1, size * 2
        rev = repo.changelog.rev(node)
        ui.write(_("Testing changeset %d:%s "
                   "(%d changesets remaining, ~%d tests)\n")
                 % (rev, short(node), changesets, tests))
        if not noupdate:
            cmdutil.bailifchanged(repo)
            return hg.clean(repo, node)

@command('bookmarks',
    [('f', 'force', False, _('force')),
    ('r', 'rev', '', _('revision'), _('REV')),
    ('d', 'delete', False, _('delete a given bookmark')),
    ('m', 'rename', '', _('rename a given bookmark'), _('NAME')),
    ('i', 'inactive', False, _('do not mark a new bookmark active'))],
    _('hg bookmarks [-f] [-d] [-i] [-m NAME] [-r REV] [NAME]'))
def bookmark(ui, repo, mark=None, rev=None, force=False, delete=False,
             rename=None, inactive=False):
    '''track a line of development with movable markers

    Bookmarks are pointers to certain commits that move when
    committing. Bookmarks are local. They can be renamed, copied and
    deleted. It is possible to use bookmark names in :hg:`merge` and
    :hg:`update` to merge and update respectively to a given bookmark.

    You can use :hg:`bookmark NAME` to set a bookmark on the working
    directory's parent revision with the given name. If you specify
    a revision using -r REV (where REV may be an existing bookmark),
    the bookmark is assigned to that revision.

    Bookmarks can be pushed and pulled between repositories (see :hg:`help
    push` and :hg:`help pull`). This requires both the local and remote
    repositories to support bookmarks. For versions prior to 1.8, this means
    the bookmarks extension must be enabled.
    '''
    hexfn = ui.debugflag and hex or short
    marks = repo._bookmarks
    cur   = repo.changectx('.').node()

    if rename:
        if rename not in marks:
            raise util.Abort(_("bookmark '%s' does not exist") % rename)
        if mark in marks and not force:
            raise util.Abort(_("bookmark '%s' already exists "
                               "(use -f to force)") % mark)
        if mark is None:
            raise util.Abort(_("new bookmark name required"))
        marks[mark] = marks[rename]
        if repo._bookmarkcurrent == rename and not inactive:
            bookmarks.setcurrent(repo, mark)
        del marks[rename]
        bookmarks.write(repo)
        return

    if delete:
        if mark is None:
            raise util.Abort(_("bookmark name required"))
        if mark not in marks:
            raise util.Abort(_("bookmark '%s' does not exist") % mark)
        if mark == repo._bookmarkcurrent:
            bookmarks.setcurrent(repo, None)
        del marks[mark]
        bookmarks.write(repo)
        return

    if mark is not None:
        if "\n" in mark:
            raise util.Abort(_("bookmark name cannot contain newlines"))
        mark = mark.strip()
        if not mark:
            raise util.Abort(_("bookmark names cannot consist entirely of "
                               "whitespace"))
        if inactive and mark == repo._bookmarkcurrent:
            bookmarks.setcurrent(repo, None)
            return
        if mark in marks and not force:
            raise util.Abort(_("bookmark '%s' already exists "
                               "(use -f to force)") % mark)
        if ((mark in repo.branchtags() or mark == repo.dirstate.branch())
            and not force):
            raise util.Abort(
                _("a bookmark cannot have the name of an existing branch"))
        if rev:
            marks[mark] = repo.lookup(rev)
        else:
            marks[mark] = repo.changectx('.').node()
        if not inactive and repo.changectx('.').node() == marks[mark]:
            bookmarks.setcurrent(repo, mark)
        bookmarks.write(repo)
        return

    if mark is None:
        if rev:
            raise util.Abort(_("bookmark name required"))
        if len(marks) == 0:
            ui.status(_("no bookmarks set\n"))
        else:
            for bmark, n in sorted(marks.iteritems()):
                current = repo._bookmarkcurrent
                if bmark == current and n == cur:
                    prefix, label = '*', 'bookmarks.current'
                else:
                    prefix, label = ' ', ''

                if ui.quiet:
                    ui.write("%s\n" % bmark, label=label)
                else:
                    ui.write(" %s %-25s %d:%s\n" % (
                        prefix, bmark, repo.changelog.rev(n), hexfn(n)),
                        label=label)
        return

@command('branch',
    [('f', 'force', None,
     _('set branch name even if it shadows an existing branch')),
    ('C', 'clean', None, _('reset branch name to parent branch name'))],
    _('[-fC] [NAME]'))
def branch(ui, repo, label=None, **opts):
    """set or show the current branch name

    With no argument, show the current branch name. With one argument,
    set the working directory branch name (the branch will not exist
    in the repository until the next commit). Standard practice
    recommends that primary development take place on the 'default'
    branch.

    Unless -f/--force is specified, branch will not let you set a
    branch name that already exists, even if it's inactive.

    Use -C/--clean to reset the working directory branch to that of
    the parent of the working directory, negating a previous branch
    change.

    Use the command :hg:`update` to switch to an existing branch. Use
    :hg:`commit --close-branch` to mark this branch as closed.

    .. note::

       Branch names are permanent. Use :hg:`bookmark` to create a
       light-weight bookmark instead. See :hg:`help glossary` for more
       information about named branches and bookmarks.

    Returns 0 on success.
    """

    if opts.get('clean'):
        label = repo[None].p1().branch()
        repo.dirstate.setbranch(label)
        ui.status(_('reset working directory to branch %s\n') % label)
    elif label:
        if not opts.get('force') and label in repo.branchtags():
            if label not in [p.branch() for p in repo.parents()]:
                raise util.Abort(_('a branch of the same name already exists'),
                                 # i18n: "it" refers to an existing branch
                                 hint=_("use 'hg update' to switch to it"))
        repo.dirstate.setbranch(label)
        ui.status(_('marked working directory as branch %s\n') % label)
    else:
        ui.write("%s\n" % repo.dirstate.branch())

@command('branches',
    [('a', 'active', False, _('show only branches that have unmerged heads')),
    ('c', 'closed', False, _('show normal and closed branches'))],
    _('[-ac]'))
def branches(ui, repo, active=False, closed=False):
    """list repository named branches

    List the repository's named branches, indicating which ones are
    inactive. If -c/--closed is specified, also list branches which have
    been marked closed (see :hg:`commit --close-branch`).

    If -a/--active is specified, only show active branches. A branch
    is considered active if it contains repository heads.

    Use the command :hg:`update` to switch to an existing branch.

    Returns 0.
    """

    hexfunc = ui.debugflag and hex or short
    activebranches = [repo[n].branch() for n in repo.heads()]
    def testactive(tag, node):
        realhead = tag in activebranches
        open = node in repo.branchheads(tag, closed=False)
        return realhead and open
    branches = sorted([(testactive(tag, node), repo.changelog.rev(node), tag)
                          for tag, node in repo.branchtags().items()],
                      reverse=True)

    for isactive, node, tag in branches:
        if (not active) or isactive:
            if ui.quiet:
                ui.write("%s\n" % tag)
            else:
                hn = repo.lookup(node)
                if isactive:
                    label = 'branches.active'
                    notice = ''
                elif hn not in repo.branchheads(tag, closed=False):
                    if not closed:
                        continue
                    label = 'branches.closed'
                    notice = _(' (closed)')
                else:
                    label = 'branches.inactive'
                    notice = _(' (inactive)')
                if tag == repo.dirstate.branch():
                    label = 'branches.current'
                rev = str(node).rjust(31 - encoding.colwidth(tag))
                rev = ui.label('%s:%s' % (rev, hexfunc(hn)), 'log.changeset')
                tag = ui.label(tag, label)
                ui.write("%s %s%s\n" % (tag, rev, notice))

@command('bundle',
    [('f', 'force', None, _('run even when the destination is unrelated')),
    ('r', 'rev', [], _('a changeset intended to be added to the destination'),
     _('REV')),
    ('b', 'branch', [], _('a specific branch you would like to bundle'),
     _('BRANCH')),
    ('', 'base', [],
     _('a base changeset assumed to be available at the destination'),
     _('REV')),
    ('a', 'all', None, _('bundle all changesets in the repository')),
    ('t', 'type', 'bzip2', _('bundle compression type to use'), _('TYPE')),
    ] + remoteopts,
    _('[-f] [-t TYPE] [-a] [-r REV]... [--base REV]... FILE [DEST]'))
def bundle(ui, repo, fname, dest=None, **opts):
    """create a changegroup file

    Generate a compressed changegroup file collecting changesets not
    known to be in another repository.

    If you omit the destination repository, then hg assumes the
    destination will have all the nodes you specify with --base
    parameters. To create a bundle containing all changesets, use
    -a/--all (or --base null).

    You can change compression method with the -t/--type option.
    The available compression methods are: none, bzip2, and
    gzip (by default, bundles are compressed using bzip2).

    The bundle file can then be transferred using conventional means
    and applied to another repository with the unbundle or pull
    command. This is useful when direct push and pull are not
    available or when exporting an entire repository is undesirable.

    Applying bundles preserves all changeset contents including
    permissions, copy/rename information, and revision history.

    Returns 0 on success, 1 if no changes found.
    """
    revs = None
    if 'rev' in opts:
        revs = scmutil.revrange(repo, opts['rev'])

    if opts.get('all'):
        base = ['null']
    else:
        base = scmutil.revrange(repo, opts.get('base'))
    if base:
        if dest:
            raise util.Abort(_("--base is incompatible with specifying "
                               "a destination"))
        common = [repo.lookup(rev) for rev in base]
        heads = revs and map(repo.lookup, revs) or revs
    else:
        dest = ui.expandpath(dest or 'default-push', dest or 'default')
        dest, branches = hg.parseurl(dest, opts.get('branch'))
        other = hg.peer(repo, opts, dest)
        revs, checkout = hg.addbranchrevs(repo, other, branches, revs)
        heads = revs and map(repo.lookup, revs) or revs
        common, outheads = discovery.findcommonoutgoing(repo, other,
                                                        onlyheads=heads,
                                                        force=opts.get('force'))

    cg = repo.getbundle('bundle', common=common, heads=heads)
    if not cg:
        ui.status(_("no changes found\n"))
        return 1

    bundletype = opts.get('type', 'bzip2').lower()
    btypes = {'none': 'HG10UN', 'bzip2': 'HG10BZ', 'gzip': 'HG10GZ'}
    bundletype = btypes.get(bundletype)
    if bundletype not in changegroup.bundletypes:
        raise util.Abort(_('unknown bundle type specified with --type'))

    changegroup.writebundle(cg, fname, bundletype)

@command('cat',
    [('o', 'output', '',
     _('print output to file with formatted name'), _('FORMAT')),
    ('r', 'rev', '', _('print the given revision'), _('REV')),
    ('', 'decode', None, _('apply any matching decode filter')),
    ] + walkopts,
    _('[OPTION]... FILE...'))
def cat(ui, repo, file1, *pats, **opts):
    """output the current or given revision of files

    Print the specified files as they were at the given revision. If
    no revision is given, the parent of the working directory is used,
    or tip if no revision is checked out.

    Output may be to a file, in which case the name of the file is
    given using a format string. The formatting rules are the same as
    for the export command, with the following additions:

    :``%s``: basename of file being printed
    :``%d``: dirname of file being printed, or '.' if in repository root
    :``%p``: root-relative path name of file being printed

    Returns 0 on success.
    """
    ctx = scmutil.revsingle(repo, opts.get('rev'))
    err = 1
    m = scmutil.match(ctx, (file1,) + pats, opts)
    for abs in ctx.walk(m):
        fp = cmdutil.makefileobj(repo, opts.get('output'), ctx.node(),
                                 pathname=abs)
        data = ctx[abs].data()
        if opts.get('decode'):
            data = repo.wwritedata(abs, data)
        fp.write(data)
        fp.close()
        err = 0
    return err

@command('^clone',
    [('U', 'noupdate', None,
     _('the clone will include an empty working copy (only a repository)')),
    ('u', 'updaterev', '', _('revision, tag or branch to check out'), _('REV')),
    ('r', 'rev', [], _('include the specified changeset'), _('REV')),
    ('b', 'branch', [], _('clone only the specified branch'), _('BRANCH')),
    ('', 'pull', None, _('use pull protocol to copy metadata')),
    ('', 'uncompressed', None, _('use uncompressed transfer (fast over LAN)')),
    ] + remoteopts,
    _('[OPTION]... SOURCE [DEST]'))
def clone(ui, source, dest=None, **opts):
    """make a copy of an existing repository

    Create a copy of an existing repository in a new directory.

    If no destination directory name is specified, it defaults to the
    basename of the source.

    The location of the source is added to the new repository's
    ``.hg/hgrc`` file, as the default to be used for future pulls.

    See :hg:`help urls` for valid source format details.

    It is possible to specify an ``ssh://`` URL as the destination, but no
    ``.hg/hgrc`` and working directory will be created on the remote side.
    Please see :hg:`help urls` for important details about ``ssh://`` URLs.

    A set of changesets (tags, or branch names) to pull may be specified
    by listing each changeset (tag, or branch name) with -r/--rev.
    If -r/--rev is used, the cloned repository will contain only a subset
    of the changesets of the source repository. Only the set of changesets
    defined by all -r/--rev options (including all their ancestors)
    will be pulled into the destination repository.
    No subsequent changesets (including subsequent tags) will be present
    in the destination.

    Using -r/--rev (or 'clone src#rev dest') implies --pull, even for
    local source repositories.

    For efficiency, hardlinks are used for cloning whenever the source
    and destination are on the same filesystem (note this applies only
    to the repository data, not to the working directory). Some
    filesystems, such as AFS, implement hardlinking incorrectly, but
    do not report errors. In these cases, use the --pull option to
    avoid hardlinking.

    In some cases, you can clone repositories and the working directory
    using full hardlinks with ::

      $ cp -al REPO REPOCLONE

    This is the fastest way to clone, but it is not always safe. The
    operation is not atomic (making sure REPO is not modified during
    the operation is up to you) and you have to make sure your editor
    breaks hardlinks (Emacs and most Linux Kernel tools do so). Also,
    this is not compatible with certain extensions that place their
    metadata under the .hg directory, such as mq.

    Mercurial will update the working directory to the first applicable
    revision from this list:

    a) null if -U or the source repository has no changesets
    b) if -u . and the source repository is local, the first parent of
       the source repository's working directory
    c) the changeset specified with -u (if a branch name, this means the
       latest head of that branch)
    d) the changeset specified with -r
    e) the tipmost head specified with -b
    f) the tipmost head specified with the url#branch source syntax
    g) the tipmost head of the default branch
    h) tip

    Returns 0 on success.
    """
    if opts.get('noupdate') and opts.get('updaterev'):
        raise util.Abort(_("cannot specify both --noupdate and --updaterev"))

    r = hg.clone(ui, opts, source, dest,
                 pull=opts.get('pull'),
                 stream=opts.get('uncompressed'),
                 rev=opts.get('rev'),
                 update=opts.get('updaterev') or not opts.get('noupdate'),
                 branch=opts.get('branch'))

    return r is None

@command('^commit|ci',
    [('A', 'addremove', None,
     _('mark new/missing files as added/removed before committing')),
    ('', 'close-branch', None,
     _('mark a branch as closed, hiding it from the branch list')),
    ] + walkopts + commitopts + commitopts2,
    _('[OPTION]... [FILE]...'))
def commit(ui, repo, *pats, **opts):
    """commit the specified files or all outstanding changes

    Commit changes to the given files into the repository. Unlike a
    centralized SCM, this operation is a local operation. See
    :hg:`push` for a way to actively distribute your changes.

    If a list of files is omitted, all changes reported by :hg:`status`
    will be committed.

    If you are committing the result of a merge, do not provide any
    filenames or -I/-X filters.

    If no commit message is specified, Mercurial starts your
    configured editor where you can enter a message. In case your
    commit fails, you will find a backup of your message in
    ``.hg/last-message.txt``.

    See :hg:`help dates` for a list of formats valid for -d/--date.

    Returns 0 on success, 1 if nothing changed.
    """
    extra = {}
    if opts.get('close_branch'):
        if repo['.'].node() not in repo.branchheads():
            # The topo heads set is included in the branch heads set of the
            # current branch, so it's sufficient to test branchheads
            raise util.Abort(_('can only close branch heads'))
        extra['close'] = 1
    e = cmdutil.commiteditor
    if opts.get('force_editor'):
        e = cmdutil.commitforceeditor

    def commitfunc(ui, repo, message, match, opts):
        return repo.commit(message, opts.get('user'), opts.get('date'), match,
                           editor=e, extra=extra)

    branch = repo[None].branch()
    bheads = repo.branchheads(branch)

    node = cmdutil.commit(ui, repo, commitfunc, pats, opts)
    if not node:
        stat = repo.status(match=scmutil.match(repo[None], pats, opts))
        if stat[3]:
            ui.status(_("nothing changed (%d missing files, see 'hg status')\n")
                      % len(stat[3]))
        else:
            ui.status(_("nothing changed\n"))
        return 1

    ctx = repo[node]
    parents = ctx.parents()

    if (bheads and node not in bheads and not
        [x for x in parents if x.node() in bheads and x.branch() == branch]):
        ui.status(_('created new head\n'))
        # The message is not printed for initial roots. For the other
        # changesets, it is printed in the following situations:
        #
        # Par column: for the 2 parents with ...
        #   N: null or no parent
        #   B: parent is on another named branch
        #   C: parent is a regular non head changeset
        #   H: parent was a branch head of the current branch
        # Msg column: whether we print "created new head" message
        # In the following, it is assumed that there already exists some
        # initial branch heads of the current branch, otherwise nothing is
        # printed anyway.
        #
        # Par Msg Comment
        # NN   y  additional topo root
        #
        # BN   y  additional branch root
        # CN   y  additional topo head
        # HN   n  usual case
        #
        # BB   y  weird additional branch root
        # CB   y  branch merge
        # HB   n  merge with named branch
        #
        # CC   y  additional head from merge
        # CH   n  merge with a head
        #
        # HH   n  head merge: head count decreases

    if not opts.get('close_branch'):
        for r in parents:
            if r.extra().get('close') and r.branch() == branch:
                ui.status(_('reopening closed branch head %d\n') % r)

    if ui.debugflag:
        ui.write(_('committed changeset %d:%s\n') % (int(ctx), ctx.hex()))
    elif ui.verbose:
        ui.write(_('committed changeset %d:%s\n') % (int(ctx), ctx))

@command('copy|cp',
    [('A', 'after', None, _('record a copy that has already occurred')),
    ('f', 'force', None, _('forcibly copy over an existing managed file')),
    ] + walkopts + dryrunopts,
    _('[OPTION]... [SOURCE]... DEST'))
def copy(ui, repo, *pats, **opts):
    """mark files as copied for the next commit

    Mark dest as having copies of source files. If dest is a
    directory, copies are put in that directory. If dest is a file,
    the source must be a single file.

    By default, this command copies the contents of files as they
    exist in the working directory. If invoked with -A/--after, the
    operation is recorded, but no copying is performed.

    This command takes effect with the next commit. To undo a copy
    before that, see :hg:`revert`.

    Returns 0 on success, 1 if errors are encountered.
    """
    wlock = repo.wlock(False)
    try:
        return cmdutil.copy(ui, repo, pats, opts)
    finally:
        wlock.release()

@command('debugancestor', [], _('[INDEX] REV1 REV2'))
def debugancestor(ui, repo, *args):
    """find the ancestor revision of two revisions in a given index"""
    if len(args) == 3:
        index, rev1, rev2 = args
        r = revlog.revlog(scmutil.opener(os.getcwd(), audit=False), index)
        lookup = r.lookup
    elif len(args) == 2:
        if not repo:
            raise util.Abort(_("there is no Mercurial repository here "
                               "(.hg not found)"))
        rev1, rev2 = args
        r = repo.changelog
        lookup = repo.lookup
    else:
        raise util.Abort(_('either two or three arguments required'))
    a = r.ancestor(lookup(rev1), lookup(rev2))
    ui.write("%d:%s\n" % (r.rev(a), hex(a)))

@command('debugbuilddag',
    [('m', 'mergeable-file', None, _('add single file mergeable changes')),
    ('o', 'overwritten-file', None, _('add single file all revs overwrite')),
    ('n', 'new-file', None, _('add new file at each rev'))],
    _('[OPTION]... [TEXT]'))
def debugbuilddag(ui, repo, text=None,
                  mergeable_file=False,
                  overwritten_file=False,
                  new_file=False):
    """builds a repo with a given DAG from scratch in the current empty repo

    The description of the DAG is read from stdin if not given on the
    command line.

    Elements:

     - "+n" is a linear run of n nodes based on the current default parent
     - "." is a single node based on the current default parent
     - "$" resets the default parent to null (implied at the start);
           otherwise the default parent is always the last node created
     - "<p" sets the default parent to the backref p
     - "*p" is a fork at parent p, which is a backref
     - "*p1/p2" is a merge of parents p1 and p2, which are backrefs
     - "/p2" is a merge of the preceding node and p2
     - ":tag" defines a local tag for the preceding node
     - "@branch" sets the named branch for subsequent nodes
     - "#...\\n" is a comment up to the end of the line

    Whitespace between the above elements is ignored.

    A backref is either

     - a number n, which references the node curr-n, where curr is the current
       node, or
     - the name of a local tag you placed earlier using ":tag", or
     - empty to denote the default parent.

    All string valued-elements are either strictly alphanumeric, or must
    be enclosed in double quotes ("..."), with "\\" as escape character.
    """

    if text is None:
        ui.status(_("reading DAG from stdin\n"))
        text = ui.fin.read()

    cl = repo.changelog
    if len(cl) > 0:
        raise util.Abort(_('repository is not empty'))

    # determine number of revs in DAG
    total = 0
    for type, data in dagparser.parsedag(text):
        if type == 'n':
            total += 1

    if mergeable_file:
        linesperrev = 2
        # make a file with k lines per rev
        initialmergedlines = [str(i) for i in xrange(0, total * linesperrev)]
        initialmergedlines.append("")

    tags = []

    tr = repo.transaction("builddag")
    try:

        at = -1
        atbranch = 'default'
        nodeids = []
        ui.progress(_('building'), 0, unit=_('revisions'), total=total)
        for type, data in dagparser.parsedag(text):
            if type == 'n':
                ui.note('node %s\n' % str(data))
                id, ps = data

                files = []
                fctxs = {}

                p2 = None
                if mergeable_file:
                    fn = "mf"
                    p1 = repo[ps[0]]
                    if len(ps) > 1:
                        p2 = repo[ps[1]]
                        pa = p1.ancestor(p2)
                        base, local, other = [x[fn].data() for x in pa, p1, p2]
                        m3 = simplemerge.Merge3Text(base, local, other)
                        ml = [l.strip() for l in m3.merge_lines()]
                        ml.append("")
                    elif at > 0:
                        ml = p1[fn].data().split("\n")
                    else:
                        ml = initialmergedlines
                    ml[id * linesperrev] += " r%i" % id
                    mergedtext = "\n".join(ml)
                    files.append(fn)
                    fctxs[fn] = context.memfilectx(fn, mergedtext)

                if overwritten_file:
                    fn = "of"
                    files.append(fn)
                    fctxs[fn] = context.memfilectx(fn, "r%i\n" % id)

                if new_file:
                    fn = "nf%i" % id
                    files.append(fn)
                    fctxs[fn] = context.memfilectx(fn, "r%i\n" % id)
                    if len(ps) > 1:
                        if not p2:
                            p2 = repo[ps[1]]
                        for fn in p2:
                            if fn.startswith("nf"):
                                files.append(fn)
                                fctxs[fn] = p2[fn]

                def fctxfn(repo, cx, path):
                    return fctxs.get(path)

                if len(ps) == 0 or ps[0] < 0:
                    pars = [None, None]
                elif len(ps) == 1:
                    pars = [nodeids[ps[0]], None]
                else:
                    pars = [nodeids[p] for p in ps]
                cx = context.memctx(repo, pars, "r%i" % id, files, fctxfn,
                                    date=(id, 0),
                                    user="debugbuilddag",
                                    extra={'branch': atbranch})
                nodeid = repo.commitctx(cx)
                nodeids.append(nodeid)
                at = id
            elif type == 'l':
                id, name = data
                ui.note('tag %s\n' % name)
                tags.append("%s %s\n" % (hex(repo.changelog.node(id)), name))
            elif type == 'a':
                ui.note('branch %s\n' % data)
                atbranch = data
            ui.progress(_('building'), id, unit=_('revisions'), total=total)
        tr.close()
    finally:
        ui.progress(_('building'), None)
        tr.release()

    if tags:
        repo.opener.write("localtags", "".join(tags))

@command('debugbundle', [('a', 'all', None, _('show all details'))], _('FILE'))
def debugbundle(ui, bundlepath, all=None, **opts):
    """lists the contents of a bundle"""
    f = url.open(ui, bundlepath)
    try:
        gen = changegroup.readbundle(f, bundlepath)
        if all:
            ui.write("format: id, p1, p2, cset, delta base, len(delta)\n")

            def showchunks(named):
                ui.write("\n%s\n" % named)
                chain = None
                while True:
                    chunkdata = gen.deltachunk(chain)
                    if not chunkdata:
                        break
                    node = chunkdata['node']
                    p1 = chunkdata['p1']
                    p2 = chunkdata['p2']
                    cs = chunkdata['cs']
                    deltabase = chunkdata['deltabase']
                    delta = chunkdata['delta']
                    ui.write("%s %s %s %s %s %s\n" %
                             (hex(node), hex(p1), hex(p2),
                              hex(cs), hex(deltabase), len(delta)))
                    chain = node

            chunkdata = gen.changelogheader()
            showchunks("changelog")
            chunkdata = gen.manifestheader()
            showchunks("manifest")
            while True:
                chunkdata = gen.filelogheader()
                if not chunkdata:
                    break
                fname = chunkdata['filename']
                showchunks(fname)
        else:
            chunkdata = gen.changelogheader()
            chain = None
            while True:
                chunkdata = gen.deltachunk(chain)
                if not chunkdata:
                    break
                node = chunkdata['node']
                ui.write("%s\n" % hex(node))
                chain = node
    finally:
        f.close()

@command('debugcheckstate', [], '')
def debugcheckstate(ui, repo):
    """validate the correctness of the current dirstate"""
    parent1, parent2 = repo.dirstate.parents()
    m1 = repo[parent1].manifest()
    m2 = repo[parent2].manifest()
    errors = 0
    for f in repo.dirstate:
        state = repo.dirstate[f]
        if state in "nr" and f not in m1:
            ui.warn(_("%s in state %s, but not in manifest1\n") % (f, state))
            errors += 1
        if state in "a" and f in m1:
            ui.warn(_("%s in state %s, but also in manifest1\n") % (f, state))
            errors += 1
        if state in "m" and f not in m1 and f not in m2:
            ui.warn(_("%s in state %s, but not in either manifest\n") %
                    (f, state))
            errors += 1
    for f in m1:
        state = repo.dirstate[f]
        if state not in "nrm":
            ui.warn(_("%s in manifest1, but listed as state %s") % (f, state))
            errors += 1
    if errors:
        error = _(".hg/dirstate inconsistent with current parent's manifest")
        raise util.Abort(error)

@command('debugcommands', [], _('[COMMAND]'))
def debugcommands(ui, cmd='', *args):
    """list all available commands and options"""
    for cmd, vals in sorted(table.iteritems()):
        cmd = cmd.split('|')[0].strip('^')
        opts = ', '.join([i[1] for i in vals[1]])
        ui.write('%s: %s\n' % (cmd, opts))

@command('debugcomplete',
    [('o', 'options', None, _('show the command options'))],
    _('[-o] CMD'))
def debugcomplete(ui, cmd='', **opts):
    """returns the completion list associated with the given command"""

    if opts.get('options'):
        options = []
        otables = [globalopts]
        if cmd:
            aliases, entry = cmdutil.findcmd(cmd, table, False)
            otables.append(entry[1])
        for t in otables:
            for o in t:
                if "(DEPRECATED)" in o[3]:
                    continue
                if o[0]:
                    options.append('-%s' % o[0])
                options.append('--%s' % o[1])
        ui.write("%s\n" % "\n".join(options))
        return

    cmdlist = cmdutil.findpossible(cmd, table)
    if ui.verbose:
        cmdlist = [' '.join(c[0]) for c in cmdlist.values()]
    ui.write("%s\n" % "\n".join(sorted(cmdlist)))

@command('debugdag',
    [('t', 'tags', None, _('use tags as labels')),
    ('b', 'branches', None, _('annotate with branch names')),
    ('', 'dots', None, _('use dots for runs')),
    ('s', 'spaces', None, _('separate elements by spaces'))],
    _('[OPTION]... [FILE [REV]...]'))
def debugdag(ui, repo, file_=None, *revs, **opts):
    """format the changelog or an index DAG as a concise textual description

    If you pass a revlog index, the revlog's DAG is emitted. If you list
    revision numbers, they get labelled in the output as rN.

    Otherwise, the changelog DAG of the current repo is emitted.
    """
    spaces = opts.get('spaces')
    dots = opts.get('dots')
    if file_:
        rlog = revlog.revlog(scmutil.opener(os.getcwd(), audit=False), file_)
        revs = set((int(r) for r in revs))
        def events():
            for r in rlog:
                yield 'n', (r, list(set(p for p in rlog.parentrevs(r) if p != -1)))
                if r in revs:
                    yield 'l', (r, "r%i" % r)
    elif repo:
        cl = repo.changelog
        tags = opts.get('tags')
        branches = opts.get('branches')
        if tags:
            labels = {}
            for l, n in repo.tags().items():
                labels.setdefault(cl.rev(n), []).append(l)
        def events():
            b = "default"
            for r in cl:
                if branches:
                    newb = cl.read(cl.node(r))[5]['branch']
                    if newb != b:
                        yield 'a', newb
                        b = newb
                yield 'n', (r, list(set(p for p in cl.parentrevs(r) if p != -1)))
                if tags:
                    ls = labels.get(r)
                    if ls:
                        for l in ls:
                            yield 'l', (r, l)
    else:
        raise util.Abort(_('need repo for changelog dag'))

    for line in dagparser.dagtextlines(events(),
                                       addspaces=spaces,
                                       wraplabels=True,
                                       wrapannotations=True,
                                       wrapnonlinear=dots,
                                       usedots=dots,
                                       maxlinewidth=70):
        ui.write(line)
        ui.write("\n")

@command('debugdata',
    [('c', 'changelog', False, _('open changelog')),
     ('m', 'manifest', False, _('open manifest'))],
    _('-c|-m|FILE REV'))
def debugdata(ui, repo, file_, rev = None, **opts):
    """dump the contents of a data file revision"""
    if opts.get('changelog') or opts.get('manifest'):
        file_, rev = None, file_
    elif rev is None:
        raise error.CommandError('debugdata', _('invalid arguments'))
    r = cmdutil.openrevlog(repo, 'debugdata', file_, opts)
    try:
        ui.write(r.revision(r.lookup(rev)))
    except KeyError:
        raise util.Abort(_('invalid revision identifier %s') % rev)

@command('debugdate',
    [('e', 'extended', None, _('try extended date formats'))],
    _('[-e] DATE [RANGE]'))
def debugdate(ui, date, range=None, **opts):
    """parse and display a date"""
    if opts["extended"]:
        d = util.parsedate(date, util.extendeddateformats)
    else:
        d = util.parsedate(date)
    ui.write("internal: %s %s\n" % d)
    ui.write("standard: %s\n" % util.datestr(d))
    if range:
        m = util.matchdate(range)
        ui.write("match: %s\n" % m(d[0]))

@command('debugdiscovery',
    [('', 'old', None, _('use old-style discovery')),
    ('', 'nonheads', None,
     _('use old-style discovery with non-heads included')),
    ] + remoteopts,
    _('[-l REV] [-r REV] [-b BRANCH]... [OTHER]'))
def debugdiscovery(ui, repo, remoteurl="default", **opts):
    """runs the changeset discovery protocol in isolation"""
    remoteurl, branches = hg.parseurl(ui.expandpath(remoteurl), opts.get('branch'))
    remote = hg.peer(repo, opts, remoteurl)
    ui.status(_('comparing with %s\n') % util.hidepassword(remoteurl))

    # make sure tests are repeatable
    random.seed(12323)

    def doit(localheads, remoteheads):
        if opts.get('old'):
            if localheads:
                raise util.Abort('cannot use localheads with old style discovery')
            common, _in, hds = treediscovery.findcommonincoming(repo, remote,
                                                                force=True)
            common = set(common)
            if not opts.get('nonheads'):
                ui.write("unpruned common: %s\n" % " ".join([short(n)
                                                            for n in common]))
                dag = dagutil.revlogdag(repo.changelog)
                all = dag.ancestorset(dag.internalizeall(common))
                common = dag.externalizeall(dag.headsetofconnecteds(all))
        else:
            common, any, hds = setdiscovery.findcommonheads(ui, repo, remote)
        common = set(common)
        rheads = set(hds)
        lheads = set(repo.heads())
        ui.write("common heads: %s\n" % " ".join([short(n) for n in common]))
        if lheads <= common:
            ui.write("local is subset\n")
        elif rheads <= common:
            ui.write("remote is subset\n")

    serverlogs = opts.get('serverlog')
    if serverlogs:
        for filename in serverlogs:
            logfile = open(filename, 'r')
            try:
                line = logfile.readline()
                while line:
                    parts = line.strip().split(';')
                    op = parts[1]
                    if op == 'cg':
                        pass
                    elif op == 'cgss':
                        doit(parts[2].split(' '), parts[3].split(' '))
                    elif op == 'unb':
                        doit(parts[3].split(' '), parts[2].split(' '))
                    line = logfile.readline()
            finally:
                logfile.close()

    else:
        remoterevs, _checkout = hg.addbranchrevs(repo, remote, branches,
                                                 opts.get('remote_head'))
        localrevs = opts.get('local_head')
        doit(localrevs, remoterevs)

@command('debugfileset', [], ('REVSPEC'))
def debugfileset(ui, repo, expr):
    '''parse and apply a fileset specification'''
    if ui.verbose:
        tree = fileset.parse(expr)[0]
        ui.note(tree, "\n")

    for f in fileset.getfileset(repo[None], expr):
        ui.write("%s\n" % f)

@command('debugfsinfo', [], _('[PATH]'))
def debugfsinfo(ui, path = "."):
    """show information detected about current filesystem"""
    util.writefile('.debugfsinfo', '')
    ui.write('exec: %s\n' % (util.checkexec(path) and 'yes' or 'no'))
    ui.write('symlink: %s\n' % (util.checklink(path) and 'yes' or 'no'))
    ui.write('case-sensitive: %s\n' % (util.checkcase('.debugfsinfo')
                                and 'yes' or 'no'))
    os.unlink('.debugfsinfo')

@command('debuggetbundle',
    [('H', 'head', [], _('id of head node'), _('ID')),
    ('C', 'common', [], _('id of common node'), _('ID')),
    ('t', 'type', 'bzip2', _('bundle compression type to use'), _('TYPE'))],
    _('REPO FILE [-H|-C ID]...'))
def debuggetbundle(ui, repopath, bundlepath, head=None, common=None, **opts):
    """retrieves a bundle from a repo

    Every ID must be a full-length hex node id string. Saves the bundle to the
    given file.
    """
    repo = hg.peer(ui, opts, repopath)
    if not repo.capable('getbundle'):
        raise util.Abort("getbundle() not supported by target repository")
    args = {}
    if common:
        args['common'] = [bin(s) for s in common]
    if head:
        args['heads'] = [bin(s) for s in head]
    bundle = repo.getbundle('debug', **args)

    bundletype = opts.get('type', 'bzip2').lower()
    btypes = {'none': 'HG10UN', 'bzip2': 'HG10BZ', 'gzip': 'HG10GZ'}
    bundletype = btypes.get(bundletype)
    if bundletype not in changegroup.bundletypes:
        raise util.Abort(_('unknown bundle type specified with --type'))
    changegroup.writebundle(bundle, bundlepath, bundletype)

@command('debugignore', [], '')
def debugignore(ui, repo, *values, **opts):
    """display the combined ignore pattern"""
    ignore = repo.dirstate._ignore
    includepat = getattr(ignore, 'includepat', None)
    if includepat is not None:
        ui.write("%s\n" % includepat)
    else:
        raise util.Abort(_("no ignore patterns found"))

@command('debugindex',
    [('c', 'changelog', False, _('open changelog')),
     ('m', 'manifest', False, _('open manifest')),
     ('f', 'format', 0, _('revlog format'), _('FORMAT'))],
    _('[-f FORMAT] -c|-m|FILE'))
def debugindex(ui, repo, file_ = None, **opts):
    """dump the contents of an index file"""
    r = cmdutil.openrevlog(repo, 'debugindex', file_, opts)
    format = opts.get('format', 0)
    if format not in (0, 1):
        raise util.Abort(_("unknown format %d") % format)

    generaldelta = r.version & revlog.REVLOGGENERALDELTA
    if generaldelta:
        basehdr = ' delta'
    else:
        basehdr = '  base'

    if format == 0:
        ui.write("   rev    offset  length " + basehdr + " linkrev"
                 " nodeid       p1           p2\n")
    elif format == 1:
        ui.write("   rev flag   offset   length"
                 "     size " + basehdr + "   link     p1     p2       nodeid\n")

    for i in r:
        node = r.node(i)
        if generaldelta:
            base = r.deltaparent(i)
        else:
            base = r.chainbase(i)
        if format == 0:
            try:
                pp = r.parents(node)
            except:
                pp = [nullid, nullid]
            ui.write("% 6d % 9d % 7d % 6d % 7d %s %s %s\n" % (
                    i, r.start(i), r.length(i), base, r.linkrev(i),
                    short(node), short(pp[0]), short(pp[1])))
        elif format == 1:
            pr = r.parentrevs(i)
            ui.write("% 6d %04x % 8d % 8d % 8d % 6d % 6d % 6d % 6d %s\n" % (
                    i, r.flags(i), r.start(i), r.length(i), r.rawsize(i),
                    base, r.linkrev(i), pr[0], pr[1], short(node)))

@command('debugindexdot', [], _('FILE'))
def debugindexdot(ui, repo, file_):
    """dump an index DAG as a graphviz dot file"""
    r = None
    if repo:
        filelog = repo.file(file_)
        if len(filelog):
            r = filelog
    if not r:
        r = revlog.revlog(scmutil.opener(os.getcwd(), audit=False), file_)
    ui.write("digraph G {\n")
    for i in r:
        node = r.node(i)
        pp = r.parents(node)
        ui.write("\t%d -> %d\n" % (r.rev(pp[0]), i))
        if pp[1] != nullid:
            ui.write("\t%d -> %d\n" % (r.rev(pp[1]), i))
    ui.write("}\n")

@command('debuginstall', [], '')
def debuginstall(ui):
    '''test Mercurial installation

    Returns 0 on success.
    '''

    def writetemp(contents):
        (fd, name) = tempfile.mkstemp(prefix="hg-debuginstall-")
        f = os.fdopen(fd, "wb")
        f.write(contents)
        f.close()
        return name

    problems = 0

    # encoding
    ui.status(_("Checking encoding (%s)...\n") % encoding.encoding)
    try:
        encoding.fromlocal("test")
    except util.Abort, inst:
        ui.write(" %s\n" % inst)
        ui.write(_(" (check that your locale is properly set)\n"))
        problems += 1

    # compiled modules
    ui.status(_("Checking installed modules (%s)...\n")
              % os.path.dirname(__file__))
    try:
        import bdiff, mpatch, base85, osutil
    except Exception, inst:
        ui.write(" %s\n" % inst)
        ui.write(_(" One or more extensions could not be found"))
        ui.write(_(" (check that you compiled the extensions)\n"))
        problems += 1

    # templates
    ui.status(_("Checking templates...\n"))
    try:
        import templater
        templater.templater(templater.templatepath("map-cmdline.default"))
    except Exception, inst:
        ui.write(" %s\n" % inst)
        ui.write(_(" (templates seem to have been installed incorrectly)\n"))
        problems += 1

    # editor
    ui.status(_("Checking commit editor...\n"))
    editor = ui.geteditor()
    cmdpath = util.findexe(editor) or util.findexe(editor.split()[0])
    if not cmdpath:
        if editor == 'vi':
            ui.write(_(" No commit editor set and can't find vi in PATH\n"))
            ui.write(_(" (specify a commit editor in your configuration"
                       " file)\n"))
        else:
            ui.write(_(" Can't find editor '%s' in PATH\n") % editor)
            ui.write(_(" (specify a commit editor in your configuration"
                       " file)\n"))
            problems += 1

    # check username
    ui.status(_("Checking username...\n"))
    try:
        ui.username()
    except util.Abort, e:
        ui.write(" %s\n" % e)
        ui.write(_(" (specify a username in your configuration file)\n"))
        problems += 1

    if not problems:
        ui.status(_("No problems detected\n"))
    else:
        ui.write(_("%s problems detected,"
                   " please check your install!\n") % problems)

    return problems

@command('debugknown', [], _('REPO ID...'))
def debugknown(ui, repopath, *ids, **opts):
    """test whether node ids are known to a repo

    Every ID must be a full-length hex node id string. Returns a list of 0s and 1s
    indicating unknown/known.
    """
    repo = hg.peer(ui, opts, repopath)
    if not repo.capable('known'):
        raise util.Abort("known() not supported by target repository")
    flags = repo.known([bin(s) for s in ids])
    ui.write("%s\n" % ("".join([f and "1" or "0" for f in flags])))

@command('debugpushkey', [], _('REPO NAMESPACE [KEY OLD NEW]'))
def debugpushkey(ui, repopath, namespace, *keyinfo, **opts):
    '''access the pushkey key/value protocol

    With two args, list the keys in the given namespace.

    With five args, set a key to new if it currently is set to old.
    Reports success or failure.
    '''

    target = hg.peer(ui, {}, repopath)
    if keyinfo:
        key, old, new = keyinfo
        r = target.pushkey(namespace, key, old, new)
        ui.status(str(r) + '\n')
        return not r
    else:
        for k, v in target.listkeys(namespace).iteritems():
            ui.write("%s\t%s\n" % (k.encode('string-escape'),
                                   v.encode('string-escape')))

@command('debugrebuildstate',
    [('r', 'rev', '', _('revision to rebuild to'), _('REV'))],
    _('[-r REV] [REV]'))
def debugrebuildstate(ui, repo, rev="tip"):
    """rebuild the dirstate as it would look like for the given revision"""
    ctx = scmutil.revsingle(repo, rev)
    wlock = repo.wlock()
    try:
        repo.dirstate.rebuild(ctx.node(), ctx.manifest())
    finally:
        wlock.release()

@command('debugrename',
    [('r', 'rev', '', _('revision to debug'), _('REV'))],
    _('[-r REV] FILE'))
def debugrename(ui, repo, file1, *pats, **opts):
    """dump rename information"""

    ctx = scmutil.revsingle(repo, opts.get('rev'))
    m = scmutil.match(ctx, (file1,) + pats, opts)
    for abs in ctx.walk(m):
        fctx = ctx[abs]
        o = fctx.filelog().renamed(fctx.filenode())
        rel = m.rel(abs)
        if o:
            ui.write(_("%s renamed from %s:%s\n") % (rel, o[0], hex(o[1])))
        else:
            ui.write(_("%s not renamed\n") % rel)

@command('debugrevlog',
    [('c', 'changelog', False, _('open changelog')),
     ('m', 'manifest', False, _('open manifest')),
     ('d', 'dump', False, _('dump index data'))],
     _('-c|-m|FILE'))
def debugrevlog(ui, repo, file_ = None, **opts):
    """show data and statistics about a revlog"""
    r = cmdutil.openrevlog(repo, 'debugrevlog', file_, opts)

    if opts.get("dump"):
        numrevs = len(r)
        ui.write("# rev p1rev p2rev start end deltastart base p1 p2"
                 " rawsize totalsize compression heads\n")
        ts = 0
        heads = set()
        for rev in xrange(numrevs):
            dbase = r.deltaparent(rev)
            if dbase == -1:
                dbase = rev
            cbase = r.chainbase(rev)
            p1, p2 = r.parentrevs(rev)
            rs = r.rawsize(rev)
            ts = ts + rs
            heads -= set(r.parentrevs(rev))
            heads.add(rev)
            ui.write("%d %d %d %d %d %d %d %d %d %d %d %d %d\n" %
                     (rev, p1, p2, r.start(rev), r.end(rev),
                      r.start(dbase), r.start(cbase),
                      r.start(p1), r.start(p2),
                      rs, ts, ts / r.end(rev), len(heads)))
        return 0

    v = r.version
    format = v & 0xFFFF
    flags = []
    gdelta = False
    if v & revlog.REVLOGNGINLINEDATA:
        flags.append('inline')
    if v & revlog.REVLOGGENERALDELTA:
        gdelta = True
        flags.append('generaldelta')
    if not flags:
        flags = ['(none)']

    nummerges = 0
    numfull = 0
    numprev = 0
    nump1 = 0
    nump2 = 0
    numother = 0
    nump1prev = 0
    nump2prev = 0
    chainlengths = []

    datasize = [None, 0, 0L]
    fullsize = [None, 0, 0L]
    deltasize = [None, 0, 0L]

    def addsize(size, l):
        if l[0] is None or size < l[0]:
            l[0] = size
        if size > l[1]:
            l[1] = size
        l[2] += size

    numrevs = len(r)
    for rev in xrange(numrevs):
        p1, p2 = r.parentrevs(rev)
        delta = r.deltaparent(rev)
        if format > 0:
            addsize(r.rawsize(rev), datasize)
        if p2 != nullrev:
            nummerges += 1
        size = r.length(rev)
        if delta == nullrev:
            chainlengths.append(0)
            numfull += 1
            addsize(size, fullsize)
        else:
            chainlengths.append(chainlengths[delta] + 1)
            addsize(size, deltasize)
            if delta == rev - 1:
                numprev += 1
                if delta == p1:
                    nump1prev += 1
                elif delta == p2:
                    nump2prev += 1
            elif delta == p1:
                nump1 += 1
            elif delta == p2:
                nump2 += 1
            elif delta != nullrev:
                numother += 1

    numdeltas = numrevs - numfull
    numoprev = numprev - nump1prev - nump2prev
    totalrawsize = datasize[2]
    datasize[2] /= numrevs
    fulltotal = fullsize[2]
    fullsize[2] /= numfull
    deltatotal = deltasize[2]
    deltasize[2] /= numrevs - numfull
    totalsize = fulltotal + deltatotal
    avgchainlen = sum(chainlengths) / numrevs
    compratio = totalrawsize / totalsize

    basedfmtstr = '%%%dd\n'
    basepcfmtstr = '%%%dd %s(%%5.2f%%%%)\n'

    def dfmtstr(max):
        return basedfmtstr % len(str(max))
    def pcfmtstr(max, padding=0):
        return basepcfmtstr % (len(str(max)), ' ' * padding)

    def pcfmt(value, total):
        return (value, 100 * float(value) / total)

    ui.write('format : %d\n' % format)
    ui.write('flags  : %s\n' % ', '.join(flags))

    ui.write('\n')
    fmt = pcfmtstr(totalsize)
    fmt2 = dfmtstr(totalsize)
    ui.write('revisions     : ' + fmt2 % numrevs)
    ui.write('    merges    : ' + fmt % pcfmt(nummerges, numrevs))
    ui.write('    normal    : ' + fmt % pcfmt(numrevs - nummerges, numrevs))
    ui.write('revisions     : ' + fmt2 % numrevs)
    ui.write('    full      : ' + fmt % pcfmt(numfull, numrevs))
    ui.write('    deltas    : ' + fmt % pcfmt(numdeltas, numrevs))
    ui.write('revision size : ' + fmt2 % totalsize)
    ui.write('    full      : ' + fmt % pcfmt(fulltotal, totalsize))
    ui.write('    deltas    : ' + fmt % pcfmt(deltatotal, totalsize))

    ui.write('\n')
    fmt = dfmtstr(max(avgchainlen, compratio))
    ui.write('avg chain length  : ' + fmt % avgchainlen)
    ui.write('compression ratio : ' + fmt % compratio)

    if format > 0:
        ui.write('\n')
        ui.write('uncompressed data size (min/max/avg) : %d / %d / %d\n'
                 % tuple(datasize))
    ui.write('full revision size (min/max/avg)     : %d / %d / %d\n'
             % tuple(fullsize))
    ui.write('delta size (min/max/avg)             : %d / %d / %d\n'
             % tuple(deltasize))

    if numdeltas > 0:
        ui.write('\n')
        fmt = pcfmtstr(numdeltas)
        fmt2 = pcfmtstr(numdeltas, 4)
        ui.write('deltas against prev  : ' + fmt % pcfmt(numprev, numdeltas))
        if numprev > 0:
            ui.write('    where prev = p1  : ' + fmt2 % pcfmt(nump1prev, numprev))
            ui.write('    where prev = p2  : ' + fmt2 % pcfmt(nump2prev, numprev))
            ui.write('    other            : ' + fmt2 % pcfmt(numoprev, numprev))
        if gdelta:
            ui.write('deltas against p1    : ' + fmt % pcfmt(nump1, numdeltas))
            ui.write('deltas against p2    : ' + fmt % pcfmt(nump2, numdeltas))
            ui.write('deltas against other : ' + fmt % pcfmt(numother, numdeltas))

@command('debugrevspec', [], ('REVSPEC'))
def debugrevspec(ui, repo, expr):
    '''parse and apply a revision specification'''
    if ui.verbose:
        tree = revset.parse(expr)[0]
        ui.note(tree, "\n")
        newtree = revset.findaliases(ui, tree)
        if newtree != tree:
            ui.note(newtree, "\n")
    func = revset.match(ui, expr)
    for c in func(repo, range(len(repo))):
        ui.write("%s\n" % c)

@command('debugsetparents', [], _('REV1 [REV2]'))
def debugsetparents(ui, repo, rev1, rev2=None):
    """manually set the parents of the current working directory

    This is useful for writing repository conversion tools, but should
    be used with care.

    Returns 0 on success.
    """

    r1 = scmutil.revsingle(repo, rev1).node()
    r2 = scmutil.revsingle(repo, rev2, 'null').node()

    wlock = repo.wlock()
    try:
        repo.dirstate.setparents(r1, r2)
    finally:
        wlock.release()

@command('debugstate',
    [('', 'nodates', None, _('do not display the saved mtime')),
    ('', 'datesort', None, _('sort by saved mtime'))],
    _('[OPTION]...'))
def debugstate(ui, repo, nodates=None, datesort=None):
    """show the contents of the current dirstate"""
    timestr = ""
    showdate = not nodates
    if datesort:
        keyfunc = lambda x: (x[1][3], x[0]) # sort by mtime, then by filename
    else:
        keyfunc = None # sort by filename
    for file_, ent in sorted(repo.dirstate._map.iteritems(), key=keyfunc):
        if showdate:
            if ent[3] == -1:
                # Pad or slice to locale representation
                locale_len = len(time.strftime("%Y-%m-%d %H:%M:%S ",
                                               time.localtime(0)))
                timestr = 'unset'
                timestr = (timestr[:locale_len] +
                           ' ' * (locale_len - len(timestr)))
            else:
                timestr = time.strftime("%Y-%m-%d %H:%M:%S ",
                                        time.localtime(ent[3]))
        if ent[1] & 020000:
            mode = 'lnk'
        else:
            mode = '%3o' % (ent[1] & 0777)
        ui.write("%c %s %10d %s%s\n" % (ent[0], mode, ent[2], timestr, file_))
    for f in repo.dirstate.copies():
        ui.write(_("copy: %s -> %s\n") % (repo.dirstate.copied(f), f))

@command('debugsub',
    [('r', 'rev', '',
     _('revision to check'), _('REV'))],
    _('[-r REV] [REV]'))
def debugsub(ui, repo, rev=None):
    ctx = scmutil.revsingle(repo, rev, None)
    for k, v in sorted(ctx.substate.items()):
        ui.write('path %s\n' % k)
        ui.write(' source   %s\n' % v[0])
        ui.write(' revision %s\n' % v[1])

@command('debugwalk', walkopts, _('[OPTION]... [FILE]...'))
def debugwalk(ui, repo, *pats, **opts):
    """show how files match on given patterns"""
    m = scmutil.match(repo[None], pats, opts)
    items = list(repo.walk(m))
    if not items:
        return
    fmt = 'f  %%-%ds  %%-%ds  %%s' % (
        max([len(abs) for abs in items]),
        max([len(m.rel(abs)) for abs in items]))
    for abs in items:
        line = fmt % (abs, m.rel(abs), m.exact(abs) and 'exact' or '')
        ui.write("%s\n" % line.rstrip())

@command('debugwireargs',
    [('', 'three', '', 'three'),
    ('', 'four', '', 'four'),
    ('', 'five', '', 'five'),
    ] + remoteopts,
    _('REPO [OPTIONS]... [ONE [TWO]]'))
def debugwireargs(ui, repopath, *vals, **opts):
    repo = hg.peer(ui, opts, repopath)
    for opt in remoteopts:
        del opts[opt[1]]
    args = {}
    for k, v in opts.iteritems():
        if v:
            args[k] = v
    # run twice to check that we don't mess up the stream for the next command
    res1 = repo.debugwireargs(*vals, **args)
    res2 = repo.debugwireargs(*vals, **args)
    ui.write("%s\n" % res1)
    if res1 != res2:
        ui.warn("%s\n" % res2)

@command('^diff',
    [('r', 'rev', [], _('revision'), _('REV')),
    ('c', 'change', '', _('change made by revision'), _('REV'))
    ] + diffopts + diffopts2 + walkopts + subrepoopts,
    _('[OPTION]... ([-c REV] | [-r REV1 [-r REV2]]) [FILE]...'))
def diff(ui, repo, *pats, **opts):
    """diff repository (or selected files)

    Show differences between revisions for the specified files.

    Differences between files are shown using the unified diff format.

    .. note::
       diff may generate unexpected results for merges, as it will
       default to comparing against the working directory's first
       parent changeset if no revisions are specified.

    When two revision arguments are given, then changes are shown
    between those revisions. If only one revision is specified then
    that revision is compared to the working directory, and, when no
    revisions are specified, the working directory files are compared
    to its parent.

    Alternatively you can specify -c/--change with a revision to see
    the changes in that changeset relative to its first parent.

    Without the -a/--text option, diff will avoid generating diffs of
    files it detects as binary. With -a, diff will generate a diff
    anyway, probably with undesirable results.

    Use the -g/--git option to generate diffs in the git extended diff
    format. For more information, read :hg:`help diffs`.

    Returns 0 on success.
    """

    revs = opts.get('rev')
    change = opts.get('change')
    stat = opts.get('stat')
    reverse = opts.get('reverse')

    if revs and change:
        msg = _('cannot specify --rev and --change at the same time')
        raise util.Abort(msg)
    elif change:
        node2 = scmutil.revsingle(repo, change, None).node()
        node1 = repo[node2].p1().node()
    else:
        node1, node2 = scmutil.revpair(repo, revs)

    if reverse:
        node1, node2 = node2, node1

    diffopts = patch.diffopts(ui, opts)
    m = scmutil.match(repo[node2], pats, opts)
    cmdutil.diffordiffstat(ui, repo, diffopts, node1, node2, m, stat=stat,
                           listsubrepos=opts.get('subrepos'))

@command('^export',
    [('o', 'output', '',
     _('print output to file with formatted name'), _('FORMAT')),
    ('', 'switch-parent', None, _('diff against the second parent')),
    ('r', 'rev', [], _('revisions to export'), _('REV')),
    ] + diffopts,
    _('[OPTION]... [-o OUTFILESPEC] REV...'))
def export(ui, repo, *changesets, **opts):
    """dump the header and diffs for one or more changesets

    Print the changeset header and diffs for one or more revisions.

    The information shown in the changeset header is: author, date,
    branch name (if non-default), changeset hash, parent(s) and commit
    comment.

    .. note::
       export may generate unexpected diff output for merge
       changesets, as it will compare the merge changeset against its
       first parent only.

    Output may be to a file, in which case the name of the file is
    given using a format string. The formatting rules are as follows:

    :``%%``: literal "%" character
    :``%H``: changeset hash (40 hexadecimal digits)
    :``%N``: number of patches being generated
    :``%R``: changeset revision number
    :``%b``: basename of the exporting repository
    :``%h``: short-form changeset hash (12 hexadecimal digits)
    :``%m``: first line of the commit message (only alphanumeric characters)
    :``%n``: zero-padded sequence number, starting at 1
    :``%r``: zero-padded changeset revision number

    Without the -a/--text option, export will avoid generating diffs
    of files it detects as binary. With -a, export will generate a
    diff anyway, probably with undesirable results.

    Use the -g/--git option to generate diffs in the git extended diff
    format. See :hg:`help diffs` for more information.

    With the --switch-parent option, the diff will be against the
    second parent. It can be useful to review a merge.

    Returns 0 on success.
    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        raise util.Abort(_("export requires at least one changeset"))
    revs = scmutil.revrange(repo, changesets)
    if len(revs) > 1:
        ui.note(_('exporting patches:\n'))
    else:
        ui.note(_('exporting patch:\n'))
    cmdutil.export(repo, revs, template=opts.get('output'),
                 switch_parent=opts.get('switch_parent'),
                 opts=patch.diffopts(ui, opts))

@command('^forget', walkopts, _('[OPTION]... FILE...'))
def forget(ui, repo, *pats, **opts):
    """forget the specified files on the next commit

    Mark the specified files so they will no longer be tracked
    after the next commit.

    This only removes files from the current branch, not from the
    entire project history, and it does not delete them from the
    working directory.

    To undo a forget before the next commit, see :hg:`add`.

    Returns 0 on success.
    """

    if not pats:
        raise util.Abort(_('no files specified'))

    m = scmutil.match(repo[None], pats, opts)
    s = repo.status(match=m, clean=True)
    forget = sorted(s[0] + s[1] + s[3] + s[6])
    errs = 0

    for f in m.files():
        if f not in repo.dirstate and not os.path.isdir(m.rel(f)):
            if os.path.exists(m.rel(f)):
                ui.warn(_('not removing %s: file is already untracked\n')
                        % m.rel(f))
            errs = 1

    for f in forget:
        if ui.verbose or not m.exact(f):
            ui.status(_('removing %s\n') % m.rel(f))

    repo[None].forget(forget)
    return errs

@command('grep',
    [('0', 'print0', None, _('end fields with NUL')),
    ('', 'all', None, _('print all revisions that match')),
    ('a', 'text', None, _('treat all files as text')),
    ('f', 'follow', None,
     _('follow changeset history,'
       ' or file history across copies and renames')),
    ('i', 'ignore-case', None, _('ignore case when matching')),
    ('l', 'files-with-matches', None,
     _('print only filenames and revisions that match')),
    ('n', 'line-number', None, _('print matching line numbers')),
    ('r', 'rev', [],
     _('only search files changed within revision range'), _('REV')),
    ('u', 'user', None, _('list the author (long with -v)')),
    ('d', 'date', None, _('list the date (short with -q)')),
    ] + walkopts,
    _('[OPTION]... PATTERN [FILE]...'))
def grep(ui, repo, pattern, *pats, **opts):
    """search for a pattern in specified files and revisions

    Search revisions of files for a regular expression.

    This command behaves differently than Unix grep. It only accepts
    Python/Perl regexps. It searches repository history, not the
    working directory. It always prints the revision number in which a
    match appears.

    By default, grep only prints output for the first revision of a
    file in which it finds a match. To get it to print every revision
    that contains a change in match status ("-" for a match that
    becomes a non-match, or "+" for a non-match that becomes a match),
    use the --all flag.

    Returns 0 if a match is found, 1 otherwise.
    """
    reflags = 0
    if opts.get('ignore_case'):
        reflags |= re.I
    try:
        regexp = re.compile(pattern, reflags)
    except re.error, inst:
        ui.warn(_("grep: invalid match pattern: %s\n") % inst)
        return 1
    sep, eol = ':', '\n'
    if opts.get('print0'):
        sep = eol = '\0'

    getfile = util.lrucachefunc(repo.file)

    def matchlines(body):
        begin = 0
        linenum = 0
        while True:
            match = regexp.search(body, begin)
            if not match:
                break
            mstart, mend = match.span()
            linenum += body.count('\n', begin, mstart) + 1
            lstart = body.rfind('\n', begin, mstart) + 1 or begin
            begin = body.find('\n', mend) + 1 or len(body)
            lend = begin - 1
            yield linenum, mstart - lstart, mend - lstart, body[lstart:lend]

    class linestate(object):
        def __init__(self, line, linenum, colstart, colend):
            self.line = line
            self.linenum = linenum
            self.colstart = colstart
            self.colend = colend

        def __hash__(self):
            return hash((self.linenum, self.line))

        def __eq__(self, other):
            return self.line == other.line

    matches = {}
    copies = {}
    def grepbody(fn, rev, body):
        matches[rev].setdefault(fn, [])
        m = matches[rev][fn]
        for lnum, cstart, cend, line in matchlines(body):
            s = linestate(line, lnum, cstart, cend)
            m.append(s)

    def difflinestates(a, b):
        sm = difflib.SequenceMatcher(None, a, b)
        for tag, alo, ahi, blo, bhi in sm.get_opcodes():
            if tag == 'insert':
                for i in xrange(blo, bhi):
                    yield ('+', b[i])
            elif tag == 'delete':
                for i in xrange(alo, ahi):
                    yield ('-', a[i])
            elif tag == 'replace':
                for i in xrange(alo, ahi):
                    yield ('-', a[i])
                for i in xrange(blo, bhi):
                    yield ('+', b[i])

    def display(fn, ctx, pstates, states):
        rev = ctx.rev()
        datefunc = ui.quiet and util.shortdate or util.datestr
        found = False
        filerevmatches = {}
        def binary():
            flog = getfile(fn)
            return util.binary(flog.read(ctx.filenode(fn)))

        if opts.get('all'):
            iter = difflinestates(pstates, states)
        else:
            iter = [('', l) for l in states]
        for change, l in iter:
            cols = [fn, str(rev)]
            before, match, after = None, None, None
            if opts.get('line_number'):
                cols.append(str(l.linenum))
            if opts.get('all'):
                cols.append(change)
            if opts.get('user'):
                cols.append(ui.shortuser(ctx.user()))
            if opts.get('date'):
                cols.append(datefunc(ctx.date()))
            if opts.get('files_with_matches'):
                c = (fn, rev)
                if c in filerevmatches:
                    continue
                filerevmatches[c] = 1
            else:
                before = l.line[:l.colstart]
                match = l.line[l.colstart:l.colend]
                after = l.line[l.colend:]
            ui.write(sep.join(cols))
            if before is not None:
                if not opts.get('text') and binary():
                    ui.write(sep + " Binary file matches")
                else:
                    ui.write(sep + before)
                    ui.write(match, label='grep.match')
                    ui.write(after)
            ui.write(eol)
            found = True
        return found

    skip = {}
    revfiles = {}
    matchfn = scmutil.match(repo[None], pats, opts)
    found = False
    follow = opts.get('follow')

    def prep(ctx, fns):
        rev = ctx.rev()
        pctx = ctx.p1()
        parent = pctx.rev()
        matches.setdefault(rev, {})
        matches.setdefault(parent, {})
        files = revfiles.setdefault(rev, [])
        for fn in fns:
            flog = getfile(fn)
            try:
                fnode = ctx.filenode(fn)
            except error.LookupError:
                continue

            copied = flog.renamed(fnode)
            copy = follow and copied and copied[0]
            if copy:
                copies.setdefault(rev, {})[fn] = copy
            if fn in skip:
                if copy:
                    skip[copy] = True
                continue
            files.append(fn)

            if fn not in matches[rev]:
                grepbody(fn, rev, flog.read(fnode))

            pfn = copy or fn
            if pfn not in matches[parent]:
                try:
                    fnode = pctx.filenode(pfn)
                    grepbody(pfn, parent, flog.read(fnode))
                except error.LookupError:
                    pass

    for ctx in cmdutil.walkchangerevs(repo, matchfn, opts, prep):
        rev = ctx.rev()
        parent = ctx.p1().rev()
        for fn in sorted(revfiles.get(rev, [])):
            states = matches[rev][fn]
            copy = copies.get(rev, {}).get(fn)
            if fn in skip:
                if copy:
                    skip[copy] = True
                continue
            pstates = matches.get(parent, {}).get(copy or fn, [])
            if pstates or states:
                r = display(fn, ctx, pstates, states)
                found = found or r
                if r and not opts.get('all'):
                    skip[fn] = True
                    if copy:
                        skip[copy] = True
        del matches[rev]
        del revfiles[rev]

    return not found

@command('heads',
    [('r', 'rev', '',
     _('show only heads which are descendants of STARTREV'), _('STARTREV')),
    ('t', 'topo', False, _('show topological heads only')),
    ('a', 'active', False, _('show active branchheads only (DEPRECATED)')),
    ('c', 'closed', False, _('show normal and closed branch heads')),
    ] + templateopts,
    _('[-ac] [-r STARTREV] [REV]...'))
def heads(ui, repo, *branchrevs, **opts):
    """show current repository heads or show branch heads

    With no arguments, show all repository branch heads.

    Repository "heads" are changesets with no child changesets. They are
    where development generally takes place and are the usual targets
    for update and merge operations. Branch heads are changesets that have
    no child changeset on the same branch.

    If one or more REVs are given, only branch heads on the branches
    associated with the specified changesets are shown. This means
    that you can use :hg:`heads foo` to see the heads on a branch
    named ``foo``.

    If -c/--closed is specified, also show branch heads marked closed
    (see :hg:`commit --close-branch`).

    If STARTREV is specified, only those heads that are descendants of
    STARTREV will be displayed.

    If -t/--topo is specified, named branch mechanics will be ignored and only
    changesets without children will be shown.

    Returns 0 if matching heads are found, 1 if not.
    """

    start = None
    if 'rev' in opts:
        start = scmutil.revsingle(repo, opts['rev'], None).node()

    if opts.get('topo'):
        heads = [repo[h] for h in repo.heads(start)]
    else:
        heads = []
        for branch in repo.branchmap():
            heads += repo.branchheads(branch, start, opts.get('closed'))
        heads = [repo[h] for h in heads]

    if branchrevs:
        branches = set(repo[br].branch() for br in branchrevs)
        heads = [h for h in heads if h.branch() in branches]

    if opts.get('active') and branchrevs:
        dagheads = repo.heads(start)
        heads = [h for h in heads if h.node() in dagheads]

    if branchrevs:
        haveheads = set(h.branch() for h in heads)
        if branches - haveheads:
            headless = ', '.join(b for b in branches - haveheads)
            msg = _('no open branch heads found on branches %s')
            if opts.get('rev'):
                msg += _(' (started at %s)' % opts['rev'])
            ui.warn((msg + '\n') % headless)

    if not heads:
        return 1

    heads = sorted(heads, key=lambda x: -x.rev())
    displayer = cmdutil.show_changeset(ui, repo, opts)
    for ctx in heads:
        displayer.show(ctx)
    displayer.close()

@command('help',
    [('e', 'extension', None, _('show only help for extensions')),
     ('c', 'command', None, _('show only help for commands'))],
    _('[-ec] [TOPIC]'))
def help_(ui, name=None, unknowncmd=False, full=True, **opts):
    """show help for a given topic or a help overview

    With no arguments, print a list of commands with short help messages.

    Given a topic, extension, or command name, print help for that
    topic.

    Returns 0 if successful.
    """

    optlist = []
    textwidth = min(ui.termwidth(), 80) - 2

    # list all option lists
    def opttext(optlist, width):
        out = []
        multioccur = False
        for title, options in optlist:
            out.append(("\n%s" % title, None))
            for option in options:
                if len(option) == 5:
                    shortopt, longopt, default, desc, optlabel = option
                else:
                    shortopt, longopt, default, desc = option
                    optlabel = _("VALUE") # default label

                if _("DEPRECATED") in desc and not ui.verbose:
                    continue
                if isinstance(default, list):
                    numqualifier = " %s [+]" % optlabel
                    multioccur = True
                elif (default is not None) and not isinstance(default, bool):
                    numqualifier = " %s" % optlabel
                else:
                    numqualifier = ""
                out.append(("%2s%s" %
                            (shortopt and "-%s" % shortopt,
                             longopt and " --%s%s" %
                             (longopt, numqualifier)),
                            "%s%s" % (desc,
                                      default
                                      and _(" (default: %s)") % default
                                      or "")))
        if multioccur:
            msg = _("\n[+] marked option can be specified multiple times")
            if ui.verbose and name != 'shortlist':
                out.append((msg, None))
            else:
                out.insert(-1, (msg, None))

        text = ""
        if out:
            colwidth = encoding.colwidth
            # normalize: (opt or message, desc or None, width of opt)
            entries = [desc and (opt, desc, colwidth(opt)) or (opt, None, 0)
                       for opt, desc in out]
            hanging = max([e[2] for e in entries])
            for opt, desc, width in entries:
                if desc:
                    initindent = ' %s%s  ' % (opt, ' ' * (hanging - width))
                    hangindent = ' ' * (hanging + 3)
                    text += '%s\n' % (util.wrap(desc, width,
                                                initindent=initindent,
                                                hangindent=hangindent))
                else:
                    text +=  "%s\n" % opt

        return text

    def addglobalopts(aliases):
        if ui.verbose:
            optlist.append((_("global options:"), globalopts))
            if name == 'shortlist':
                optlist.append((_('use "hg help" for the full list '
                                       'of commands'), ()))
        else:
            if name == 'shortlist':
                msg = _('use "hg help" for the full list of commands '
                        'or "hg -v" for details')
            elif name and not full:
                msg = _('use "hg help %s" to show the full help text' % name)
            elif aliases:
                msg = _('use "hg -v help%s" to show builtin aliases and '
                        'global options') % (name and " " + name or "")
            else:
                msg = _('use "hg -v help %s" to show global options') % name
            optlist.append((msg, ()))

    def helpcmd(name):
        try:
            aliases, entry = cmdutil.findcmd(name, table, strict=unknowncmd)
        except error.AmbiguousCommand, inst:
            # py3k fix: except vars can't be used outside the scope of the
            # except block, nor can be used inside a lambda. python issue4617
            prefix = inst.args[0]
            select = lambda c: c.lstrip('^').startswith(prefix)
            helplist(_('list of commands:\n\n'), select)
            return

        # check if it's an invalid alias and display its error if it is
        if getattr(entry[0], 'badalias', False):
            if not unknowncmd:
                entry[0](ui)
            return

        # synopsis
        if len(entry) > 2:
            if entry[2].startswith('hg'):
                ui.write("%s\n" % entry[2])
            else:
                ui.write('hg %s %s\n' % (aliases[0], entry[2]))
        else:
            ui.write('hg %s\n' % aliases[0])

        # aliases
        if full and not ui.quiet and len(aliases) > 1:
            ui.write(_("\naliases: %s\n") % ', '.join(aliases[1:]))

        # description
        doc = gettext(entry[0].__doc__)
        if not doc:
            doc = _("(no help text available)")
        if util.safehasattr(entry[0], 'definition'):  # aliased command
            if entry[0].definition.startswith('!'):  # shell alias
                doc = _('shell alias for::\n\n    %s') % entry[0].definition[1:]
            else:
                doc = _('alias for: hg %s\n\n%s') % (entry[0].definition, doc)
        if ui.quiet or not full:
            doc = doc.splitlines()[0]
        keep = ui.verbose and ['verbose'] or []
        formatted, pruned = minirst.format(doc, textwidth, keep=keep)
        ui.write("\n%s\n" % formatted)
        if pruned:
            ui.write(_('\nuse "hg -v help %s" to show verbose help\n') % name)

        if not ui.quiet:
            # options
            if entry[1]:
                optlist.append((_("options:\n"), entry[1]))

            addglobalopts(False)

        # check if this command shadows a non-trivial (multi-line)
        # extension help text
        try:
            mod = extensions.find(name)
            doc = gettext(mod.__doc__) or ''
            if '\n' in doc.strip():
                msg = _('use "hg help -e %s" to show help for '
                        'the %s extension') % (name, name)
                ui.write('\n%s\n' % msg)
        except KeyError:
            pass

    def helplist(header, select=None):
        h = {}
        cmds = {}
        for c, e in table.iteritems():
            f = c.split("|", 1)[0]
            if select and not select(f):
                continue
            if (not select and name != 'shortlist' and
                e[0].__module__ != __name__):
                continue
            if name == "shortlist" and not f.startswith("^"):
                continue
            f = f.lstrip("^")
            if not ui.debugflag and f.startswith("debug"):
                continue
            doc = e[0].__doc__
            if doc and 'DEPRECATED' in doc and not ui.verbose:
                continue
            doc = gettext(doc)
            if not doc:
                doc = _("(no help text available)")
            h[f] = doc.splitlines()[0].rstrip()
            cmds[f] = c.lstrip("^")

        if not h:
            ui.status(_('no commands defined\n'))
            return

        ui.status(header)
        fns = sorted(h)
        m = max(map(len, fns))
        for f in fns:
            if ui.verbose:
                commands = cmds[f].replace("|",", ")
                ui.write(" %s:\n      %s\n"%(commands, h[f]))
            else:
                ui.write('%s\n' % (util.wrap(h[f], textwidth,
                                             initindent=' %-*s   ' % (m, f),
                                             hangindent=' ' * (m + 4))))

        if not ui.quiet:
            addglobalopts(True)

    def helptopic(name):
        for names, header, doc in help.helptable:
            if name in names:
                break
        else:
            raise error.UnknownCommand(name)

        # description
        if not doc:
            doc = _("(no help text available)")
        if util.safehasattr(doc, '__call__'):
            doc = doc()

        ui.write("%s\n\n" % header)
        ui.write("%s\n" % minirst.format(doc, textwidth, indent=4))
        try:
            cmdutil.findcmd(name, table)
            ui.write(_('\nuse "hg help -c %s" to see help for '
                       'the %s command\n') % (name, name))
        except error.UnknownCommand:
            pass

    def helpext(name):
        try:
            mod = extensions.find(name)
            doc = gettext(mod.__doc__) or _('no help text available')
        except KeyError:
            mod = None
            doc = extensions.disabledext(name)
            if not doc:
                raise error.UnknownCommand(name)

        if '\n' not in doc:
            head, tail = doc, ""
        else:
            head, tail = doc.split('\n', 1)
        ui.write(_('%s extension - %s\n\n') % (name.split('.')[-1], head))
        if tail:
            ui.write(minirst.format(tail, textwidth))
            ui.status('\n\n')

        if mod:
            try:
                ct = mod.cmdtable
            except AttributeError:
                ct = {}
            modcmds = set([c.split('|', 1)[0] for c in ct])
            helplist(_('list of commands:\n\n'), modcmds.__contains__)
        else:
            ui.write(_('use "hg help extensions" for information on enabling '
                       'extensions\n'))

    def helpextcmd(name):
        cmd, ext, mod = extensions.disabledcmd(ui, name, ui.config('ui', 'strict'))
        doc = gettext(mod.__doc__).splitlines()[0]

        msg = help.listexts(_("'%s' is provided by the following "
                              "extension:") % cmd, {ext: doc}, indent=4)
        ui.write(minirst.format(msg, textwidth))
        ui.write('\n\n')
        ui.write(_('use "hg help extensions" for information on enabling '
                   'extensions\n'))

    if name and name != 'shortlist':
        i = None
        if unknowncmd:
            queries = (helpextcmd,)
        elif opts.get('extension'):
            queries = (helpext,)
        elif opts.get('command'):
            queries = (helpcmd,)
        else:
            queries = (helptopic, helpcmd, helpext, helpextcmd)
        for f in queries:
            try:
                f(name)
                i = None
                break
            except error.UnknownCommand, inst:
                i = inst
        if i:
            raise i

    else:
        # program name
        ui.status(_("Mercurial Distributed SCM\n"))
        ui.status('\n')

        # list of commands
        if name == "shortlist":
            header = _('basic commands:\n\n')
        else:
            header = _('list of commands:\n\n')

        helplist(header)
        if name != 'shortlist':
            text = help.listexts(_('enabled extensions:'), extensions.enabled())
            if text:
                ui.write("\n%s\n" % minirst.format(text, textwidth))

    if not name:
        ui.write(_("\nadditional help topics:\n\n"))
        topics = []
        for names, header, doc in help.helptable:
            topics.append((sorted(names, key=len, reverse=True)[0], header))
        topics_len = max([len(s[0]) for s in topics])
        for t, desc in topics:
            ui.write(" %-*s  %s\n" % (topics_len, t, desc))

    ui.write(opttext(optlist, textwidth))

@command('identify|id',
    [('r', 'rev', '',
     _('identify the specified revision'), _('REV')),
    ('n', 'num', None, _('show local revision number')),
    ('i', 'id', None, _('show global revision id')),
    ('b', 'branch', None, _('show branch')),
    ('t', 'tags', None, _('show tags')),
    ('B', 'bookmarks', None, _('show bookmarks'))],
    _('[-nibtB] [-r REV] [SOURCE]'))
def identify(ui, repo, source=None, rev=None,
             num=None, id=None, branch=None, tags=None, bookmarks=None):
    """identify the working copy or specified revision

    Print a summary identifying the repository state at REV using one or
    two parent hash identifiers, followed by a "+" if the working
    directory has uncommitted changes, the branch name (if not default),
    a list of tags, and a list of bookmarks.

    When REV is not given, print a summary of the current state of the
    repository.

    Specifying a path to a repository root or Mercurial bundle will
    cause lookup to operate on that repository/bundle.

    Returns 0 if successful.
    """

    if not repo and not source:
        raise util.Abort(_("there is no Mercurial repository here "
                           "(.hg not found)"))

    hexfunc = ui.debugflag and hex or short
    default = not (num or id or branch or tags or bookmarks)
    output = []
    revs = []

    if source:
        source, branches = hg.parseurl(ui.expandpath(source))
        repo = hg.peer(ui, {}, source)
        revs, checkout = hg.addbranchrevs(repo, repo, branches, None)

    if not repo.local():
        if num or branch or tags:
            raise util.Abort(
                _("can't query remote revision number, branch, or tags"))
        if not rev and revs:
            rev = revs[0]
        if not rev:
            rev = "tip"

        remoterev = repo.lookup(rev)
        if default or id:
            output = [hexfunc(remoterev)]

        def getbms():
            bms = []

            if 'bookmarks' in repo.listkeys('namespaces'):
                hexremoterev = hex(remoterev)
                bms = [bm for bm, bmr in repo.listkeys('bookmarks').iteritems()
                       if bmr == hexremoterev]

            return bms

        if bookmarks:
            output.extend(getbms())
        elif default and not ui.quiet:
            # multiple bookmarks for a single parent separated by '/'
            bm = '/'.join(getbms())
            if bm:
                output.append(bm)
    else:
        if not rev:
            ctx = repo[None]
            parents = ctx.parents()
            changed = ""
            if default or id or num:
                changed = util.any(repo.status()) and "+" or ""
            if default or id:
                output = ["%s%s" %
                  ('+'.join([hexfunc(p.node()) for p in parents]), changed)]
            if num:
                output.append("%s%s" %
                  ('+'.join([str(p.rev()) for p in parents]), changed))
        else:
            ctx = scmutil.revsingle(repo, rev)
            if default or id:
                output = [hexfunc(ctx.node())]
            if num:
                output.append(str(ctx.rev()))

        if default and not ui.quiet:
            b = ctx.branch()
            if b != 'default':
                output.append("(%s)" % b)

            # multiple tags for a single parent separated by '/'
            t = '/'.join(ctx.tags())
            if t:
                output.append(t)

            # multiple bookmarks for a single parent separated by '/'
            bm = '/'.join(ctx.bookmarks())
            if bm:
                output.append(bm)
        else:
            if branch:
                output.append(ctx.branch())

            if tags:
                output.extend(ctx.tags())

            if bookmarks:
                output.extend(ctx.bookmarks())

    ui.write("%s\n" % ' '.join(output))

@command('import|patch',
    [('p', 'strip', 1,
     _('directory strip option for patch. This has the same '
       'meaning as the corresponding patch option'), _('NUM')),
    ('b', 'base', '', _('base path (DEPRECATED)'), _('PATH')),
    ('f', 'force', None, _('skip check for outstanding uncommitted changes')),
    ('', 'no-commit', None,
     _("don't commit, just update the working directory")),
    ('', 'bypass', None,
     _("apply patch without touching the working directory")),
    ('', 'exact', None,
     _('apply patch to the nodes from which it was generated')),
    ('', 'import-branch', None,
     _('use any branch information in patch (implied by --exact)'))] +
    commitopts + commitopts2 + similarityopts,
    _('[OPTION]... PATCH...'))
def import_(ui, repo, patch1, *patches, **opts):
    """import an ordered set of patches

    Import a list of patches and commit them individually (unless
    --no-commit is specified).

    If there are outstanding changes in the working directory, import
    will abort unless given the -f/--force flag.

    You can import a patch straight from a mail message. Even patches
    as attachments work (to use the body part, it must have type
    text/plain or text/x-patch). From and Subject headers of email
    message are used as default committer and commit message. All
    text/plain body parts before first diff are added to commit
    message.

    If the imported patch was generated by :hg:`export`, user and
    description from patch override values from message headers and
    body. Values given on command line with -m/--message and -u/--user
    override these.

    If --exact is specified, import will set the working directory to
    the parent of each patch before applying it, and will abort if the
    resulting changeset has a different ID than the one recorded in
    the patch. This may happen due to character set problems or other
    deficiencies in the text patch format.

    Use --bypass to apply and commit patches directly to the
    repository, not touching the working directory. Without --exact,
    patches will be applied on top of the working directory parent
    revision.

    With -s/--similarity, hg will attempt to discover renames and
    copies in the patch in the same way as 'addremove'.

    To read a patch from standard input, use "-" as the patch name. If
    a URL is specified, the patch will be downloaded from it.
    See :hg:`help dates` for a list of formats valid for -d/--date.

    Returns 0 on success.
    """
    patches = (patch1,) + patches

    date = opts.get('date')
    if date:
        opts['date'] = util.parsedate(date)

    update = not opts.get('bypass')
    if not update and opts.get('no_commit'):
        raise util.Abort(_('cannot use --no-commit with --bypass'))
    try:
        sim = float(opts.get('similarity') or 0)
    except ValueError:
        raise util.Abort(_('similarity must be a number'))
    if sim < 0 or sim > 100:
        raise util.Abort(_('similarity must be between 0 and 100'))
    if sim and not update:
        raise util.Abort(_('cannot use --similarity with --bypass'))

    if (opts.get('exact') or not opts.get('force')) and update:
        cmdutil.bailifchanged(repo)

    d = opts["base"]
    strip = opts["strip"]
    wlock = lock = None
    msgs = []

    def checkexact(repo, n, nodeid):
        if opts.get('exact') and hex(n) != nodeid:
            repo.rollback()
            raise util.Abort(_('patch is damaged or loses information'))

    def tryone(ui, hunk, parents):
        tmpname, message, user, date, branch, nodeid, p1, p2 = \
            patch.extract(ui, hunk)

        if not tmpname:
            return None
        commitid = _('to working directory')

        try:
            cmdline_message = cmdutil.logmessage(ui, opts)
            if cmdline_message:
                # pickup the cmdline msg
                message = cmdline_message
            elif message:
                # pickup the patch msg
                message = message.strip()
            else:
                # launch the editor
                message = None
            ui.debug('message:\n%s\n' % message)

            if len(parents) == 1:
                parents.append(repo[nullid])
            if opts.get('exact'):
                if not nodeid or not p1:
                    raise util.Abort(_('not a Mercurial patch'))
                p1 = repo[p1]
                p2 = repo[p2 or nullid]
            elif p2:
                try:
                    p1 = repo[p1]
                    p2 = repo[p2]
                except error.RepoError:
                    p1, p2 = parents
            else:
                p1, p2 = parents

            n = None
            if update:
                if opts.get('exact') and p1 != parents[0]:
                    hg.clean(repo, p1.node())
                if p1 != parents[0] and p2 != parents[1]:
                    repo.dirstate.setparents(p1.node(), p2.node())

                if opts.get('exact') or opts.get('import_branch'):
                    repo.dirstate.setbranch(branch or 'default')

                files = set()
                patch.patch(ui, repo, tmpname, strip=strip, files=files,
                            eolmode=None, similarity=sim / 100.0)
                files = list(files)
                if opts.get('no_commit'):
                    if message:
                        msgs.append(message)
                else:
                    if opts.get('exact'):
                        m = None
                    else:
                        m = scmutil.matchfiles(repo, files or [])
                    n = repo.commit(message, opts.get('user') or user,
                                    opts.get('date') or date, match=m,
                                    editor=cmdutil.commiteditor)
                    checkexact(repo, n, nodeid)
                    # Force a dirstate write so that the next transaction
                    # backups an up-to-date file.
                    repo.dirstate.write()
            else:
                if opts.get('exact') or opts.get('import_branch'):
                    branch = branch or 'default'
                else:
                    branch = p1.branch()
                store = patch.filestore()
                try:
                    files = set()
                    try:
                        patch.patchrepo(ui, repo, p1, store, tmpname, strip,
                                        files, eolmode=None)
                    except patch.PatchError, e:
                        raise util.Abort(str(e))
                    memctx = patch.makememctx(repo, (p1.node(), p2.node()),
                                              message,
                                              opts.get('user') or user,
                                              opts.get('date') or date,
                                              branch, files, store,
                                              editor=cmdutil.commiteditor)
                    repo.savecommitmessage(memctx.description())
                    n = memctx.commit()
                    checkexact(repo, n, nodeid)
                finally:
                    store.close()
            if n:
                commitid = short(n)
            return commitid
        finally:
            os.unlink(tmpname)

    try:
        wlock = repo.wlock()
        lock = repo.lock()
        parents = repo.parents()
        lastcommit = None
        for p in patches:
            pf = os.path.join(d, p)

            if pf == '-':
                ui.status(_("applying patch from stdin\n"))
                pf = ui.fin
            else:
                ui.status(_("applying %s\n") % p)
                pf = url.open(ui, pf)

            haspatch = False
            for hunk in patch.split(pf):
                commitid = tryone(ui, hunk, parents)
                if commitid:
                    haspatch = True
                    if lastcommit:
                        ui.status(_('applied %s\n') % lastcommit)
                    lastcommit = commitid
                if update or opts.get('exact'):
                    parents = repo.parents()
                else:
                    parents = [repo[commitid]]

            if not haspatch:
                raise util.Abort(_('no diffs found'))

        if msgs:
            repo.savecommitmessage('\n* * *\n'.join(msgs))
    finally:
        release(lock, wlock)

@command('incoming|in',
    [('f', 'force', None,
     _('run even if remote repository is unrelated')),
    ('n', 'newest-first', None, _('show newest record first')),
    ('', 'bundle', '',
     _('file to store the bundles into'), _('FILE')),
    ('r', 'rev', [], _('a remote changeset intended to be added'), _('REV')),
    ('B', 'bookmarks', False, _("compare bookmarks")),
    ('b', 'branch', [],
     _('a specific branch you would like to pull'), _('BRANCH')),
    ] + logopts + remoteopts + subrepoopts,
    _('[-p] [-n] [-M] [-f] [-r REV]... [--bundle FILENAME] [SOURCE]'))
def incoming(ui, repo, source="default", **opts):
    """show new changesets found in source

    Show new changesets found in the specified path/URL or the default
    pull location. These are the changesets that would have been pulled
    if a pull at the time you issued this command.

    For remote repository, using --bundle avoids downloading the
    changesets twice if the incoming is followed by a pull.

    See pull for valid source format details.

    Returns 0 if there are incoming changes, 1 otherwise.
    """
    if opts.get('bundle') and opts.get('subrepos'):
        raise util.Abort(_('cannot combine --bundle and --subrepos'))

    if opts.get('bookmarks'):
        source, branches = hg.parseurl(ui.expandpath(source),
                                       opts.get('branch'))
        other = hg.peer(repo, opts, source)
        if 'bookmarks' not in other.listkeys('namespaces'):
            ui.warn(_("remote doesn't support bookmarks\n"))
            return 0
        ui.status(_('comparing with %s\n') % util.hidepassword(source))
        return bookmarks.diff(ui, repo, other)

    repo._subtoppath = ui.expandpath(source)
    try:
        return hg.incoming(ui, repo, source, opts)
    finally:
        del repo._subtoppath


@command('^init', remoteopts, _('[-e CMD] [--remotecmd CMD] [DEST]'))
def init(ui, dest=".", **opts):
    """create a new repository in the given directory

    Initialize a new repository in the given directory. If the given
    directory does not exist, it will be created.

    If no directory is given, the current directory is used.

    It is possible to specify an ``ssh://`` URL as the destination.
    See :hg:`help urls` for more information.

    Returns 0 on success.
    """
    hg.peer(ui, opts, ui.expandpath(dest), create=True)

@command('locate',
    [('r', 'rev', '', _('search the repository as it is in REV'), _('REV')),
    ('0', 'print0', None, _('end filenames with NUL, for use with xargs')),
    ('f', 'fullpath', None, _('print complete paths from the filesystem root')),
    ] + walkopts,
    _('[OPTION]... [PATTERN]...'))
def locate(ui, repo, *pats, **opts):
    """locate files matching specific patterns

    Print files under Mercurial control in the working directory whose
    names match the given patterns.

    By default, this command searches all directories in the working
    directory. To search just the current directory and its
    subdirectories, use "--include .".

    If no patterns are given to match, this command prints the names
    of all files under Mercurial control in the working directory.

    If you want to feed the output of this command into the "xargs"
    command, use the -0 option to both this command and "xargs". This
    will avoid the problem of "xargs" treating single filenames that
    contain whitespace as multiple filenames.

    Returns 0 if a match is found, 1 otherwise.
    """
    end = opts.get('print0') and '\0' or '\n'
    rev = scmutil.revsingle(repo, opts.get('rev'), None).node()

    ret = 1
    m = scmutil.match(repo[rev], pats, opts, default='relglob')
    m.bad = lambda x, y: False
    for abs in repo[rev].walk(m):
        if not rev and abs not in repo.dirstate:
            continue
        if opts.get('fullpath'):
            ui.write(repo.wjoin(abs), end)
        else:
            ui.write(((pats and m.rel(abs)) or abs), end)
        ret = 0

    return ret

@command('^log|history',
    [('f', 'follow', None,
     _('follow changeset history, or file history across copies and renames')),
    ('', 'follow-first', None,
     _('only follow the first parent of merge changesets')),
    ('d', 'date', '', _('show revisions matching date spec'), _('DATE')),
    ('C', 'copies', None, _('show copied files')),
    ('k', 'keyword', [],
     _('do case-insensitive search for a given text'), _('TEXT')),
    ('r', 'rev', [], _('show the specified revision or range'), _('REV')),
    ('', 'removed', None, _('include revisions where files were removed')),
    ('m', 'only-merges', None, _('show only merges')),
    ('u', 'user', [], _('revisions committed by user'), _('USER')),
    ('', 'only-branch', [],
     _('show only changesets within the given named branch (DEPRECATED)'),
     _('BRANCH')),
    ('b', 'branch', [],
     _('show changesets within the given named branch'), _('BRANCH')),
    ('P', 'prune', [],
     _('do not display revision or any of its ancestors'), _('REV')),
    ('', 'hidden', False, _('show hidden changesets')),
    ] + logopts + walkopts,
    _('[OPTION]... [FILE]'))
def log(ui, repo, *pats, **opts):
    """show revision history of entire repository or files

    Print the revision history of the specified files or the entire
    project.

    If no revision range is specified, the default is ``tip:0`` unless
    --follow is set, in which case the working directory parent is
    used as the starting revision.

    File history is shown without following rename or copy history of
    files. Use -f/--follow with a filename to follow history across
    renames and copies. --follow without a filename will only show
    ancestors or descendants of the starting revision.

    By default this command prints revision number and changeset id,
    tags, non-trivial parents, user, date and time, and a summary for
    each commit. When the -v/--verbose switch is used, the list of
    changed files and full commit message are shown.

    .. note::
       log -p/--patch may generate unexpected diff output for merge
       changesets, as it will only compare the merge changeset against
       its first parent. Also, only files different from BOTH parents
       will appear in files:.

    .. container:: verbose

      Some examples:

      - changesets with full descriptions and file lists::

          hg log -v

      - changesets ancestral to the working directory::

          hg log -f

      - last 10 commits on the current branch::

          hg log -l 10 -b .

      - changesets showing all modifications of a file, including removals::

          hg log --removed file.c

      - all changesets that touch a directory, with diffs, excluding merges::

          hg log -Mp lib/

      - all revision numbers that match a keyword::

          hg log -k bug --template "{rev}\\n"

      - check if a given changeset is included is a tagged release::

          hg log -r "a21ccf and ancestor(1.9)"

      - find all changesets by some user in a date range::

          hg log -k alice -d "may 2008 to jul 2008"

      - summary of all changesets after the last tag::

          hg log -r "last(tagged())::" --template "{desc|firstline}\\n"

    See :hg:`help dates` for a list of formats valid for -d/--date.

    See :hg:`help revisions` and :hg:`help revsets` for more about
    specifying revisions.

    Returns 0 on success.
    """

    matchfn = scmutil.match(repo[None], pats, opts)
    limit = cmdutil.loglimit(opts)
    count = 0

    endrev = None
    if opts.get('copies') and opts.get('rev'):
        endrev = max(scmutil.revrange(repo, opts.get('rev'))) + 1

    df = False
    if opts["date"]:
        df = util.matchdate(opts["date"])

    branches = opts.get('branch', []) + opts.get('only_branch', [])
    opts['branch'] = [repo.lookupbranch(b) for b in branches]

    displayer = cmdutil.show_changeset(ui, repo, opts, True)
    def prep(ctx, fns):
        rev = ctx.rev()
        parents = [p for p in repo.changelog.parentrevs(rev)
                   if p != nullrev]
        if opts.get('no_merges') and len(parents) == 2:
            return
        if opts.get('only_merges') and len(parents) != 2:
            return
        if opts.get('branch') and ctx.branch() not in opts['branch']:
            return
        if not opts.get('hidden') and ctx.hidden():
            return
        if df and not df(ctx.date()[0]):
            return
        if opts['user'] and not [k for k in opts['user']
                                 if k.lower() in ctx.user().lower()]:
            return
        if opts.get('keyword'):
            for k in [kw.lower() for kw in opts['keyword']]:
                if (k in ctx.user().lower() or
                    k in ctx.description().lower() or
                    k in " ".join(ctx.files()).lower()):
                    break
            else:
                return

        copies = None
        if opts.get('copies') and rev:
            copies = []
            getrenamed = templatekw.getrenamedfn(repo, endrev=endrev)
            for fn in ctx.files():
                rename = getrenamed(fn, rev)
                if rename:
                    copies.append((fn, rename[0]))

        revmatchfn = None
        if opts.get('patch') or opts.get('stat'):
            if opts.get('follow') or opts.get('follow_first'):
                # note: this might be wrong when following through merges
                revmatchfn = scmutil.match(repo[None], fns, default='path')
            else:
                revmatchfn = matchfn

        displayer.show(ctx, copies=copies, matchfn=revmatchfn)

    for ctx in cmdutil.walkchangerevs(repo, matchfn, opts, prep):
        if count == limit:
            break
        if displayer.flush(ctx.rev()):
            count += 1
    displayer.close()

@command('manifest',
    [('r', 'rev', '', _('revision to display'), _('REV')),
     ('', 'all', False, _("list files from all revisions"))],
    _('[-r REV]'))
def manifest(ui, repo, node=None, rev=None, **opts):
    """output the current or given revision of the project manifest

    Print a list of version controlled files for the given revision.
    If no revision is given, the first parent of the working directory
    is used, or the null revision if no revision is checked out.

    With -v, print file permissions, symlink and executable bits.
    With --debug, print file revision hashes.

    If option --all is specified, the list of all files from all revisions
    is printed. This includes deleted and renamed files.

    Returns 0 on success.
    """
    if opts.get('all'):
        if rev or node:
            raise util.Abort(_("can't specify a revision with --all"))

        res = []
        prefix = "data/"
        suffix = ".i"
        plen = len(prefix)
        slen = len(suffix)
        lock = repo.lock()
        try:
            for fn, b, size in repo.store.datafiles():
                if size != 0 and fn[-slen:] == suffix and fn[:plen] == prefix:
                    res.append(fn[plen:-slen])
        finally:
            lock.release()
        for f in sorted(res):
            ui.write("%s\n" % f)
        return

    if rev and node:
        raise util.Abort(_("please specify just one revision"))

    if not node:
        node = rev

    decor = {'l':'644 @ ', 'x':'755 * ', '':'644   '}
    ctx = scmutil.revsingle(repo, node)
    for f in ctx:
        if ui.debugflag:
            ui.write("%40s " % hex(ctx.manifest()[f]))
        if ui.verbose:
            ui.write(decor[ctx.flags(f)])
        ui.write("%s\n" % f)

@command('^merge',
    [('f', 'force', None, _('force a merge with outstanding changes')),
    ('r', 'rev', '', _('revision to merge'), _('REV')),
    ('P', 'preview', None,
     _('review revisions to merge (no merge is performed)'))
     ] + mergetoolopts,
    _('[-P] [-f] [[-r] REV]'))
def merge(ui, repo, node=None, **opts):
    """merge working directory with another revision

    The current working directory is updated with all changes made in
    the requested revision since the last common predecessor revision.

    Files that changed between either parent are marked as changed for
    the next commit and a commit must be performed before any further
    updates to the repository are allowed. The next commit will have
    two parents.

    ``--tool`` can be used to specify the merge tool used for file
    merges. It overrides the HGMERGE environment variable and your
    configuration files. See :hg:`help merge-tools` for options.

    If no revision is specified, the working directory's parent is a
    head revision, and the current branch contains exactly one other
    head, the other head is merged with by default. Otherwise, an
    explicit revision with which to merge with must be provided.

    :hg:`resolve` must be used to resolve unresolved files.

    To undo an uncommitted merge, use :hg:`update --clean .` which
    will check out a clean copy of the original merge parent, losing
    all changes.

    Returns 0 on success, 1 if there are unresolved files.
    """

    if opts.get('rev') and node:
        raise util.Abort(_("please specify just one revision"))
    if not node:
        node = opts.get('rev')

    if not node:
        branch = repo[None].branch()
        bheads = repo.branchheads(branch)
        if len(bheads) > 2:
            raise util.Abort(_("branch '%s' has %d heads - "
                               "please merge with an explicit rev")
                             % (branch, len(bheads)),
                             hint=_("run 'hg heads .' to see heads"))

        parent = repo.dirstate.p1()
        if len(bheads) == 1:
            if len(repo.heads()) > 1:
                raise util.Abort(_("branch '%s' has one head - "
                                   "please merge with an explicit rev")
                                 % branch,
                                 hint=_("run 'hg heads' to see all heads"))
            msg = _('there is nothing to merge')
            if parent != repo.lookup(repo[None].branch()):
                msg = _('%s - use "hg update" instead') % msg
            raise util.Abort(msg)

        if parent not in bheads:
            raise util.Abort(_('working directory not at a head revision'),
                             hint=_("use 'hg update' or merge with an "
                                    "explicit revision"))
        node = parent == bheads[0] and bheads[-1] or bheads[0]
    else:
        node = scmutil.revsingle(repo, node).node()

    if opts.get('preview'):
        # find nodes that are ancestors of p2 but not of p1
        p1 = repo.lookup('.')
        p2 = repo.lookup(node)
        nodes = repo.changelog.findmissing(common=[p1], heads=[p2])

        displayer = cmdutil.show_changeset(ui, repo, opts)
        for node in nodes:
            displayer.show(repo[node])
        displayer.close()
        return 0

    try:
        # ui.forcemerge is an internal variable, do not document
        repo.ui.setconfig('ui', 'forcemerge', opts.get('tool', ''))
        return hg.merge(repo, node, force=opts.get('force'))
    finally:
        ui.setconfig('ui', 'forcemerge', '')

@command('outgoing|out',
    [('f', 'force', None, _('run even when the destination is unrelated')),
    ('r', 'rev', [],
     _('a changeset intended to be included in the destination'), _('REV')),
    ('n', 'newest-first', None, _('show newest record first')),
    ('B', 'bookmarks', False, _('compare bookmarks')),
    ('b', 'branch', [], _('a specific branch you would like to push'),
     _('BRANCH')),
    ] + logopts + remoteopts + subrepoopts,
    _('[-M] [-p] [-n] [-f] [-r REV]... [DEST]'))
def outgoing(ui, repo, dest=None, **opts):
    """show changesets not found in the destination

    Show changesets not found in the specified destination repository
    or the default push location. These are the changesets that would
    be pushed if a push was requested.

    See pull for details of valid destination formats.

    Returns 0 if there are outgoing changes, 1 otherwise.
    """

    if opts.get('bookmarks'):
        dest = ui.expandpath(dest or 'default-push', dest or 'default')
        dest, branches = hg.parseurl(dest, opts.get('branch'))
        other = hg.peer(repo, opts, dest)
        if 'bookmarks' not in other.listkeys('namespaces'):
            ui.warn(_("remote doesn't support bookmarks\n"))
            return 0
        ui.status(_('comparing with %s\n') % util.hidepassword(dest))
        return bookmarks.diff(ui, other, repo)

    repo._subtoppath = ui.expandpath(dest or 'default-push', dest or 'default')
    try:
        return hg.outgoing(ui, repo, dest, opts)
    finally:
        del repo._subtoppath

@command('parents',
    [('r', 'rev', '', _('show parents of the specified revision'), _('REV')),
    ] + templateopts,
    _('[-r REV] [FILE]'))
def parents(ui, repo, file_=None, **opts):
    """show the parents of the working directory or revision

    Print the working directory's parent revisions. If a revision is
    given via -r/--rev, the parent of that revision will be printed.
    If a file argument is given, the revision in which the file was
    last changed (before the working directory revision or the
    argument to --rev if given) is printed.

    Returns 0 on success.
    """

    ctx = scmutil.revsingle(repo, opts.get('rev'), None)

    if file_:
        m = scmutil.match(ctx, (file_,), opts)
        if m.anypats() or len(m.files()) != 1:
            raise util.Abort(_('can only specify an explicit filename'))
        file_ = m.files()[0]
        filenodes = []
        for cp in ctx.parents():
            if not cp:
                continue
            try:
                filenodes.append(cp.filenode(file_))
            except error.LookupError:
                pass
        if not filenodes:
            raise util.Abort(_("'%s' not found in manifest!") % file_)
        fl = repo.file(file_)
        p = [repo.lookup(fl.linkrev(fl.rev(fn))) for fn in filenodes]
    else:
        p = [cp.node() for cp in ctx.parents()]

    displayer = cmdutil.show_changeset(ui, repo, opts)
    for n in p:
        if n != nullid:
            displayer.show(repo[n])
    displayer.close()

@command('paths', [], _('[NAME]'))
def paths(ui, repo, search=None):
    """show aliases for remote repositories

    Show definition of symbolic path name NAME. If no name is given,
    show definition of all available names.

    Option -q/--quiet suppresses all output when searching for NAME
    and shows only the path names when listing all definitions.

    Path names are defined in the [paths] section of your
    configuration file and in ``/etc/mercurial/hgrc``. If run inside a
    repository, ``.hg/hgrc`` is used, too.

    The path names ``default`` and ``default-push`` have a special
    meaning.  When performing a push or pull operation, they are used
    as fallbacks if no location is specified on the command-line.
    When ``default-push`` is set, it will be used for push and
    ``default`` will be used for pull; otherwise ``default`` is used
    as the fallback for both.  When cloning a repository, the clone
    source is written as ``default`` in ``.hg/hgrc``.  Note that
    ``default`` and ``default-push`` apply to all inbound (e.g.
    :hg:`incoming`) and outbound (e.g. :hg:`outgoing`, :hg:`email` and
    :hg:`bundle`) operations.

    See :hg:`help urls` for more information.

    Returns 0 on success.
    """
    if search:
        for name, path in ui.configitems("paths"):
            if name == search:
                ui.status("%s\n" % util.hidepassword(path))
                return
        if not ui.quiet:
            ui.warn(_("not found!\n"))
        return 1
    else:
        for name, path in ui.configitems("paths"):
            if ui.quiet:
                ui.write("%s\n" % name)
            else:
                ui.write("%s = %s\n" % (name, util.hidepassword(path)))

def postincoming(ui, repo, modheads, optupdate, checkout):
    if modheads == 0:
        return
    if optupdate:
        try:
            return hg.update(repo, checkout)
        except util.Abort, inst:
            ui.warn(_("not updating: %s\n" % str(inst)))
            return 0
    if modheads > 1:
        currentbranchheads = len(repo.branchheads())
        if currentbranchheads == modheads:
            ui.status(_("(run 'hg heads' to see heads, 'hg merge' to merge)\n"))
        elif currentbranchheads > 1:
            ui.status(_("(run 'hg heads .' to see heads, 'hg merge' to merge)\n"))
        else:
            ui.status(_("(run 'hg heads' to see heads)\n"))
    else:
        ui.status(_("(run 'hg update' to get a working copy)\n"))

@command('^pull',
    [('u', 'update', None,
     _('update to new branch head if changesets were pulled')),
    ('f', 'force', None, _('run even when remote repository is unrelated')),
    ('r', 'rev', [], _('a remote changeset intended to be added'), _('REV')),
    ('B', 'bookmark', [], _("bookmark to pull"), _('BOOKMARK')),
    ('b', 'branch', [], _('a specific branch you would like to pull'),
     _('BRANCH')),
    ] + remoteopts,
    _('[-u] [-f] [-r REV]... [-e CMD] [--remotecmd CMD] [SOURCE]'))
def pull(ui, repo, source="default", **opts):
    """pull changes from the specified source

    Pull changes from a remote repository to a local one.

    This finds all changes from the repository at the specified path
    or URL and adds them to a local repository (the current one unless
    -R is specified). By default, this does not update the copy of the
    project in the working directory.

    Use :hg:`incoming` if you want to see what would have been added
    by a pull at the time you issued this command. If you then decide
    to add those changes to the repository, you should use :hg:`pull
    -r X` where ``X`` is the last changeset listed by :hg:`incoming`.

    If SOURCE is omitted, the 'default' path will be used.
    See :hg:`help urls` for more information.

    Returns 0 on success, 1 if an update had unresolved files.
    """
    source, branches = hg.parseurl(ui.expandpath(source), opts.get('branch'))
    other = hg.peer(repo, opts, source)
    ui.status(_('pulling from %s\n') % util.hidepassword(source))
    revs, checkout = hg.addbranchrevs(repo, other, branches, opts.get('rev'))

    if opts.get('bookmark'):
        if not revs:
            revs = []
        rb = other.listkeys('bookmarks')
        for b in opts['bookmark']:
            if b not in rb:
                raise util.Abort(_('remote bookmark %s not found!') % b)
            revs.append(rb[b])

    if revs:
        try:
            revs = [other.lookup(rev) for rev in revs]
        except error.CapabilityError:
            err = _("other repository doesn't support revision lookup, "
                    "so a rev cannot be specified.")
            raise util.Abort(err)

    modheads = repo.pull(other, heads=revs, force=opts.get('force'))
    bookmarks.updatefromremote(ui, repo, other)
    if checkout:
        checkout = str(repo.changelog.rev(other.lookup(checkout)))
    repo._subtoppath = source
    try:
        ret = postincoming(ui, repo, modheads, opts.get('update'), checkout)

    finally:
        del repo._subtoppath

    # update specified bookmarks
    if opts.get('bookmark'):
        for b in opts['bookmark']:
            # explicit pull overrides local bookmark if any
            ui.status(_("importing bookmark %s\n") % b)
            repo._bookmarks[b] = repo[rb[b]].node()
        bookmarks.write(repo)

    return ret

@command('^push',
    [('f', 'force', None, _('force push')),
    ('r', 'rev', [],
     _('a changeset intended to be included in the destination'),
     _('REV')),
    ('B', 'bookmark', [], _("bookmark to push"), _('BOOKMARK')),
    ('b', 'branch', [],
     _('a specific branch you would like to push'), _('BRANCH')),
    ('', 'new-branch', False, _('allow pushing a new branch')),
    ] + remoteopts,
    _('[-f] [-r REV]... [-e CMD] [--remotecmd CMD] [DEST]'))
def push(ui, repo, dest=None, **opts):
    """push changes to the specified destination

    Push changesets from the local repository to the specified
    destination.

    This operation is symmetrical to pull: it is identical to a pull
    in the destination repository from the current one.

    By default, push will not allow creation of new heads at the
    destination, since multiple heads would make it unclear which head
    to use. In this situation, it is recommended to pull and merge
    before pushing.

    Use --new-branch if you want to allow push to create a new named
    branch that is not present at the destination. This allows you to
    only create a new branch without forcing other changes.

    Use -f/--force to override the default behavior and push all
    changesets on all branches.

    If -r/--rev is used, the specified revision and all its ancestors
    will be pushed to the remote repository.

    Please see :hg:`help urls` for important details about ``ssh://``
    URLs. If DESTINATION is omitted, a default path will be used.

    Returns 0 if push was successful, 1 if nothing to push.
    """

    if opts.get('bookmark'):
        for b in opts['bookmark']:
            # translate -B options to -r so changesets get pushed
            if b in repo._bookmarks:
                opts.setdefault('rev', []).append(b)
            else:
                # if we try to push a deleted bookmark, translate it to null
                # this lets simultaneous -r, -b options continue working
                opts.setdefault('rev', []).append("null")

    dest = ui.expandpath(dest or 'default-push', dest or 'default')
    dest, branches = hg.parseurl(dest, opts.get('branch'))
    ui.status(_('pushing to %s\n') % util.hidepassword(dest))
    revs, checkout = hg.addbranchrevs(repo, repo, branches, opts.get('rev'))
    other = hg.peer(repo, opts, dest)
    if revs:
        revs = [repo.lookup(rev) for rev in revs]

    repo._subtoppath = dest
    try:
        # push subrepos depth-first for coherent ordering
        c = repo['']
        subs = c.substate # only repos that are committed
        for s in sorted(subs):
            if not c.sub(s).push(opts.get('force')):
                return False
    finally:
        del repo._subtoppath
    result = repo.push(other, opts.get('force'), revs=revs,
                       newbranch=opts.get('new_branch'))

    result = (result == 0)

    if opts.get('bookmark'):
        rb = other.listkeys('bookmarks')
        for b in opts['bookmark']:
            # explicit push overrides remote bookmark if any
            if b in repo._bookmarks:
                ui.status(_("exporting bookmark %s\n") % b)
                new = repo[b].hex()
            elif b in rb:
                ui.status(_("deleting remote bookmark %s\n") % b)
                new = '' # delete
            else:
                ui.warn(_('bookmark %s does not exist on the local '
                          'or remote repository!\n') % b)
                return 2
            old = rb.get(b, '')
            r = other.pushkey('bookmarks', b, old, new)
            if not r:
                ui.warn(_('updating bookmark %s failed!\n') % b)
                if not result:
                    result = 2

    return result

@command('recover', [])
def recover(ui, repo):
    """roll back an interrupted transaction

    Recover from an interrupted commit or pull.

    This command tries to fix the repository status after an
    interrupted operation. It should only be necessary when Mercurial
    suggests it.

    Returns 0 if successful, 1 if nothing to recover or verify fails.
    """
    if repo.recover():
        return hg.verify(repo)
    return 1

@command('^remove|rm',
    [('A', 'after', None, _('record delete for missing files')),
    ('f', 'force', None,
     _('remove (and delete) file even if added or modified')),
    ] + walkopts,
    _('[OPTION]... FILE...'))
def remove(ui, repo, *pats, **opts):
    """remove the specified files on the next commit

    Schedule the indicated files for removal from the repository.

    This only removes files from the current branch, not from the
    entire project history. -A/--after can be used to remove only
    files that have already been deleted, -f/--force can be used to
    force deletion, and -Af can be used to remove files from the next
    revision without deleting them from the working directory.

    The following table details the behavior of remove for different
    file states (columns) and option combinations (rows). The file
    states are Added [A], Clean [C], Modified [M] and Missing [!] (as
    reported by :hg:`status`). The actions are Warn, Remove (from
    branch) and Delete (from disk):

      ======= == == == ==
              A  C  M  !
      ======= == == == ==
      none    W  RD W  R
      -f      R  RD RD R
      -A      W  W  W  R
      -Af     R  R  R  R
      ======= == == == ==

    Note that remove never deletes files in Added [A] state from the
    working directory, not even if option --force is specified.

    This command schedules the files to be removed at the next commit.
    To undo a remove before that, see :hg:`revert`.

    Returns 0 on success, 1 if any warnings encountered.
    """

    ret = 0
    after, force = opts.get('after'), opts.get('force')
    if not pats and not after:
        raise util.Abort(_('no files specified'))

    m = scmutil.match(repo[None], pats, opts)
    s = repo.status(match=m, clean=True)
    modified, added, deleted, clean = s[0], s[1], s[3], s[6]

    for f in m.files():
        if f not in repo.dirstate and not os.path.isdir(m.rel(f)):
            if os.path.exists(m.rel(f)):
                ui.warn(_('not removing %s: file is untracked\n') % m.rel(f))
            ret = 1

    if force:
        list = modified + deleted + clean + added
    elif after:
        list = deleted
        for f in modified + added + clean:
            ui.warn(_('not removing %s: file still exists (use -f'
                      ' to force removal)\n') % m.rel(f))
            ret = 1
    else:
        list = deleted + clean
        for f in modified:
            ui.warn(_('not removing %s: file is modified (use -f'
                      ' to force removal)\n') % m.rel(f))
            ret = 1
        for f in added:
            ui.warn(_('not removing %s: file has been marked for add (use -f'
                      ' to force removal)\n') % m.rel(f))
            ret = 1

    for f in sorted(list):
        if ui.verbose or not m.exact(f):
            ui.status(_('removing %s\n') % m.rel(f))

    wlock = repo.wlock()
    try:
        if not after:
            for f in list:
                if f in added:
                    continue # we never unlink added files on remove
                try:
                    util.unlinkpath(repo.wjoin(f))
                except OSError, inst:
                    if inst.errno != errno.ENOENT:
                        raise
        repo[None].forget(list)
    finally:
        wlock.release()

    return ret

@command('rename|move|mv',
    [('A', 'after', None, _('record a rename that has already occurred')),
    ('f', 'force', None, _('forcibly copy over an existing managed file')),
    ] + walkopts + dryrunopts,
    _('[OPTION]... SOURCE... DEST'))
def rename(ui, repo, *pats, **opts):
    """rename files; equivalent of copy + remove

    Mark dest as copies of sources; mark sources for deletion. If dest
    is a directory, copies are put in that directory. If dest is a
    file, there can only be one source.

    By default, this command copies the contents of files as they
    exist in the working directory. If invoked with -A/--after, the
    operation is recorded, but no copying is performed.

    This command takes effect at the next commit. To undo a rename
    before that, see :hg:`revert`.

    Returns 0 on success, 1 if errors are encountered.
    """
    wlock = repo.wlock(False)
    try:
        return cmdutil.copy(ui, repo, pats, opts, rename=True)
    finally:
        wlock.release()

@command('resolve',
    [('a', 'all', None, _('select all unresolved files')),
    ('l', 'list', None, _('list state of files needing merge')),
    ('m', 'mark', None, _('mark files as resolved')),
    ('u', 'unmark', None, _('mark files as unresolved')),
    ('n', 'no-status', None, _('hide status prefix'))]
    + mergetoolopts + walkopts,
    _('[OPTION]... [FILE]...'))
def resolve(ui, repo, *pats, **opts):
    """redo merges or set/view the merge status of files

    Merges with unresolved conflicts are often the result of
    non-interactive merging using the ``internal:merge`` configuration
    setting, or a command-line merge tool like ``diff3``. The resolve
    command is used to manage the files involved in a merge, after
    :hg:`merge` has been run, and before :hg:`commit` is run (i.e. the
    working directory must have two parents).

    The resolve command can be used in the following ways:

    - :hg:`resolve [--tool TOOL] FILE...`: attempt to re-merge the specified
      files, discarding any previous merge attempts. Re-merging is not
      performed for files already marked as resolved. Use ``--all/-a``
      to select all unresolved files. ``--tool`` can be used to specify
      the merge tool used for the given files. It overrides the HGMERGE
      environment variable and your configuration files.

    - :hg:`resolve -m [FILE]`: mark a file as having been resolved
      (e.g. after having manually fixed-up the files). The default is
      to mark all unresolved files.

    - :hg:`resolve -u [FILE]...`: mark a file as unresolved. The
      default is to mark all resolved files.

    - :hg:`resolve -l`: list files which had or still have conflicts.
      In the printed list, ``U`` = unresolved and ``R`` = resolved.

    Note that Mercurial will not let you commit files with unresolved
    merge conflicts. You must use :hg:`resolve -m ...` before you can
    commit after a conflicting merge.

    Returns 0 on success, 1 if any files fail a resolve attempt.
    """

    all, mark, unmark, show, nostatus = \
        [opts.get(o) for o in 'all mark unmark list no_status'.split()]

    if (show and (mark or unmark)) or (mark and unmark):
        raise util.Abort(_("too many options specified"))
    if pats and all:
        raise util.Abort(_("can't specify --all and patterns"))
    if not (all or pats or show or mark or unmark):
        raise util.Abort(_('no files or directories specified; '
                           'use --all to remerge all files'))

    ms = mergemod.mergestate(repo)
    m = scmutil.match(repo[None], pats, opts)
    ret = 0

    for f in ms:
        if m(f):
            if show:
                if nostatus:
                    ui.write("%s\n" % f)
                else:
                    ui.write("%s %s\n" % (ms[f].upper(), f),
                             label='resolve.' +
                             {'u': 'unresolved', 'r': 'resolved'}[ms[f]])
            elif mark:
                ms.mark(f, "r")
            elif unmark:
                ms.mark(f, "u")
            else:
                wctx = repo[None]
                mctx = wctx.parents()[-1]

                # backup pre-resolve (merge uses .orig for its own purposes)
                a = repo.wjoin(f)
                util.copyfile(a, a + ".resolve")

                try:
                    # resolve file
                    ui.setconfig('ui', 'forcemerge', opts.get('tool', ''))
                    if ms.resolve(f, wctx, mctx):
                        ret = 1
                finally:
                    ui.setconfig('ui', 'forcemerge', '')

                # replace filemerge's .orig file with our resolve file
                util.rename(a + ".resolve", a + ".orig")

    ms.commit()
    return ret

@command('revert',
    [('a', 'all', None, _('revert all changes when no arguments given')),
    ('d', 'date', '', _('tipmost revision matching date'), _('DATE')),
    ('r', 'rev', '', _('revert to the specified revision'), _('REV')),
    ('C', 'no-backup', None, _('do not save backup copies of files')),
    ] + walkopts + dryrunopts,
    _('[OPTION]... [-r REV] [NAME]...'))
def revert(ui, repo, *pats, **opts):
    """restore files to their checkout state

    .. note::
       To check out earlier revisions, you should use :hg:`update REV`.
       To cancel a merge (and lose your changes), use :hg:`update --clean .`.

    With no revision specified, revert the specified files or directories
    to the contents they had in the parent of the working directory.
    This restores the contents of files to an unmodified
    state and unschedules adds, removes, copies, and renames. If the
    working directory has two parents, you must explicitly specify a
    revision.

    Using the -r/--rev or -d/--date options, revert the given files or
    directories to their states as of a specific revision. Because
    revert does not change the working directory parents, this will
    cause these files to appear modified. This can be helpful to "back
    out" some or all of an earlier change. See :hg:`backout` for a
    related method.

    Modified files are saved with a .orig suffix before reverting.
    To disable these backups, use --no-backup.

    See :hg:`help dates` for a list of formats valid for -d/--date.

    Returns 0 on success.
    """

    if opts.get("date"):
        if opts.get("rev"):
            raise util.Abort(_("you can't specify a revision and a date"))
        opts["rev"] = cmdutil.finddate(ui, repo, opts["date"])

    parent, p2 = repo.dirstate.parents()
    if not opts.get('rev') and p2 != nullid:
        # revert after merge is a trap for new users (issue2915)
        raise util.Abort(_('uncommitted merge with no revision specified'),
                         hint=_('use "hg update" or see "hg help revert"'))

    ctx = scmutil.revsingle(repo, opts.get('rev'))
    node = ctx.node()

    if not pats and not opts.get('all'):
        msg = _("no files or directories specified")
        if p2 != nullid:
            hint = _("uncommitted merge, use --all to discard all changes,"
                     " or 'hg update -C .' to abort the merge")
            raise util.Abort(msg, hint=hint)
        dirty = util.any(repo.status())
        if node != parent:
            if dirty:
                hint = _("uncommitted changes, use --all to discard all"
                         " changes, or 'hg update %s' to update") % ctx.rev()
            else:
                hint = _("use --all to revert all files,"
                         " or 'hg update %s' to update") % ctx.rev()
        elif dirty:
            hint = _("uncommitted changes, use --all to discard all changes")
        else:
            hint = _("use --all to revert all files")
        raise util.Abort(msg, hint=hint)

    mf = ctx.manifest()
    if node == parent:
        pmf = mf
    else:
        pmf = None

    # need all matching names in dirstate and manifest of target rev,
    # so have to walk both. do not print errors if files exist in one
    # but not other.

    names = {}

    wlock = repo.wlock()
    try:
        # walk dirstate.

        m = scmutil.match(repo[None], pats, opts)
        m.bad = lambda x, y: False
        for abs in repo.walk(m):
            names[abs] = m.rel(abs), m.exact(abs)

        # walk target manifest.

        def badfn(path, msg):
            if path in names:
                return
            path_ = path + '/'
            for f in names:
                if f.startswith(path_):
                    return
            ui.warn("%s: %s\n" % (m.rel(path), msg))

        m = scmutil.match(repo[node], pats, opts)
        m.bad = badfn
        for abs in repo[node].walk(m):
            if abs not in names:
                names[abs] = m.rel(abs), m.exact(abs)

        m = scmutil.matchfiles(repo, names)
        changes = repo.status(match=m)[:4]
        modified, added, removed, deleted = map(set, changes)

        # if f is a rename, also revert the source
        cwd = repo.getcwd()
        for f in added:
            src = repo.dirstate.copied(f)
            if src and src not in names and repo.dirstate[src] == 'r':
                removed.add(src)
                names[src] = (repo.pathto(src, cwd), True)

        def removeforget(abs):
            if repo.dirstate[abs] == 'a':
                return _('forgetting %s\n')
            return _('removing %s\n')

        revert = ([], _('reverting %s\n'))
        add = ([], _('adding %s\n'))
        remove = ([], removeforget)
        undelete = ([], _('undeleting %s\n'))

        disptable = (
            # dispatch table:
            #   file state
            #   action if in target manifest
            #   action if not in target manifest
            #   make backup if in target manifest
            #   make backup if not in target manifest
            (modified, revert, remove, True, True),
            (added, revert, remove, True, False),
            (removed, undelete, None, False, False),
            (deleted, revert, remove, False, False),
            )

        for abs, (rel, exact) in sorted(names.items()):
            mfentry = mf.get(abs)
            target = repo.wjoin(abs)
            def handle(xlist, dobackup):
                xlist[0].append(abs)
                if (dobackup and not opts.get('no_backup') and
                    os.path.lexists(target)):
                    bakname = "%s.orig" % rel
                    ui.note(_('saving current version of %s as %s\n') %
                            (rel, bakname))
                    if not opts.get('dry_run'):
                        util.rename(target, bakname)
                if ui.verbose or not exact:
                    msg = xlist[1]
                    if not isinstance(msg, basestring):
                        msg = msg(abs)
                    ui.status(msg % rel)
            for table, hitlist, misslist, backuphit, backupmiss in disptable:
                if abs not in table:
                    continue
                # file has changed in dirstate
                if mfentry:
                    handle(hitlist, backuphit)
                elif misslist is not None:
                    handle(misslist, backupmiss)
                break
            else:
                if abs not in repo.dirstate:
                    if mfentry:
                        handle(add, True)
                    elif exact:
                        ui.warn(_('file not managed: %s\n') % rel)
                    continue
                # file has not changed in dirstate
                if node == parent:
                    if exact:
                        ui.warn(_('no changes needed to %s\n') % rel)
                    continue
                if pmf is None:
                    # only need parent manifest in this unlikely case,
                    # so do not read by default
                    pmf = repo[parent].manifest()
                if abs in pmf:
                    if mfentry:
                        # if version of file is same in parent and target
                        # manifests, do nothing
                        if (pmf[abs] != mfentry or
                            pmf.flags(abs) != mf.flags(abs)):
                            handle(revert, False)
                    else:
                        handle(remove, False)

        if not opts.get('dry_run'):
            def checkout(f):
                fc = ctx[f]
                repo.wwrite(f, fc.data(), fc.flags())

            audit_path = scmutil.pathauditor(repo.root)
            for f in remove[0]:
                if repo.dirstate[f] == 'a':
                    repo.dirstate.drop(f)
                    continue
                audit_path(f)
                try:
                    util.unlinkpath(repo.wjoin(f))
                except OSError:
                    pass
                repo.dirstate.remove(f)

            normal = None
            if node == parent:
                # We're reverting to our parent. If possible, we'd like status
                # to report the file as clean. We have to use normallookup for
                # merges to avoid losing information about merged/dirty files.
                if p2 != nullid:
                    normal = repo.dirstate.normallookup
                else:
                    normal = repo.dirstate.normal
            for f in revert[0]:
                checkout(f)
                if normal:
                    normal(f)

            for f in add[0]:
                checkout(f)
                repo.dirstate.add(f)

            normal = repo.dirstate.normallookup
            if node == parent and p2 == nullid:
                normal = repo.dirstate.normal
            for f in undelete[0]:
                checkout(f)
                normal(f)

    finally:
        wlock.release()

@command('rollback', dryrunopts)
def rollback(ui, repo, **opts):
    """roll back the last transaction (dangerous)

    This command should be used with care. There is only one level of
    rollback, and there is no way to undo a rollback. It will also
    restore the dirstate at the time of the last transaction, losing
    any dirstate changes since that time. This command does not alter
    the working directory.

    Transactions are used to encapsulate the effects of all commands
    that create new changesets or propagate existing changesets into a
    repository. For example, the following commands are transactional,
    and their effects can be rolled back:

    - commit
    - import
    - pull
    - push (with this repository as the destination)
    - unbundle

    This command is not intended for use on public repositories. Once
    changes are visible for pull by other users, rolling a transaction
    back locally is ineffective (someone else may already have pulled
    the changes). Furthermore, a race is possible with readers of the
    repository; for example an in-progress pull from the repository
    may fail if a rollback is performed.

    Returns 0 on success, 1 if no rollback data is available.
    """
    return repo.rollback(opts.get('dry_run'))

@command('root', [])
def root(ui, repo):
    """print the root (top) of the current working directory

    Print the root directory of the current repository.

    Returns 0 on success.
    """
    ui.write(repo.root + "\n")

@command('^serve',
    [('A', 'accesslog', '', _('name of access log file to write to'),
     _('FILE')),
    ('d', 'daemon', None, _('run server in background')),
    ('', 'daemon-pipefds', '', _('used internally by daemon mode'), _('NUM')),
    ('E', 'errorlog', '', _('name of error log file to write to'), _('FILE')),
    # use string type, then we can check if something was passed
    ('p', 'port', '', _('port to listen on (default: 8000)'), _('PORT')),
    ('a', 'address', '', _('address to listen on (default: all interfaces)'),
     _('ADDR')),
    ('', 'prefix', '', _('prefix path to serve from (default: server root)'),
     _('PREFIX')),
    ('n', 'name', '',
     _('name to show in web pages (default: working directory)'), _('NAME')),
    ('', 'web-conf', '',
     _('name of the hgweb config file (see "hg help hgweb")'), _('FILE')),
    ('', 'webdir-conf', '', _('name of the hgweb config file (DEPRECATED)'),
     _('FILE')),
    ('', 'pid-file', '', _('name of file to write process ID to'), _('FILE')),
    ('', 'stdio', None, _('for remote clients')),
    ('', 'cmdserver', '', _('for remote clients'), _('MODE')),
    ('t', 'templates', '', _('web templates to use'), _('TEMPLATE')),
    ('', 'style', '', _('template style to use'), _('STYLE')),
    ('6', 'ipv6', None, _('use IPv6 in addition to IPv4')),
    ('', 'certificate', '', _('SSL certificate file'), _('FILE'))],
    _('[OPTION]...'))
def serve(ui, repo, **opts):
    """start stand-alone webserver

    Start a local HTTP repository browser and pull server. You can use
    this for ad-hoc sharing and browsing of repositories. It is
    recommended to use a real web server to serve a repository for
    longer periods of time.

    Please note that the server does not implement access control.
    This means that, by default, anybody can read from the server and
    nobody can write to it by default. Set the ``web.allow_push``
    option to ``*`` to allow everybody to push to the server. You
    should use a real web server if you need to authenticate users.

    By default, the server logs accesses to stdout and errors to
    stderr. Use the -A/--accesslog and -E/--errorlog options to log to
    files.

    To have the server choose a free port number to listen on, specify
    a port number of 0; in this case, the server will print the port
    number it uses.

    Returns 0 on success.
    """

    if opts["stdio"] and opts["cmdserver"]:
        raise util.Abort(_("cannot use --stdio with --cmdserver"))

    def checkrepo():
        if repo is None:
            raise error.RepoError(_("There is no Mercurial repository here"
                              " (.hg not found)"))

    if opts["stdio"]:
        checkrepo()
        s = sshserver.sshserver(ui, repo)
        s.serve_forever()

    if opts["cmdserver"]:
        checkrepo()
        s = commandserver.server(ui, repo, opts["cmdserver"])
        return s.serve()

    # this way we can check if something was given in the command-line
    if opts.get('port'):
        opts['port'] = util.getport(opts.get('port'))

    baseui = repo and repo.baseui or ui
    optlist = ("name templates style address port prefix ipv6"
               " accesslog errorlog certificate encoding")
    for o in optlist.split():
        val = opts.get(o, '')
        if val in (None, ''): # should check against default options instead
            continue
        baseui.setconfig("web", o, val)
        if repo and repo.ui != baseui:
            repo.ui.setconfig("web", o, val)

    o = opts.get('web_conf') or opts.get('webdir_conf')
    if not o:
        if not repo:
            raise error.RepoError(_("There is no Mercurial repository"
                                    " here (.hg not found)"))
        o = repo.root

    app = hgweb.hgweb(o, baseui=ui)

    class service(object):
        def init(self):
            util.setsignalhandler()
            self.httpd = hgweb.server.create_server(ui, app)

            if opts['port'] and not ui.verbose:
                return

            if self.httpd.prefix:
                prefix = self.httpd.prefix.strip('/') + '/'
            else:
                prefix = ''

            port = ':%d' % self.httpd.port
            if port == ':80':
                port = ''

            bindaddr = self.httpd.addr
            if bindaddr == '0.0.0.0':
                bindaddr = '*'
            elif ':' in bindaddr: # IPv6
                bindaddr = '[%s]' % bindaddr

            fqaddr = self.httpd.fqaddr
            if ':' in fqaddr:
                fqaddr = '[%s]' % fqaddr
            if opts['port']:
                write = ui.status
            else:
                write = ui.write
            write(_('listening at http://%s%s/%s (bound to %s:%d)\n') %
                  (fqaddr, port, prefix, bindaddr, self.httpd.port))

        def run(self):
            self.httpd.serve_forever()

    service = service()

    cmdutil.service(opts, initfn=service.init, runfn=service.run)

@command('showconfig|debugconfig',
    [('u', 'untrusted', None, _('show untrusted configuration options'))],
    _('[-u] [NAME]...'))
def showconfig(ui, repo, *values, **opts):
    """show combined config settings from all hgrc files

    With no arguments, print names and values of all config items.

    With one argument of the form section.name, print just the value
    of that config item.

    With multiple arguments, print names and values of all config
    items with matching section names.

    With --debug, the source (filename and line number) is printed
    for each config item.

    Returns 0 on success.
    """

    for f in scmutil.rcpath():
        ui.debug('read config from: %s\n' % f)
    untrusted = bool(opts.get('untrusted'))
    if values:
        sections = [v for v in values if '.' not in v]
        items = [v for v in values if '.' in v]
        if len(items) > 1 or items and sections:
            raise util.Abort(_('only one config item permitted'))
    for section, name, value in ui.walkconfig(untrusted=untrusted):
        value = str(value).replace('\n', '\\n')
        sectname = section + '.' + name
        if values:
            for v in values:
                if v == section:
                    ui.debug('%s: ' %
                             ui.configsource(section, name, untrusted))
                    ui.write('%s=%s\n' % (sectname, value))
                elif v == sectname:
                    ui.debug('%s: ' %
                             ui.configsource(section, name, untrusted))
                    ui.write(value, '\n')
        else:
            ui.debug('%s: ' %
                     ui.configsource(section, name, untrusted))
            ui.write('%s=%s\n' % (sectname, value))

@command('^status|st',
    [('A', 'all', None, _('show status of all files')),
    ('m', 'modified', None, _('show only modified files')),
    ('a', 'added', None, _('show only added files')),
    ('r', 'removed', None, _('show only removed files')),
    ('d', 'deleted', None, _('show only deleted (but tracked) files')),
    ('c', 'clean', None, _('show only files without changes')),
    ('u', 'unknown', None, _('show only unknown (not tracked) files')),
    ('i', 'ignored', None, _('show only ignored files')),
    ('n', 'no-status', None, _('hide status prefix')),
    ('C', 'copies', None, _('show source of copied files')),
    ('0', 'print0', None, _('end filenames with NUL, for use with xargs')),
    ('', 'rev', [], _('show difference from revision'), _('REV')),
    ('', 'change', '', _('list the changed files of a revision'), _('REV')),
    ] + walkopts + subrepoopts,
    _('[OPTION]... [FILE]...'))
def status(ui, repo, *pats, **opts):
    """show changed files in the working directory

    Show status of files in the repository. If names are given, only
    files that match are shown. Files that are clean or ignored or
    the source of a copy/move operation, are not listed unless
    -c/--clean, -i/--ignored, -C/--copies or -A/--all are given.
    Unless options described with "show only ..." are given, the
    options -mardu are used.

    Option -q/--quiet hides untracked (unknown and ignored) files
    unless explicitly requested with -u/--unknown or -i/--ignored.

    .. note::
       status may appear to disagree with diff if permissions have
       changed or a merge has occurred. The standard diff format does
       not report permission changes and diff only reports changes
       relative to one merge parent.

    If one revision is given, it is used as the base revision.
    If two revisions are given, the differences between them are
    shown. The --change option can also be used as a shortcut to list
    the changed files of a revision from its first parent.

    The codes used to show the status of files are::

      M = modified
      A = added
      R = removed
      C = clean
      ! = missing (deleted by non-hg command, but still tracked)
      ? = not tracked
      I = ignored
        = origin of the previous file listed as A (added)

    Returns 0 on success.
    """

    revs = opts.get('rev')
    change = opts.get('change')

    if revs and change:
        msg = _('cannot specify --rev and --change at the same time')
        raise util.Abort(msg)
    elif change:
        node2 = repo.lookup(change)
        node1 = repo[node2].p1().node()
    else:
        node1, node2 = scmutil.revpair(repo, revs)

    cwd = (pats and repo.getcwd()) or ''
    end = opts.get('print0') and '\0' or '\n'
    copy = {}
    states = 'modified added removed deleted unknown ignored clean'.split()
    show = [k for k in states if opts.get(k)]
    if opts.get('all'):
        show += ui.quiet and (states[:4] + ['clean']) or states
    if not show:
        show = ui.quiet and states[:4] or states[:5]

    stat = repo.status(node1, node2, scmutil.match(repo[node2], pats, opts),
                       'ignored' in show, 'clean' in show, 'unknown' in show,
                       opts.get('subrepos'))
    changestates = zip(states, 'MAR!?IC', stat)

    if (opts.get('all') or opts.get('copies')) and not opts.get('no_status'):
        ctxn = repo[nullid]
        ctx1 = repo[node1]
        ctx2 = repo[node2]
        added = stat[1]
        if node2 is None:
            added = stat[0] + stat[1] # merged?

        for k, v in copies.copies(repo, ctx1, ctx2, ctxn)[0].iteritems():
            if k in added:
                copy[k] = v
            elif v in added:
                copy[v] = k

    for state, char, files in changestates:
        if state in show:
            format = "%s %%s%s" % (char, end)
            if opts.get('no_status'):
                format = "%%s%s" % end

            for f in files:
                ui.write(format % repo.pathto(f, cwd),
                         label='status.' + state)
                if f in copy:
                    ui.write('  %s%s' % (repo.pathto(copy[f], cwd), end),
                             label='status.copied')

@command('^summary|sum',
    [('', 'remote', None, _('check for push and pull'))], '[--remote]')
def summary(ui, repo, **opts):
    """summarize working directory state

    This generates a brief summary of the working directory state,
    including parents, branch, commit status, and available updates.

    With the --remote option, this will check the default paths for
    incoming and outgoing changes. This can be time-consuming.

    Returns 0 on success.
    """

    ctx = repo[None]
    parents = ctx.parents()
    pnode = parents[0].node()
    marks = []

    for p in parents:
        # label with log.changeset (instead of log.parent) since this
        # shows a working directory parent *changeset*:
        ui.write(_('parent: %d:%s ') % (p.rev(), str(p)),
                 label='log.changeset')
        ui.write(' '.join(p.tags()), label='log.tag')
        if p.bookmarks():
            marks.extend(p.bookmarks())
        if p.rev() == -1:
            if not len(repo):
                ui.write(_(' (empty repository)'))
            else:
                ui.write(_(' (no revision checked out)'))
        ui.write('\n')
        if p.description():
            ui.status(' ' + p.description().splitlines()[0].strip() + '\n',
                      label='log.summary')

    branch = ctx.branch()
    bheads = repo.branchheads(branch)
    m = _('branch: %s\n') % branch
    if branch != 'default':
        ui.write(m, label='log.branch')
    else:
        ui.status(m, label='log.branch')

    if marks:
        current = repo._bookmarkcurrent
        ui.write(_('bookmarks:'), label='log.bookmark')
        if current is not None:
            try:
                marks.remove(current)
                ui.write(' *' + current, label='bookmarks.current')
            except ValueError:
                # current bookmark not in parent ctx marks
                pass
        for m in marks:
          ui.write(' ' + m, label='log.bookmark')
        ui.write('\n', label='log.bookmark')

    st = list(repo.status(unknown=True))[:6]

    c = repo.dirstate.copies()
    copied, renamed = [], []
    for d, s in c.iteritems():
        if s in st[2]:
            st[2].remove(s)
            renamed.append(d)
        else:
            copied.append(d)
        if d in st[1]:
            st[1].remove(d)
    st.insert(3, renamed)
    st.insert(4, copied)

    ms = mergemod.mergestate(repo)
    st.append([f for f in ms if ms[f] == 'u'])

    subs = [s for s in ctx.substate if ctx.sub(s).dirty()]
    st.append(subs)

    labels = [ui.label(_('%d modified'), 'status.modified'),
              ui.label(_('%d added'), 'status.added'),
              ui.label(_('%d removed'), 'status.removed'),
              ui.label(_('%d renamed'), 'status.copied'),
              ui.label(_('%d copied'), 'status.copied'),
              ui.label(_('%d deleted'), 'status.deleted'),
              ui.label(_('%d unknown'), 'status.unknown'),
              ui.label(_('%d ignored'), 'status.ignored'),
              ui.label(_('%d unresolved'), 'resolve.unresolved'),
              ui.label(_('%d subrepos'), 'status.modified')]
    t = []
    for s, l in zip(st, labels):
        if s:
            t.append(l % len(s))

    t = ', '.join(t)
    cleanworkdir = False

    if len(parents) > 1:
        t += _(' (merge)')
    elif branch != parents[0].branch():
        t += _(' (new branch)')
    elif (parents[0].extra().get('close') and
          pnode in repo.branchheads(branch, closed=True)):
        t += _(' (head closed)')
    elif not (st[0] or st[1] or st[2] or st[3] or st[4] or st[9]):
        t += _(' (clean)')
        cleanworkdir = True
    elif pnode not in bheads:
        t += _(' (new branch head)')

    if cleanworkdir:
        ui.status(_('commit: %s\n') % t.strip())
    else:
        ui.write(_('commit: %s\n') % t.strip())

    # all ancestors of branch heads - all ancestors of parent = new csets
    new = [0] * len(repo)
    cl = repo.changelog
    for a in [cl.rev(n) for n in bheads]:
        new[a] = 1
    for a in cl.ancestors(*[cl.rev(n) for n in bheads]):
        new[a] = 1
    for a in [p.rev() for p in parents]:
        if a >= 0:
            new[a] = 0
    for a in cl.ancestors(*[p.rev() for p in parents]):
        new[a] = 0
    new = sum(new)

    if new == 0:
        ui.status(_('update: (current)\n'))
    elif pnode not in bheads:
        ui.write(_('update: %d new changesets (update)\n') % new)
    else:
        ui.write(_('update: %d new changesets, %d branch heads (merge)\n') %
                 (new, len(bheads)))

    if opts.get('remote'):
        t = []
        source, branches = hg.parseurl(ui.expandpath('default'))
        other = hg.peer(repo, {}, source)
        revs, checkout = hg.addbranchrevs(repo, other, branches, opts.get('rev'))
        ui.debug('comparing with %s\n' % util.hidepassword(source))
        repo.ui.pushbuffer()
        commoninc = discovery.findcommonincoming(repo, other)
        _common, incoming, _rheads = commoninc
        repo.ui.popbuffer()
        if incoming:
            t.append(_('1 or more incoming'))

        dest, branches = hg.parseurl(ui.expandpath('default-push', 'default'))
        revs, checkout = hg.addbranchrevs(repo, repo, branches, None)
        if source != dest:
            other = hg.peer(repo, {}, dest)
            commoninc = None
            ui.debug('comparing with %s\n' % util.hidepassword(dest))
        repo.ui.pushbuffer()
        common, outheads = discovery.findcommonoutgoing(repo, other,
                                                        commoninc=commoninc)
        repo.ui.popbuffer()
        o = repo.changelog.findmissing(common=common, heads=outheads)
        if o:
            t.append(_('%d outgoing') % len(o))
        if 'bookmarks' in other.listkeys('namespaces'):
            lmarks = repo.listkeys('bookmarks')
            rmarks = other.listkeys('bookmarks')
            diff = set(rmarks) - set(lmarks)
            if len(diff) > 0:
                t.append(_('%d incoming bookmarks') % len(diff))
            diff = set(lmarks) - set(rmarks)
            if len(diff) > 0:
                t.append(_('%d outgoing bookmarks') % len(diff))

        if t:
            ui.write(_('remote: %s\n') % (', '.join(t)))
        else:
            ui.status(_('remote: (synced)\n'))

@command('tag',
    [('f', 'force', None, _('force tag')),
    ('l', 'local', None, _('make the tag local')),
    ('r', 'rev', '', _('revision to tag'), _('REV')),
    ('', 'remove', None, _('remove a tag')),
    # -l/--local is already there, commitopts cannot be used
    ('e', 'edit', None, _('edit commit message')),
    ('m', 'message', '', _('use <text> as commit message'), _('TEXT')),
    ] + commitopts2,
    _('[-f] [-l] [-m TEXT] [-d DATE] [-u USER] [-r REV] NAME...'))
def tag(ui, repo, name1, *names, **opts):
    """add one or more tags for the current or given revision

    Name a particular revision using <name>.

    Tags are used to name particular revisions of the repository and are
    very useful to compare different revisions, to go back to significant
    earlier versions or to mark branch points as releases, etc. Changing
    an existing tag is normally disallowed; use -f/--force to override.

    If no revision is given, the parent of the working directory is
    used, or tip if no revision is checked out.

    To facilitate version control, distribution, and merging of tags,
    they are stored as a file named ".hgtags" which is managed similarly
    to other project files and can be hand-edited if necessary. This
    also means that tagging creates a new commit. The file
    ".hg/localtags" is used for local tags (not shared among
    repositories).

    Tag commits are usually made at the head of a branch. If the parent
    of the working directory is not a branch head, :hg:`tag` aborts; use
    -f/--force to force the tag commit to be based on a non-head
    changeset.

    See :hg:`help dates` for a list of formats valid for -d/--date.

    Since tag names have priority over branch names during revision
    lookup, using an existing branch name as a tag name is discouraged.

    Returns 0 on success.
    """

    rev_ = "."
    names = [t.strip() for t in (name1,) + names]
    if len(names) != len(set(names)):
        raise util.Abort(_('tag names must be unique'))
    for n in names:
        if n in ['tip', '.', 'null']:
            raise util.Abort(_("the name '%s' is reserved") % n)
        if not n:
            raise util.Abort(_('tag names cannot consist entirely of whitespace'))
    if opts.get('rev') and opts.get('remove'):
        raise util.Abort(_("--rev and --remove are incompatible"))
    if opts.get('rev'):
        rev_ = opts['rev']
    message = opts.get('message')
    if opts.get('remove'):
        expectedtype = opts.get('local') and 'local' or 'global'
        for n in names:
            if not repo.tagtype(n):
                raise util.Abort(_("tag '%s' does not exist") % n)
            if repo.tagtype(n) != expectedtype:
                if expectedtype == 'global':
                    raise util.Abort(_("tag '%s' is not a global tag") % n)
                else:
                    raise util.Abort(_("tag '%s' is not a local tag") % n)
        rev_ = nullid
        if not message:
            # we don't translate commit messages
            message = 'Removed tag %s' % ', '.join(names)
    elif not opts.get('force'):
        for n in names:
            if n in repo.tags():
                raise util.Abort(_("tag '%s' already exists "
                                   "(use -f to force)") % n)
    if not opts.get('local'):
        p1, p2 = repo.dirstate.parents()
        if p2 != nullid:
            raise util.Abort(_('uncommitted merge'))
        bheads = repo.branchheads()
        if not opts.get('force') and bheads and p1 not in bheads:
            raise util.Abort(_('not at a branch head (use -f to force)'))
    r = scmutil.revsingle(repo, rev_).node()

    if not message:
        # we don't translate commit messages
        message = ('Added tag %s for changeset %s' %
                   (', '.join(names), short(r)))

    date = opts.get('date')
    if date:
        date = util.parsedate(date)

    if opts.get('edit'):
        message = ui.edit(message, ui.username())

    repo.tag(names, r, message, opts.get('local'), opts.get('user'), date)

@command('tags', [], '')
def tags(ui, repo):
    """list repository tags

    This lists both regular and local tags. When the -v/--verbose
    switch is used, a third column "local" is printed for local tags.

    Returns 0 on success.
    """

    hexfunc = ui.debugflag and hex or short
    tagtype = ""

    for t, n in reversed(repo.tagslist()):
        if ui.quiet:
            ui.write("%s\n" % t, label='tags.normal')
            continue

        hn = hexfunc(n)
        r = "%5d:%s" % (repo.changelog.rev(n), hn)
        rev = ui.label(r, 'log.changeset')
        spaces = " " * (30 - encoding.colwidth(t))

        tag = ui.label(t, 'tags.normal')
        if ui.verbose:
            if repo.tagtype(t) == 'local':
                tagtype = " local"
                tag = ui.label(t, 'tags.local')
            else:
                tagtype = ""
        ui.write("%s%s %s%s\n" % (tag, spaces, rev, tagtype))

@command('tip',
    [('p', 'patch', None, _('show patch')),
    ('g', 'git', None, _('use git extended diff format')),
    ] + templateopts,
    _('[-p] [-g]'))
def tip(ui, repo, **opts):
    """show the tip revision

    The tip revision (usually just called the tip) is the changeset
    most recently added to the repository (and therefore the most
    recently changed head).

    If you have just made a commit, that commit will be the tip. If
    you have just pulled changes from another repository, the tip of
    that repository becomes the current tip. The "tip" tag is special
    and cannot be renamed or assigned to a different changeset.

    Returns 0 on success.
    """
    displayer = cmdutil.show_changeset(ui, repo, opts)
    displayer.show(repo[len(repo) - 1])
    displayer.close()

@command('unbundle',
    [('u', 'update', None,
     _('update to new branch head if changesets were unbundled'))],
    _('[-u] FILE...'))
def unbundle(ui, repo, fname1, *fnames, **opts):
    """apply one or more changegroup files

    Apply one or more compressed changegroup files generated by the
    bundle command.

    Returns 0 on success, 1 if an update has unresolved files.
    """
    fnames = (fname1,) + fnames

    lock = repo.lock()
    wc = repo['.']
    try:
        for fname in fnames:
            f = url.open(ui, fname)
            gen = changegroup.readbundle(f, fname)
            modheads = repo.addchangegroup(gen, 'unbundle', 'bundle:' + fname,
                                           lock=lock)
        bookmarks.updatecurrentbookmark(repo, wc.node(), wc.branch())
    finally:
        lock.release()
    return postincoming(ui, repo, modheads, opts.get('update'), None)

@command('^update|up|checkout|co',
    [('C', 'clean', None, _('discard uncommitted changes (no backup)')),
    ('c', 'check', None,
     _('update across branches if no uncommitted changes')),
    ('d', 'date', '', _('tipmost revision matching date'), _('DATE')),
    ('r', 'rev', '', _('revision'), _('REV'))],
    _('[-c] [-C] [-d DATE] [[-r] REV]'))
def update(ui, repo, node=None, rev=None, clean=False, date=None, check=False):
    """update working directory (or switch revisions)

    Update the repository's working directory to the specified
    changeset. If no changeset is specified, update to the tip of the
    current named branch.

    If the changeset is not a descendant of the working directory's
    parent, the update is aborted. With the -c/--check option, the
    working directory is checked for uncommitted changes; if none are
    found, the working directory is updated to the specified
    changeset.

    Update sets the working directory's parent revison to the specified
    changeset (see :hg:`help parents`).

    The following rules apply when the working directory contains
    uncommitted changes:

    1. If neither -c/--check nor -C/--clean is specified, and if
       the requested changeset is an ancestor or descendant of
       the working directory's parent, the uncommitted changes
       are merged into the requested changeset and the merged
       result is left uncommitted. If the requested changeset is
       not an ancestor or descendant (that is, it is on another
       branch), the update is aborted and the uncommitted changes
       are preserved.

    2. With the -c/--check option, the update is aborted and the
       uncommitted changes are preserved.

    3. With the -C/--clean option, uncommitted changes are discarded and
       the working directory is updated to the requested changeset.

    Use null as the changeset to remove the working directory (like
    :hg:`clone -U`).

    If you want to revert just one file to an older revision, use
    :hg:`revert [-r REV] NAME`.

    See :hg:`help dates` for a list of formats valid for -d/--date.

    Returns 0 on success, 1 if there are unresolved files.
    """
    if rev and node:
        raise util.Abort(_("please specify just one revision"))

    if rev is None or rev == '':
        rev = node

    # if we defined a bookmark, we have to remember the original bookmark name
    brev = rev
    rev = scmutil.revsingle(repo, rev, rev).rev()

    if check and clean:
        raise util.Abort(_("cannot specify both -c/--check and -C/--clean"))

    if check:
        # we could use dirty() but we can ignore merge and branch trivia
        c = repo[None]
        if c.modified() or c.added() or c.removed():
            raise util.Abort(_("uncommitted local changes"))

    if date:
        if rev is not None:
            raise util.Abort(_("you can't specify a revision and a date"))
        rev = cmdutil.finddate(ui, repo, date)

    if clean or check:
        ret = hg.clean(repo, rev)
    else:
        ret = hg.update(repo, rev)

    if brev in repo._bookmarks:
        bookmarks.setcurrent(repo, brev)

    return ret

@command('verify', [])
def verify(ui, repo):
    """verify the integrity of the repository

    Verify the integrity of the current repository.

    This will perform an extensive check of the repository's
    integrity, validating the hashes and checksums of each entry in
    the changelog, manifest, and tracked files, as well as the
    integrity of their crosslinks and indices.

    Returns 0 on success, 1 if errors are encountered.
    """
    return hg.verify(repo)

@command('version', [])
def version_(ui):
    """output version and copyright information"""
    ui.write(_("Mercurial Distributed SCM (version %s)\n")
             % util.version())
    ui.status(_(
        "(see http://mercurial.selenic.com for more information)\n"
        "\nCopyright (C) 2005-2011 Matt Mackall and others\n"
        "This is free software; see the source for copying conditions. "
        "There is NO\nwarranty; "
        "not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.\n"
    ))

norepo = ("clone init version help debugcommands debugcomplete"
          " debugdate debuginstall debugfsinfo debugpushkey debugwireargs"
          " debugknown debuggetbundle debugbundle")
optionalrepo = ("identify paths serve showconfig debugancestor debugdag"
                " debugdata debugindex debugindexdot debugrevlog")
