# Marcpick

Marcpick is a Python library for sifting MARC (MAchine Readable Cataloging)
records. It offers a simple and flexible way to extract data from records
that meet criteria.

## General

```
marcpick.set_scheme(field, condition=None)
```

Sets the scheme used to parse records.

- **field** (*str*): tab-delimited (sub)fields whose values will be extracted
- **condition** (*str*): a compound conditional based on regular expressions
  and boolean logic for (sub)field matching

Returns a dictionary containing key-value pairs of the parameters as keys and
their validation results as the values.

```
marcpick.parse_marc(source)
marcpick.parse_marcxml(source)
marcpick.parse_aleph(source)
```

Parses MARC, MARCXML or Aleph sequential records, and extracts data based on
specific criteria.

- **source** (*str* | *TextIO*): one or more MARC records

Returns a generator that can be iterated over to obtain the extracted data.

## Installation

```
$ pip install marcpick
```

## Usage

```
>>> from marcpick import MarcPick  
>>> mp = MarcPick()
>>> # The wildcard @ (at sign) represents any single character in tags,
>>> # indicators and subfield codes.
>>> field = 'LDR@@@\t010@@a\t200@@a\t210@@d'
>>> condition = '(200@@a(?i\)java AND NOT 200@@a(?i\)script) OR 606@@a^JAVA'
>>> mp.set_scheme(field, condition)
{'field': True, 'condition': True}
>>> with open('test.mrc', encoding='UTF-8') as fr:
...     data = mp.parse_marc(fr)
...     next(data)
```