import re
import xml.etree.ElementTree as Et
from functools import partial
from io import StringIO
from typing import Any, Dict, Iterator, List, Optional, TextIO, Union

Result = Iterator[Optional[List]]
Source = Union[str, TextIO]
Value = List[List[str]]


class MarcPick:
    def __init__(self) -> None:
        self._fields: List[str] = []
        self._conditions: List[Dict[str, Any]] = []
        self._combo: str = ''
        self._ANY = '@'
        self._IND = '#'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._fields.clear()
        self._conditions.clear()
        self._combo = ''

    def set_scheme(
            self, field: str,
            condition: Optional[str] = None) -> Dict[str, bool]:
        schemes = {
            'field': self._set_field(field),
            'condition': self._set_condition(condition)
        }
        if any(not v for v in schemes.values()):
            self._fields.clear()
            self._conditions.clear()
            self._combo = ''
        return schemes

    def get_scheme(self) -> Dict[str, Any]:
        return {
            'field': self._fields,
            'condition': self._conditions,
            'combo': self._combo
        }

    def parse_marc(self, source: Source) -> Result:
        if isinstance(source, str):
            source = StringIO(source)
        try:
            tail = ''
            for chunk in iter(partial(source.read, 4096), ''):
                if len(records := chunk.strip('\r\n').split('\x1D')) <= 1:
                    tail += chunk
                    continue
                yield self._parse_marc(tail + records[0])
                for record in records[1:-1]:
                    yield self._parse_marc(record)
                tail = records[-1]
            if tail:
                yield self._parse_marc(tail)
        except (AttributeError, UnicodeDecodeError):
            yield None

    def parse_marcxml(self, source: Source) -> Result:
        if isinstance(source, str):
            source = StringIO(source)
        try:
            namespaces = {n[0]: n[1] for _, n in Et.iterparse(
                source, events=['start-ns'])}
            source.seek(0)
            if not (root := Et.parse(source).getroot()):
                yield None
            if any(root.tag == f'{{{n}}}record' for n in namespaces.values()):
                yield self._parse_marcxml(root, namespaces)
            else:
                for record in root.iterfind('record', namespaces):
                    yield self._parse_marcxml(record, namespaces)
        except Et.ParseError:
            yield None

    def parse_aleph(self, source: Source) -> Result:
        if isinstance(source, str):
            source = StringIO(source)
        try:
            asn = ''
            records: List[str] = []
            for line in source:
                if len(line := line.strip()) < 19:
                    continue
                if asn and asn != line[:9]:
                    yield self._parse_aleph(records)
                    records = []
                asn = line[:9]
                records.append(line)
            if asn:
                yield self._parse_aleph(records)
        except (TypeError, UnicodeDecodeError):
            yield None

    def _set_field(self, field: str) -> bool:
        self._fields.clear()
        if not isinstance(field, str) or not field.strip():
            return False
        for f in field.split('\t'):
            if len(f) < 6 or not f[:6].isprintable():
                self._fields.clear()
                return False
            self._fields.append(f.lower())
        return True

    def _set_condition(self, condition: Optional[str]) -> bool:
        self._conditions.clear()
        self._combo = ''
        if not isinstance(condition, str):
            return False
        if not (condition := condition.strip().replace('\r', '').replace(
                '\n', '').replace('\\ ', '\t').replace('\\)', '\v')):
            return True
        pattern = '([0-9A-Za-z@]{3}[0-9A-Za-z@#]{2}[0-9A-Za-z@][^ \\)]*)'
        for cond in re.findall(pattern, condition):
            if len(cond) < 6 or not cond[:6].isprintable():
                return False
            if len(cond) == 6:
                regex = None
            else:
                try:
                    regex = re.compile(
                        cond[6:].replace('\t', ' ').replace('\v', ')'))
                except re.error:
                    return False
            label = cond[:6].lower().replace(self._IND, ' ')
            self._conditions.append(
                {'label': label, 'regex': regex, 'matched': []})
        self._combo = re.sub(pattern, '{}', condition).lower()
        if self._combo.count('{}') != len(self._conditions):
            return False
        try:
            eval(self._combo, {'__builtins__': None}, None)
        except SyntaxError:
            return False
        return True

    def _parse_marc(self, record: str) -> Optional[List]:
        for condition in self._conditions:
            condition['matched'] = []
        if not record:
            return None
        record = record.lstrip().replace('\t', '').replace(
            '\r', '').replace('\n', '')
        if not 40 <= len(record) < 99999:
            return None
        base = record.find('\x1E')
        if base == -1 or base % 12 != 0:
            return None
        if record.count('\x1E') != base / 12 - 1:
            return None
        for i in range(24 + 3, base, 12):
            if not record[i: i + 9].isdigit():
                return None
        values: Value = [[] for _ in range(len(self._fields))]
        self._parse_field(f'LDR{self._ANY * 3}', record[:24], values)
        entries = {
            record[i + 7: i + 12]: record[i: i + 3] for i in range(24, base, 12)
        }
        tags = [tag for _, tag in sorted(entries.items())]
        fields = record[base + 1:].split('\x1E')
        for tag, field in zip(tags, fields):
            if tag.startswith('00'):
                self._parse_field(tag + self._ANY * 3, field, values)
                continue
            subfields = field.split('\x1F')
            ind = subfields.pop(0)
            self._parse_field(tag + ind + self._ANY, field[2:], values, False)
            self._parse_field(tag + ind + self._IND, ind, values, False)
            for sf in subfields:
                if len(sf) > 1:
                    self._parse_field(tag + ind + sf[:1], sf[1:], values)
        return values if self._is_match() else []

    def _parse_marcxml(
            self, record: Et.Element, nss: Optional[Dict]) -> Optional[List]:
        for condition in self._conditions:
            condition['matched'] = []
        if not record:
            return None
        values: Value = [[] for _ in range(len(self._fields))]
        ldr = record.find('leader', nss)
        if ldr and ldr.text:
            self._parse_field(f'LDR{self._ANY * 3}', ldr.text, values)
        for cf in record.findall('controlfield', nss):
            tag = cf.attrib.get('tag', None)
            if not tag or not cf.text:
                continue
            if tag != 'LDR' or (ldr and ldr.text != cf.text):
                self._parse_field(tag + self._ANY * 3, cf.text, values)
        for df in record.findall('datafield', nss):
            if not (tag := df.attrib.get('tag', None)):
                continue
            ind1 = df.attrib.get('ind1', ' ')
            ind2 = df.attrib.get('ind2', ' ')
            if len(ti := tag + ind1 + ind2) != 5:
                continue
            self._parse_field(ti + self._IND, ind1 + ind2, values, False)
            sfs = []
            for sf in df:
                if (code := sf.attrib.get('code', None)) and sf.text:
                    self._parse_field(ti + code, sf.text, values)
                    sfs.append(code + sf.text)
            value = '\x1E' + '\x1E'.join(sfs)
            self._parse_field(ti + self._ANY, value, values, False)
        return values if self._is_match() else []

    def _parse_aleph(self, fields: List[str]) -> Optional[List]:
        for condition in self._conditions:
            condition['matched'] = []
        if not fields:
            return None
        values: Value = [[] for _ in range(len(self._fields))]
        if len(f := fields[0].strip()) > 18 and (asn := f[:9]).isdigit():
            self._parse_field(f'ASN{self._ANY * 3}', asn, values)
        for field in fields:
            if len(f := field.strip()) < 19 or not f[:9].isdigit():
                continue
            tag = f[10:13]
            value = f[18:]
            if tag in ('FMT', 'LDR') or tag.startswith('00'):
                self._parse_field(tag + self._ANY * 3, value, values)
                continue
            ind = f[13:15]
            self._parse_field(tag + ind + self._ANY, value, values, False)
            self._parse_field(tag + ind + self._IND, ind, values, False)
            subfields = value.split('$$')
            for sf in subfields:
                if len(sf) > 1:
                    self._parse_field(tag + ind + sf[0], sf[1:], values)
        return values if self._is_match() else []

    def _parse_field(
            self, label: str, value: str, values: Value,
            conditional: bool = True) -> None:
        if not value:
            return
        for i, field in enumerate(self._fields):
            for j, (f, l) in enumerate(zip(field, label.lower())):
                if (f == l) or (2 < j < 5 and f == self._ANY):
                    continue
                break
            else:
                values[i].append(value)
        if not conditional:
            return
        for condition in self._conditions:
            for f, l in zip(condition['label'], label):
                if f not in (self._ANY, l.lower()):
                    break
            else:
                if not (r := condition['regex']) or re.search(r, value):
                    condition['matched'].append(True)
                else:
                    condition['matched'].append(False)

    def _is_match(self) -> bool:
        if self._conditions:
            matched = [any(c['matched']) for c in self._conditions]
            ex = self._combo.format(*matched)
            if not eval(ex, {'__builtins__': None}, None):
                return False
        return True
