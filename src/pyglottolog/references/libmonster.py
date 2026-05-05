r"""libmonster.py - mixed support library

# TODO: consider replacing pauthor in keyid with _bibtex.names
# TODO: enusure \emph is dropped from titles in keyid calculation
"""
import re
import logging
from heapq import nsmallest
from collections import defaultdict
from collections.abc import Sequence, Generator, Iterable, Iterator
import dataclasses
from itertools import groupby
from operator import itemgetter
from typing import TypeVar, Callable, Any, Literal, Optional, Union, TypedDict

from csvw.dsv import UnicodeWriter

from ..util import unique, Trigger, PathType
from .bibfiles import Entry
from .bibtex import EntryDictType, BibtexTypeAndFields
from .bibtex_undiacritic import undiacritic
from .roman import roman, romanint
from .hhtypes import HHTypes

T = TypeVar('T')
INF = float('inf')
log = logging.getLogger('pyglottolog')
LgcodeType = str
KeyType = str
HHType = str
DescriptionStatusType = tuple[float, str, KeyType, HHType]
INLG_FIELD = 'inlg'
LGCODE_FIELD = 'lgcode'


def map_values(
        d: Union[dict[str, T], Iterator[tuple[str, T]]],
        func: Callable[[T, ...], Any], *args) -> Generator[tuple[str, Any]]:
    """
    Apply func to all values of key-value tuples in d.

    :param d: A dictionary or an iterator of key-value pairs.
    :param func: Callable accepting a value of `d` as first parameter.
    :param args: Additional positional arguments to be passed to `func`.
    :return: `dict` mapping the keys of `d` to the return value of the function call.

    >>> dict(map_values({'a': 1}, lambda x, y: x + y, 3))
    {'a': 4}
    """
    for i, v in d.items() if isinstance(d, dict) else d:
        yield i, func(v, *args)


def group_pairs(seq: Sequence[Sequence[Any]]) -> dict[Any, list[Any]]:
    """
    Turn a list of pairs into a dictionary, mapping first elements to lists of
    co-occurring second elements in pairs.

    >>> group_pairs(['ab', 'ac', 'de', 'ax'])
    {'a': ['b', 'c', 'x'], 'd': ['e']}
    """
    return {a: [pair[1] for pair in pairs] for a, pairs in
            groupby(sorted(seq, key=itemgetter(0)), itemgetter(0))}


def grp2fd(seq: Sequence[Sequence[Any]]) -> dict[Any, dict[Any, Literal[1]]]:
    """
    Turn a list of pairs into a nested dictionary, thus grouping by the first (and then by the
    second) element in the pair.
    """
    return {k: {vv: 1 for vv in v} for k, v in group_pairs(seq).items()}


class Author(TypedDict):
    """Author name components."""
    lastname: str
    firstname: Optional[str]
    jr: Optional[str]


reauthor = [re.compile(pattern) for pattern in [
    r"(?P<lastname>[^,]+),\s((?P<jr>[JS]r\.|[I]+),\s)?(?P<firstname>[^,]+)$",
    r"(?P<firstname>[^{][\S]+(\s[A-Z][\S]+)*)\s"
    r"(?P<lastname>([a-z]+\s)*[A-Z\\\\][\S]+)(?P<jr>,\s[JS]r\.|[I]+)?$",
    r"(?P<firstname>\\{[\S]+\\}[\S]+(\s[A-Z][\S]+)*)\s"
    r"(?P<lastname>([a-z]+\s)*[A-Z\\\\][\S]+)(?P<jr>,\s[JS]r\.|[I]+)?$",
    r"(?P<firstname>[\s\S]+?)\s\{(?P<lastname>[\s\S]+)\}(?P<jr>,\s[JS]r\.|[I]+)?$",
    r"\{(?P<firstname>[\s\S]+)\}\s(?P<lastname>[\s\S]+?)(?P<jr>,\s[JS]r\.|[I]+)?$",
    r"(?P<lastname>[A-Z][\S]+)$",
    r"\{(?P<lastname>[\s\S]+)\}$",
    r"(?P<lastname>[aA]nonymous)$",
    r"(?P<lastname>\?)$",
    r"(?P<lastname>[\s\S]+)$",
]]


def psingleauthor(n: str) -> Optional[Author]:
    """Try to parse an author name from a string."""
    if not n:
        return None

    for pattern in reauthor:
        o = pattern.match(n)
        if o:
            return o.groupdict()
    log.warning("Couldn't parse name: %s", n)  # pragma: no cover
    return None  # pragma: no cover


def pauthor(s) -> list[Author]:
    """Parse authors from string."""
    pas = [psingleauthor(a) for a in s.split(' and ')]
    if [a for a in pas if not a]:
        if s:
            log.warning("Couldn't parse name: %s", s)
    return [a for a in pas if a]


relu = re.compile(r"\s+|(d\')(?=[A-Z])")
recapstart = re.compile(r"\[?[A-Z]")


def lowerupper(s: str) -> tuple[list[str], list[str]]:
    """
    >>> lowerupper('von der Hofen')
    (['von', 'der'], ['Hofen'])
    """
    parts, lower, upper = [x for x in relu.split(s) if x], [], []
    for i, x in enumerate(parts):
        if not recapstart.match(undiacritic(x)):
            lower.append(x)
        else:
            upper = parts[i:]
            break
    return lower, upper


def lastnamekey(s: str) -> str:
    """
    >>> lastnamekey('von der Meier')
    'Meier'
    """
    _, upper = lowerupper(s)
    return max(upper) if upper else ''


def rangecomplete(incomplete, complete):
    """
    >>> rangecomplete('2', '10')
    '12'
    """
    if len(complete) > len(incomplete):
        # if the second number in a range of pages has less digits than the first,
        # we assume it's meant as only the last digits of the bigger number,
        # i.e. 10-2 is interpreted as 10-12.
        return complete[:len(complete) - len(incomplete)] + incomplete
    return incomplete


rebracketyear = re.compile(r"\[([\d,\-/]+)]")

reyl = re.compile(r"[,\-/\s\[\]]+")


def pyear(s: str) -> str:
    """
    >>> pyear('1990 [2001]')
    '2001'
    """
    if rebracketyear.search(s):
        s = rebracketyear.search(s).group(1)
    my = [x for x in reyl.split(s) if x.strip()]
    if len(my) == 0:
        return "[nd]"
    if len(my) != 1:
        return my[0] + "-" + rangecomplete(my[-1], my[0])
    return my[-1]


bibord = {k: i for i, k in enumerate(['author',
                                      'editor',
                                      'title',
                                      'booktitle',
                                      'journal',
                                      'school',
                                      'publisher',
                                      'address',
                                      'series',
                                      'volume',
                                      'number',
                                      'pages',
                                      'year',
                                      'issn',
                                      'url'])}


def bibord_iteritems(fields: dict[str, Any]) -> Generator[tuple[str, Any], None, None]:
    """Yield fields items in canonical order."""
    for f in sorted(fields, key=lambda f: (bibord.get(f, INF), f)):
        yield f, fields[f]


resplittit = re.compile(r"[\(\)\[\]\:\,\.\s\-\?\!\;\/\~\=]+")


def wrds(txt: str) -> list[str]:
    """
    >>> wrds('Liberté, Égalité, Fraternité')
    ['liberte', 'egalite', 'fraternite']
    """
    txt = undiacritic(txt.lower())
    txt = txt.replace("'", "").replace('"', "")
    return [x for x in resplittit.split(txt) if x]


def renfn(e: EntryDictType, ups: Iterable[tuple[KeyType, str, Any]]) -> EntryDictType:
    """Apply the updates specified in ups to the appropriate entries in e."""
    for k, field, newvalue in ups:
        typ, fields = e[k]
        fields[field] = newvalue
        e[k] = (typ, fields)
    return e


def add_inlg_e(e: EntryDictType, trigs, verbose=True) -> EntryDictType:
    """Adds inlg field, computed from triggers."""
    # FIXME:  # pylint: disable=fixme
    # does not honor 'NOT' for now, only maps words to iso codes.
    dh = {word: t.type for t in trigs for _, word in t.clauses}

    # map record keys to lists of words in titles:
    ts = [(k, wrds(fields['title']) + wrds(fields.get('booktitle', '')))
          for (k, (typ, fields)) in e.items()
          if 'title' in fields and INLG_FIELD not in fields]

    if verbose:
        print(len(ts), "without", INLG_FIELD)

    # map record keys to sets of assigned iso codes, based on words in the title
    ann = [(k, set(dh[w] for w in tit if w in dh)) for k, tit in ts]

    # list of record keys which have been assigned exactly one language code
    unique_ = [(k, lgs.pop()) for (k, lgs) in ann if len(lgs) == 1]
    if verbose:
        print(len(unique_), "cases of unique hits")

    return renfn(e, [(k, INLG_FIELD, v) for (k, v) in unique_])


rerpgs = re.compile(r"([xivmcl]+)-?([xivmcl]*)")
repgs = re.compile(r"([\d]+)-?([\d]*)")


def pagecount(pgstr: str) -> int:
    """Compute pagecount from a string of page ranges, possibly using roman numerals."""
    rpgs = rerpgs.findall(pgstr)
    pgs = repgs.findall(pgstr)
    rsump = sum(romanint(b) - romanint(a) + 1 if b else romanint(a) for (a, b) in rpgs)
    sump = sum(int(rangecomplete(b, a)) - int(a) + 1 if b else int(a) for (a, b) in pgs)
    return rsump + sump


rewrdtok = re.compile(r"[a-zA-Z].+")
reokkey = re.compile(r"[^a-z\d\-_\[\]]")


def keyid(fields: dict[str, Any], frequency_dict: dict[str, float]) -> str:
    """Create a hashable key for an entry."""
    if 'author' not in fields:
        if 'editor' not in fields:
            values = ''.join(
                v for f, v in bibord_iteritems(fields) if f != 'glottolog_ref_id')
            return '__missingcontrib__' + reokkey.sub('_', values.lower())
        astring = fields['editor']
    else:
        astring = fields['author']

    authors = pauthor(astring)
    if len(authors) != len(astring.split(' and ')):
        print("Unparsed author in", authors)
        print("   ", astring, astring.split(' and '))
        print(fields.get('title'))

    ak = [undiacritic(x) for x in sorted(lastnamekey(a['lastname']) for a in authors)]
    yk = pyear(fields.get('year', '[nd]'))[:4]
    tks = wrds(fields.get("title", "no.title"))  # takeuntil :
    # select the (leftmost) two least frequent words from the title
    types = list(unique(w for w in tks if rewrdtok.match(w)))
    tk = nsmallest(2, types, key=lambda w: frequency_dict.get(w, float('inf')))
    # put them back into the title order (i.e. 'spam eggs' != 'eggs spam')
    order = {w: i for i, w in enumerate(types)}
    tk.sort(key=lambda w: order[w])
    if 'volume' in fields and all(
            f not in fields for f in ['journal', 'booktitle', 'series']):
        vk = roman(fields['volume'])
    else:
        vk = ''

    if 'extra_hash' in fields:
        yk = yk + fields['extra_hash']

    key = '-'.join(ak) + "_" + '-'.join(tk) + vk + yk
    return reokkey.sub("", key.lower())


def lgcode(arg: BibtexTypeAndFields) -> list[LgcodeType]:
    """Parse all language codes in the lgcode field."""
    fields = arg[1]
    return Entry.lgcodes(fields[LGCODE_FIELD]) if LGCODE_FIELD in fields else []


def description_status(es: EntryDictType, hht: HHTypes) -> list[list[DescriptionStatusType]]:
    """
    Lists of ordered description-stats tuples per hhtype.
    """
    # most signficant piece of descriptive material
    # hhtype, pages, year
    d = key_with_stats_by_hhtype(
        (k,
         (hht.parse(fields.get('hhtype', 'unknown')),
          fields.get('pages', ''),
          fields.get('year', ''))) for (k, (typ, fields)) in es.items())
    return [sorted(((p, y, k, t.id) for (k, (p, y)) in d[t.id].items()), reverse=True)
            for t in hht if t.id in d]


def key_with_stats_by_hhtype(
        mi: Iterator[tuple[KeyType, tuple[list[HHType], str, str]]],
) -> dict[HHType, dict[KeyType, tuple[float, str]]]:
    """
    Map hhtypes to dicts {key: description stats}.
    """
    r = defaultdict(dict)
    for (k, (hhts, pgs, year)) in mi:
        pci = pagecount(pgs)
        for t in hhts:
            r[t][k] = (pci / float(len(hhts)), year)
    return r


def keys_by_lgcode(e: EntryDictType) -> dict[LgcodeType, list[KeyType]]:
    """
    >>> e = {'k1': ('misc', {'lgcode': '[aaa], [bbb]'}), 'k2': ('misc', {'lgcode': '[bbb]'})}
    >>> keys_by_lgcode(e)
    {'aaa': ['k1'], 'bbb': ['k1', 'k2']}
    """
    return group_pairs([(code, key) for key, tf in e.items() for code in lgcode(tf)])


def sdlgs(e: EntryDictType, hht: HHTypes) -> dict[LgcodeType, list[list[DescriptionStatusType]]]:
    """Map language codes to description stats."""
    # Now expand the lists of keys into an EntryDictType:
    fes = map_values(keys_by_lgcode(e), lambda ks, *_: {k: e[k] for k in ks})
    return dict(map_values(fes, description_status, hht))


def lstat(e: EntryDictType, hht: HHTypes) -> dict[LgcodeType, Optional[HHType]]:
    """Map language codes to best HHType."""
    return dict(map_values(sdlgs(e, hht), lambda xs, *_: (xs + [[[None]]])[0][0][-1]))


def lstat_witness(e, hht) -> dict[LgcodeType, tuple[HHType, list[KeyType]]]:
    """Map language codes to best HHType and list of associated bibkeys."""
    def statwit(xs, *_):
        assert xs
        [(typ, ks)] = group_pairs([(t, k) for _, _, k, t in xs[0]]).items()
        return typ, ks

    return dict(map_values(sdlgs(e, hht), statwit))


@dataclasses.dataclass
class Report:
    """Reporting for conservative marking."""
    # Language codes with a higher computed HHType than in reference bib:
    log: list[tuple[LgcodeType, list[tuple[str, KeyType, str, str]], HHType]] \
        = dataclasses.field(default_factory=list)
    # Language codes with a computed HHType but no HHType in reference bib:
    no_status: dict[LgcodeType, set[str]] = dataclasses.field(
        default_factory=lambda: defaultdict(set))


def _revise_computerized_assignment(ls, lsafter, mafter, hht, report):
    blamefield = "hhtype"
    for (lg, (stat, wits)) in lsafter.items():
        if not ls.get(lg):  # No HHType assigned any entry for the language in the reference bib.
            srctrickles = [mafter[k][1].get('srctrickle') for k in wits]
            for t in srctrickles:
                if t and not t.startswith('iso6393'):
                    report.no_status[lg].add(t)
            continue
        if hht[stat] > hht[ls[lg]]:  # A higher HHType via computerized assignment.
            report.log.append((
                lg,
                [(mafter[k][1].get(blamefield, f"No {blamefield}"),
                  k,
                  mafter[k][1].get('title', 'no title'),
                  mafter[k][1].get('srctrickle', 'no srctrickle')) for k in wits],
                ls[lg]))
            for k in wits:
                (t, f) = mafter[k]
                if blamefield in f:
                    del f[blamefield]  # Can't be right :). Delete assigned field.
                mafter[k] = (t, f)
    return mafter


def markconservative(  # pylint: disable=R0913,R0917
        m: EntryDictType,
        trigs: list[Trigger],
        ref: EntryDictType,
        hht: HHTypes,
        outfn: PathType,
        verbose=True,
        rank=None,
) -> EntryDictType:
    """
    Run the computerized assignment of fields based on triggers.

    Then compare the computerized assignments per language code with the assignments based on a
    reference bibfile (typically hh.bib).

    Since hh.bib is thought to contain the best description for each language, a higher HHType
    computed for a language based on triggers is considered dubious, and thus deleted when marking
    conservatively. By the same reasoning, a HHType computed for a language which does not have one
    in hh.bib is considered dubious.
    """
    mafter: EntryDictType = markall(m, trigs, verbose=verbose, rank=rank)
    # HHType assignment in the ref bib - the gold standard.
    ls: dict[LgcodeType, Optional[HHType]] = lstat(ref, hht)
    # HHType assignment to the whole db after applying triggers:
    lsafter: dict[LgcodeType, tuple[HHType, list[KeyType]]] = lstat_witness(mafter, hht)

    report = Report()
    mafter = _revise_computerized_assignment(ls, lsafter, mafter, hht, report)
    for lg in report.no_status:
        print(f'{lg} lacks status')
    with UnicodeWriter(outfn, dialect='excel-tab') as writer:
        writer.writerows(((lg, was) + mis for (lg, miss, was) in report.log for mis in miss))
    return mafter


def _get_triggered(
        e: EntryDictType,
        trigs: list[Trigger],
) -> tuple[EntryDictType, dict[str, dict[tuple[str, str], Trigger]], set[str]]:
    # the set of fields triggers relate to:
    trigger_fields = set(t.field for t in trigs)

    # Construct the first argument to Trigger.__call__
    # all bibitems lacking any of the potential triggered fields:
    ei: EntryDictType = {
        k: (typ, fields) for k, (typ, fields) in e.items()
        if any(c not in fields for c in trigger_fields)}
    eikeys = set(list(ei.keys()))

    # Construct the second argument to Trigger.__call__.
    # Map words in titles to lists of bibitem keys having the word in the title.
    wk = defaultdict(set)
    for k, (typ, fields) in ei.items():
        for w in wrds(fields.get('title', '')):
            wk[w].add(k)

    triggered: dict[str, dict[tuple[str, str], Trigger]] = defaultdict(lambda: defaultdict(list))
    for _, triggers in Trigger.group(trigs):
        for k in triggers[0](eikeys, wk):
            for t in triggers:
                triggered[k][t.cls].append(t)

    return ei, triggered, trigger_fields


def markall(e: EntryDictType, trigs: list[Trigger], verbose=True, rank=None) -> EntryDictType:
    """
    Apply triggers.
    """
    ei, triggered, trigger_fields = _get_triggered(e, trigs)

    for k, t_by_c in sorted(triggered.items(), key=lambda i: i[0]):
        t, f = e[k]
        f2 = dict(f.items())  # A copy of the fields.
        for (field, type_), triggers in sorted(t_by_c.items(), key=lambda i: len(i[1])):
            # Make sure we handle the trigger class with the biggest number of matching
            # triggers last.
            if rank and field in f2:
                # only update the assigned hhtype if something better comes along:
                if rank(f2[field].split(' (comp')[0]) >= rank(type_):
                    continue
            # Assign the result of trigger-based computation:
            f2[field] = Trigger.format(type_, triggers)
        e[k] = (t, f2)

    if verbose:
        print("trigs", len(trigs))
        print("label classes", len(trigger_fields))
        print("unlabeled refs", len(ei))
        print("updates", len(triggered))
    return e
