from pydoctor import model

from nevow import tags

import inspect, urllib

def link(o):
    return urllib.quote(o.system.urlprefix+o.fullName()+'.html')

def get_parser(formatname):
    try:
        mod = __import__('epydoc.markup.' + formatname, globals(), locals(), ['parse_docstring'])
    except ImportError, e:
        return None, e
    else:
        return mod.parse_docstring, None

def boringDocstring(doc, summary=False):
    """Generate an HTML representation of a docstring in a really boring
    way."""
    # inspect.getdoc requires an object with a __doc__ attribute, not
    # just a string :-(
    if doc is None or not doc.strip():
        return '<pre class="undocumented">Undocumented</pre>'
    def crappit(): pass
    crappit.__doc__ = doc
    return [tags.pre, tags.tt][bool(summary)][inspect.getdoc(crappit)]

class _EpydocLinker(object):
    def __init__(self, obj):
        self.obj = obj
    def translate_indexterm(self, something):
        # X{foobar} is meant to put foobar in an index page (like, a
        # proper end-of-the-book index). Should we support that? There
        # are like 2 uses in Twisted.
        return something.to_html(self)
    def translate_identifier_xref(self, fullID, prettyID):
        obj = self.obj.resolveDottedName(fullID)
        if obj is None:
            return '<code>%s</code>'%(prettyID,)
        else:
            if isinstance(obj, model.Function):
                linktext = link(obj.parent) + '#' + urllib.quote(obj.name)
            else:
                linktext = link(obj)
            return '<a href="%s"><code>%s</code></a>'%(linktext, prettyID)

class FieldDesc(object):
    def __init__(self):
        self.kind = None
        self.name = None
        self.type = None
        self.body = None
    def format(self):
        if self.body is None:
            body = ''
        else:
            body = self.body
        if self.type is not None:
            body = body, '(type: ', self.type, ')'
        return body
    def __repr__(self):
        contents = []
        for k, v in self.__dict__.iteritems():
            contents.append("%s=%r"%(k, v))
        return "<%s(%s)>"%(self.__class__.__name__, ', '.join(contents))

def format_desc_list(singular, descs, plural=None):
    if plural is None:
        plural = singular + 's'
    if not descs:
        return ''
    if len(descs) > 1:
        label = plural
    else:
        label = singular
    r = []
    first = True
    for d in descs:
        if first:
            row = tags.tr(class_="fieldStart")
            row[tags.td(class_="fieldName")[label]]
            first = False
        else:
            row = tags.tr()
            row[tags.td()]
        if d.name is None:
            row[tags.td(colspan=2)[d.format()]]
        else:
            row[tags.td(class_="fieldArg")[d.name], tags.td[d.format()]]
        r.append(row)
    return r

def format_field_list(obj, singular, fields, plural=None):
    if plural is None:
        plural = singular + 's'
    if not fields:
        return ''
    if len(fields) > 1:
        label = plural
    else:
        label = singular
    rows = []
    first = True
    for field in fields:
        if first:
            row = tags.tr(class_="fieldStart")
            row[tags.td(class_="fieldName")[label]]
            first=False
        else:
            row = tags.tr()
            row[tags.td()]
        row[tags.td(colspan=2)[field.body]]
        rows.append(row)
    return rows

class Field(object):
    """Like epydoc.markup.Field, but without the gross accessor
    methods and with a formatted body."""
    def __init__(self, field, obj):
        self.tag = field.tag()
        self.arg = field.arg()
        self.body = tags.raw(field.body().to_html(_EpydocLinker(obj)))

    def __repr__(self):
        return "<%s %r %r %s>"%(self.__class__.__name__,
                             self.tag, self.arg, repr(self.body)[:30])

class FieldHandler(object):
    def __init__(self, obj):
        self.obj = obj

        self.parameter_descs = []
        self.ivar_descs = []
        self.cvar_descs = []
        self.var_descs = []
        self.return_desc = None
        self.raise_descs = []
        self.seealsos = []
        self.notes = []
        self.authors = []
        self.unknowns = []
        self.unattached_types = {}

    def handle_return(self, field):
        if not self.return_desc:
            self.return_desc = FieldDesc()
        if self.return_desc.body:
            print 'XXX'
        self.return_desc.body = field.body
    handle_returns = handle_return

    def handle_returntype(self, field):
        if not self.return_desc:
            self.return_desc = FieldDesc()
        if self.return_desc.type:
            print 'XXX'
        self.return_desc.type = field.body
    handle_rtype = handle_returntype

    def add_type_info(self, desc_list, field):
        #print desc_list, field
        if desc_list and desc_list[-1].name == field.arg:
            if desc_list[-1].type is None:
                self.obj.system.msg("epytext", "redefinition of @type %s"%(field.arg,), thresh=1)
            desc_list[-1].type = field.body
        else:
            d = FieldDesc()
            d.kind = field.tag
            d.name = field.arg
            d.type = field.body
            desc_list.append(d)

    def add_info(self, desc_list, field):
        if desc_list and desc_list[-1].name == field.arg and desc_list[-1].body is None:
            desc_list[-1].body = field.body
        else:
            d = FieldDesc()
            d.kind = field.tag
            d.name = field.arg
            d.body = field.body
            desc_list.append(d)

    def handle_type(self, field):
        obj = self.obj
        if isinstance(obj, model.Function):
            self.add_type_info(self.parameter_descs, field)
        elif isinstance(obj, model.Class):
            ivars = self.ivar_descs
            cvars = self.cvar_descs
            if ivars and ivars[-1].name == field.arg:
                if ivars[-1].type is not None:
                    self.obj.system.msg("epytext", "redefinition of @type %s"%(field.arg,), thresh=1)
                ivars[-1].type = field.body
            elif cvars and cvars[-1].name == field.arg:
                if cvars[-1].type is not None:
                    self.obj.system.msg("epytext", "redefinition of @type %s"%(field.arg,), thresh=1)
                cvars[-1].type = field.body
            else:
                self.unattached_types[field.arg] = field.body
        else:
            self.add_type_info(self.var_descs, field)

    def handle_param(self, field):
        self.add_info(self.parameter_descs, field)
    handle_arg = handle_param

    def handle_ivar(self, field):
        self.add_info(self.ivar_descs, field)
        if field.arg in self.unattached_types:
            self.ivar_descs[-1].type = self.unattached_types[field.arg]
            del self.unattached_types[field.arg]

    def handle_cvar(self, field):
        self.add_info(self.cvar_descs, field)
        if field.arg in self.unattached_types:
            self.cvar_descs[-1].type = self.unattached_types[field.arg]
            del self.unattached_types[field.arg]

    def handle_var(self, field):
        self.add_info(self.var_descs, field)

    def handle_raises(self, field):
        self.add_info(self.raise_descs, field)
    handle_raise = handle_raises

    def handle_seealso(self, field):
        self.seealsos.append(field)
    handle_see = handle_seealso

    def handle_note(self, field):
        self.notes.append(field)

    def handle_author(self, field):
        self.authors.append(field)

    def handleUnknownField(self, field):
        print 'XXX', 'unknown field', field
        self.add_info(self.unknowns, field)

    def handle(self, field):
        m = getattr(self, 'handle_' + field.tag, self.handleUnknownField)
        m(field)

    def format(self):
        r = []
        for d, l in (('Parameters', self.parameter_descs),
                     ('Instance Variables', self.ivar_descs),
                     ('Class Variables', self.cvar_descs),
                     ('Variables', self.var_descs)):
            r.append(format_desc_list(d, l, d))
        if self.return_desc:
            r.append(tags.tr(class_="fieldStart")[tags.td(class_="fieldName")['Returns'],
                               tags.td(colspan="2")[self.return_desc.format()]])
        r.append(format_desc_list("Raises", self.raise_descs, "Raises"))
        for s, p, l in (('Author', 'Authors', self.authors),
                        ('See Also', 'See Also', self.seealsos),
                        ('Note', 'Notes', self.notes)):
            r.append(format_field_list(self.obj, s, l, p))
        unknowns = {}
        unknownsinorder = []
        for fieldinfo in self.unknowns:
            tag = fieldinfo.kind
            if tag in unknowns:
                unknowns[tag].append(fieldinfo)
            else:
                unknowns[tag] = [fieldinfo]
                unknownsinorder.append(unknowns[tag])
        for fieldlist in unknownsinorder:
            label = "Unknown Field: " + fieldlist[0].kind
            r.append(format_desc_list(label, fieldlist, label))

        return tags.table(class_='fieldTable')[r]

errcount = 0

def doc2html(obj, summary=False, docstring=None):
    """Generate an HTML representation of a docstring"""
    origobj = obj
    if isinstance(obj, model.Package):
        obj = obj.contents['__init__']
    if docstring is None:
        if obj.docstring is None and hasattr(obj, 'docsource'):
            doc = obj.docsource.docstring
        else:
            doc = obj.docstring
    else:
        doc = docstring
    if doc is None or not doc.strip():
        text = "Undocumented"
        subdocstrings = {}
        subcounts = {}
        for subob in origobj.contents.itervalues():
            k = subob.kind.lower()
            subcounts[k] = subcounts.get(k, 0) + 1
            if subob.docstring is not None:
                subdocstrings[k] = subdocstrings.get(k, 0) + 1
        if isinstance(origobj, model.Package):
            subcounts["module"] -= 1
        if subdocstrings:
            plurals = {'class':'classes'}
            text = "No %s docstring"%origobj.kind.lower()
            if summary:
                u = []
                for k in sorted(subcounts):
                    u.append("%s/%s %s"%(subdocstrings.get(k, 0), subcounts[k],
                                         plurals.get(k, k+'s')))
                text += '; ' + ', '.join(u) + " documented"
        if summary:
            return tags.span(class_="undocumented")[text]
        else:
            return tags.div(class_="undocumented")[text]
    if summary:
        for line in doc.split('\n'):
            if line.strip():
                doc = line
                break
    parse_docstring, e = get_parser(obj.system.options.docformat)
    if not parse_docstring:
        #obj.system.msg('epytext', '%r parser cannot be imported: %s'%(obj.system.options.docformat, e))
        return boringDocstring(doc, summary)
    errs = []
    def crappit(): pass
    crappit.__doc__ = doc
    doc = inspect.getdoc(crappit)
    try:
        pdoc = parse_docstring(doc, errs)
    except Exception, e:
        errs = [e.__class__.__name__ +': ' + str(e)]
    if errs:
        obj.system.epytextproblems.append(obj.fullName())
        obj.system.msg('epytext', 'epytext error in %s'%(obj,), thresh=1)
        p = lambda m:obj.system.msg('epytext', m, thresh=2)
        for i, l in enumerate(doc.splitlines()):
            p("%4s"%(i+1)+' '+l)
        for err in errs:
            p(err)
        global errcount
        errcount += len(errs)
        return boringDocstring(doc, summary)
    pdoc, fields = pdoc.split_fields()
    try:
        crap = pdoc.to_html(_EpydocLinker(getattr(obj, 'docsource', obj)))
    except Exception, e:
        errs = [e.__class__.__name__ +': ' + str(e)]
        obj.system.epytextproblems.append(obj.fullName())
        obj.system.msg('epytext', 'epytext error in %s'%(obj,), thresh=1)
        p = lambda m:obj.system.msg('epytext', m, thresh=2)
        for i, l in enumerate(doc.splitlines()):
            p("%4s"%(i+1)+' '+l)
        for err in errs:
            p(err)
        global errcount
        errcount += len(errs)
        return boringDocstring(doc, summary)
    if crap.startswith('<p>') and crap.endswith('</p>\n'):
        crap = crap[3:-5] # argh reST
    if isinstance(crap, unicode):
        crap = crap.encode('utf-8')
    if summary:
        if not crap:
            return ()
        s = tags.span()[tags.raw(crap)]
    else:
        if not crap and not fields:
            return ()
        s = tags.div()[tags.raw(crap)]
        fh = FieldHandler(obj)
        for field in fields:
            fh.handle(Field(field, obj))
        s[fh.format()]
    return s
