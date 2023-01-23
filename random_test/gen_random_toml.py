"""
Python module to generate random valid TOML documents.

This code is designed to produce valid TOML v1.0.0 documents.

Certain TOML features are avoided:
 - Leap-second time values (where seconds field has value "60").
"""

import sys
import argparse
import datetime
import math
import random
from collections.abc import Container, Sequence
from typing import Callable, cast


# Set True to debug the TOML generator.
_DEBUG = False

# Data type to represent keys or table names as a tuple of strings.
_KeyType = tuple[str, ...]

# Data type to represent date and/or time with or without timezone.
_DateTimeType = datetime.datetime | datetime.date | datetime.time

# Data type to represent any TOML value.
_ValueType = (
    str
    | bool
    | int
    | float
    | _DateTimeType
    | list["_ValueType"]
    | dict[str, "_ValueType"]
)

# Data type to represent a table (possibly inline table).
_TableType = dict[str, _ValueType]

# Data type to represent a table in the internal table tree.
_InternalTableType = dict[str,
    "_ValueType | TomlGenerator.Table | TomlGenerator.TableArray"]


class TomlGenerator:
    """Generate random valid TOML documents."""

    MAX_EXPRESSIONS     = 200
    MEAN_WS_LEN         = 2
    MAX_WS_LEN          = 100
    MEAN_COMMENT_LEN    = 8
    MAX_COMMENT_LEN     = 100
    MEAN_KEY_LEN        = 5
    MAX_KEY_LEN         = 100
    MEAN_STRING_LEN     = 10
    MAX_STRING_LEN      = 100
    MEAN_MLSTRING_LEN   = 25
    MAX_MLSTRING_LEN    = 200
    MEAN_ARRAY_ELEMS    = 2
    MAX_ARRAY_ELEMS     = 10
    MAX_DOTTED_LEN      = 3
    MAX_INT_VALUE       = 2**80

    PROB_COMMENT        = 0.5
    PROB_EXPR_KEYVAL    = 0.7
    PROB_EXPR_TABLE     = 0.1
    PROB_COMMENT_WS     = 0.1
    PROB_COMMENT_NASTY  = 0.1
    PROB_COMMENT_NONASCII = 0.1
    PROB_QUOTED_KEY     = 0.4
    PROB_EXISTING_KEY   = 0.5
    PROB_ESCAPE_CHAR    = 0.1
    PROB_ML_NEWLINE     = 0.1
    PROB_ML_ESCAPED_NEWLINE = 0.05
    PROB_ML_QUOTE       = 0.1
    PROB_SPECIAL_FLOAT  = 0.1

    ESCAPE_CHARS = {
        0x08: "b",
        0x09: "t",
        0x0a: "n",
        0x0c: "f",
        0x0d: "r",
        0x22: '"',
        0x5c: "\\"
    }

    class Table:
        """Helper class to represent a table."""
        def __init__(self, defined: bool, dotted: bool) -> None:
            self.elems: _InternalTableType = {}
            self.defined = defined
            self.dotted = dotted

    class TableArray:
        """Helper class to represent a table array."""
        def __init__(self) -> None:
            self.elems: list[_InternalTableType] = []

    class Context:
        """Helper class to build the semantic data structure."""

        def __init__(self) -> None:
            self.data: _InternalTableType = {}
            self.active_table = self.data

        def get_active_item_keys(self) -> list[_KeyType]:
            """Return a list of assigned item keys in the active table."""
            keys: list[_KeyType] = []

            def rec(tbl: _InternalTableType, path: _KeyType) -> None:
                for (p, v) in tbl.items():
                    if isinstance(v, TomlGenerator.Table):
                        rec(v.elems, path + (p, ))
                    elif isinstance(v, TomlGenerator.TableArray):
                        rec(v.elems[-1], path + (p, ))
                    else:
                        keys.append(path + (p, ))

            rec(self.active_table, ())
            return sorted(keys)

        def get_active_item_prefixes(self) -> list[_KeyType]:
            """Return a list of prefixes of items in the active table."""
            keys: list[_KeyType] = []

            def rec(tbl: _InternalTableType, path: _KeyType) -> None:
                for (p, v) in tbl.items():
                    if isinstance(v, TomlGenerator.Table) and v.dotted:
                        keys.append(path + (p, ))
                        rec(v.elems, path + (p, ))

            rec(self.active_table, ())
            return sorted(keys)

        def get_active_subtable_keys(self) -> list[_KeyType]:
            """Return a list of keys of subtables within the active table."""
            keys: list[_KeyType] = []
            for (p, v) in self.active_table.items():
                if isinstance(v, TomlGenerator.Table) and not v.dotted:
                    keys.append((p, ))
                elif isinstance(v, TomlGenerator.TableArray):
                    keys.append((p, ))
            return sorted(keys)

        def get_item_keys(self) -> list[_KeyType]:
            """Return a global list of assigned item keys and prefixes."""
            keys: list[_KeyType] = []

            def rec(tbl: _InternalTableType, path: _KeyType) -> None:
                for (p, v) in tbl.items():
                    if isinstance(v, TomlGenerator.Table):
                        rec(v.elems, path + (p, ))
                    elif isinstance(v, TomlGenerator.TableArray):
                        rec(v.elems[-1], path + (p, ))
                    else:
                        keys.append(path + (p, ))

            rec(self.data, ())
            return sorted(keys)

        def get_table_keys(self,
                           defined: bool|None = None,
                           array: bool|None = None
                           ) -> list[_KeyType]:
            """Return a global list of table keys."""
            keys: list[_KeyType] = []

            def rec(tbl: _InternalTableType, path: _KeyType) -> None:
                for (p, v) in tbl.items():
                    if isinstance(v, TomlGenerator.Table):
                        if ((array is not True)
                                and (defined is None
                                     or defined == v.defined)):
                            keys.append(path + (p, ))
                        rec(v.elems, path + (p, ))
                    elif isinstance(v, TomlGenerator.TableArray):
                        if array is not False:
                            keys.append(path + (p, ))
                        rec(v.elems[-1], path + (p, ))

            rec(self.data, ())
            return sorted(keys)

        def _make_subtable(self,
                           tbl: _InternalTableType,
                           key: _KeyType,
                           dotted: bool
                           ) -> _InternalTableType:
            """Return the subtable with the specified key.
            If necessary, make the subtable and any parents that are missing.
            """
            for p in key:
                if p not in tbl:
                    tbl[p] = TomlGenerator.Table(defined=dotted, dotted=dotted)
                subtbl = tbl[p]
                assert isinstance(subtbl,
                    (TomlGenerator.Table, TomlGenerator.TableArray))
                if isinstance(subtbl, TomlGenerator.TableArray):
                    tbl = subtbl.elems[-1]
                else:
                    tbl = subtbl.elems
            return tbl

        def open_table(self, key: _KeyType) -> None:
            """Define and activate a table.

            Create the table and its parents if necessary.
            The table must not have been defined previously.
            """
            if _DEBUG:
                print("OPEN TABLE", ascii(key))
            tbl = self._make_subtable(self.data, key[:-1], dotted=False)
            assert isinstance(tbl, dict)
            p = key[-1]
            if p not in tbl:
                tbl[p] = TomlGenerator.Table(defined=False, dotted=False)
            subtbl = tbl[p]
            assert isinstance(subtbl, TomlGenerator.Table)
            assert (not subtbl.defined)
            assert (not subtbl.dotted)
            subtbl.defined = True
            self.active_table = subtbl.elems

        def open_table_array(self, key: _KeyType) -> None:
            """Create a table array or add a new table to the array."""
            if _DEBUG:
                print("OPEN ARRAY", ascii(key))
            tbl = self._make_subtable(self.data, key[:-1], dotted=False)
            assert isinstance(tbl, dict)
            p = key[-1]
            if p not in tbl:
                tbl[p] = TomlGenerator.TableArray()
            subtbl = tbl[p]
            assert isinstance(subtbl, TomlGenerator.TableArray)
            subtbl.elems.append({})
            self.active_table = subtbl.elems[-1]

        def assign(self, key: _KeyType, value: _ValueType) -> None:
            """Insert a key-value element into the active table."""
            if _DEBUG:
                print("ASSIGN", ascii(key), ascii(value))
            tbl = self._make_subtable(self.active_table, key[:-1], dotted=True)
            assert isinstance(tbl, dict)
            p = key[-1]
            assert p not in tbl
            tbl[p] = value

        def _simplify_tables(self, tbl: _InternalTableType) -> _TableType:
            d: _TableType = {}
            for (key, val) in tbl.items():
                if isinstance(val, TomlGenerator.Table):
                    d[key] = self._simplify_tables(val.elems)
                elif isinstance(val, TomlGenerator.TableArray):
                    d[key] = [self._simplify_tables(v) for v in val.elems]
                else:
                    d[key] = val
            return d

        def get_data(self) -> _TableType:
            """Return the TOML data as a dictionary."""
            return self._simplify_tables(self.data)

    def __init__(self, rng: random.Random) -> None:
        """Initialize the TOML generator.

        Parameters:
            rng: Random number generator instance.
        """
        self.rng = rng

    def gen_toml(self) -> tuple[str, _TableType]:
        """Generate a random valid TOML document.

        Return a string containing the TOML document and a dict
        representing the TOML data.

        toml = expession *( newline expression )
        """
        ctx = TomlGenerator.Context()
        doc: list[str] = []

        num_expressions = self.rng.randint(1, self.MAX_EXPRESSIONS)
        for i in range(num_expressions):
            if i > 0:
                eol = self._gen_newline()
                doc.append(eol)
            expr = self._gen_expression(ctx)
            doc.append(expr)

        toml_doc = "".join(doc)
        toml_data = ctx.get_data()
        return (toml_doc, toml_data)

    def _rand_exp(self, mean: float, minval: int, maxval: int) -> int:
        """Choose a random integer from a semi-geometric distribution."""
        p = 1.0 / (1.0 + mean)
        cdfmin = 1.0 - (1.0 - p)**minval
        cdfmax = 1.0 - (1.0 - p)**(maxval + 1)
        r = self.rng.uniform(cdfmin, cdfmax)
        v = math.log(1.0 - r) / math.log(1.0 - p)
        v = math.floor(v)
        v = max(minval, min(maxval, v))
        return v

    def _rand_format_hex(self, val: int, minwidth: int = 1) -> str:
        """Format an integer as hexadecimal with random case."""
        s = ""
        while len(s) < minwidth or val > 0:
            c = val % 16
            val //= 16
            if c < 10:
                s = str(c) + s
            elif self.rng.randint(0, 1) == 0:
                s = chr(ord('a') + c - 10) + s
            else:
                s = chr(ord('A') + c - 10) + s
        return s

    def _gen_newline(self) -> str:
        """
        newline = %x0A / %x0D %x0A
        """
        return self.rng.choice(("\n", "\r\n"))

    def _gen_ws(self) -> str:
        """
        ws = *wschar
        wschar = %x20 / %x09
        """
        n = self._rand_exp(self.MEAN_WS_LEN, 0, self.MAX_WS_LEN)
        if n == 0:
            return ""
        wschars = self.rng.choices("\t ", weights=[1, 4], k=n)
        return "".join(wschars)

    def _gen_expression(self, ctx: Context) -> str:
        """
        expression = ws [comment]
                   / ws keyval ws [comment]
                   / ws table ws [comment]
        """
        doc = self._gen_ws()
        r = self.rng.random()
        if r < self.PROB_EXPR_KEYVAL:
            doc += self._gen_keyval(ctx)
            doc += self._gen_ws()
        elif r < self.PROB_EXPR_KEYVAL + self.PROB_EXPR_TABLE:
            doc += self._gen_table(ctx)
            doc += self._gen_ws()
        if self.rng.random() < self.PROB_COMMENT:
            doc += self._gen_comment()
        return doc

    def _gen_comment(self) -> str:
        """
        comment = "#" *non-eol
        non-eol = %x09 / %x20-7E / %x80-D7FF / %xE000-10FFFF
        """
        n = self._rand_exp(self.MEAN_COMMENT_LEN, 0, self.MAX_COMMENT_LEN)

        weights = [
            self.PROB_COMMENT_WS,
            self.PROB_COMMENT_NASTY,
            0.5 * self.PROB_COMMENT_NONASCII,
            0.5 * self.PROB_COMMENT_NONASCII]
        weights.append(1.0 - sum(weights))
        char_types = self.rng.choices([1, 2, 3, 4, 5], weights, k=n)

        comment_chars = []
        for t in char_types:
            if t == 1:
                c = self.rng.choice("\t    ")
            elif t == 2:
                c = self.rng.choice("#\"'\\")
            elif t == 3:
                c = chr(self.rng.randint(0x80, 0xd7ff))
            elif t == 4:
                c = chr(self.rng.randint(0xe000, 0x10ffff))
            else:
                c = chr(self.rng.randint(0x21, 0x7e))
            comment_chars.append(c)

        return "#" + "".join(comment_chars)

    def _gen_keyval(self, ctx: Context) -> str:
        """
        keyval = key keyval-sep val
        keyval-sep = ws "=" ws
        """
        # Do not re-use any existing key.
        # Do not re-use any existing table as prefix.
        # Encourage re-using an existing prefix from the active table.
        item_keys = ctx.get_active_item_keys()
        item_prefixes = ctx.get_active_item_prefixes()
        table_keys = ctx.get_active_subtable_keys()
        (key_str, key) = self._gen_key(
            exclude_prefix=item_keys + table_keys,
            exclude_key=item_keys + item_prefixes + table_keys,
            reuse_prefix=item_prefixes,
            reuse_key=())
        (val_str, val) = self._gen_val()
        ws1 = self._gen_ws()
        ws2 = self._gen_ws()
        ctx.assign(key, val)
        return key_str + ws1 + "=" + ws2 + val_str

    def _gen_key(self,
                 exclude_prefix: Container[tuple[str, ...]] = (),
                 exclude_key: Container[tuple[str, ...]] = (),
                 reuse_prefix: Sequence[tuple[str, ...]] = (),
                 reuse_key: Sequence[tuple[str, ...]] = ()
                 ) -> tuple[str, tuple[str, ...]]:
        """
        key = simple-key / dotted-key
        """
        # consider reusing an existing key or prefix
        if ((reuse_prefix or reuse_key)
                and self.rng.random() < self.PROB_EXISTING_KEY):
            n = len(reuse_prefix) + len(reuse_key)
            r = self.rng.randint(0, n - 1)
            if r < len(reuse_key):
                # reuse an existing key
                key = reuse_key[r]
                key_str = self._format_key(key)
                return (key_str, key)
            else:
                # reuse an existing prefix
                prefix = reuse_prefix[r - len(reuse_key)]
        else:
            prefix = ()

        # generate random dotted key, maybe using existing prefix
        searching = True
        while searching:
            (key_str, key) = self._gen_dotted_key(prefix)
            # check that key does not use a forbidden prefix
            searching = False
            if key in exclude_key:
                searching = True
                continue
            for i in range(1, len(key)):
                if key[:i] in exclude_prefix:
                    searching = True
                    break

        return (key_str, key)

    def _gen_simple_key(self) -> tuple[str, str]:
        """
        simple-key = quoted-key / unquoted-key
        quoted-key = basic-string / literal-string
        """
        r = self.rng.random()
        if r < self.PROB_QUOTED_KEY:
            if r < 0.5 * self.PROB_QUOTED_KEY:
                return self._gen_basic_string()
            else:
                return self._gen_literal_string()
        else:
            return self._gen_unquoted_key()

    def _gen_unquoted_key(self) -> tuple[str, str]:
        """
        unquoted-key = 1*( ALPHA / DIGIT / "-" / "_" )
        """
        n = self._rand_exp(self.MEAN_KEY_LEN, 1, self.MAX_KEY_LEN)
        key_chars = []
        for i in range(n):
            if self.rng.random() < 0.5:
                c = self.rng.choice("0123456789-_")
            else:
                c = self.rng.choice([chr(ord('a') + i) for i in range(26)]
                                    + [chr(ord('A') + i) for i in range(26)])
            key_chars.append(c)
        key = "".join(key_chars)
        return (key, key)

    def _format_simple_key(self, key: str) -> str:
        need_quote = (len(key) == 0)
        need_basic = False
        for c in key:
            if not (c in "-_"
                    or (0x30 <= ord(c) <= 0x39)
                    or (ord("a") <= ord(c) <= ord("z"))
                    or (ord("A") <= ord(c) <= ord("Z"))):
                need_quote = True
            if not (ord(c) == 0x09
                    or (0x20 <= ord(c) <= 0x7e and c != "'")
                    or (0x80 <= ord(c) <= 0xd7ff)
                    or (0xe000 <= ord(c) <= 0x10ffff)):
                need_basic = True
        if need_quote or self.rng.random() < self.PROB_QUOTED_KEY:
            if need_basic or self.rng.random() < 0.5:
                key_chars = []
                for c in key:
                    need_escape = not (
                        ord(c) == 0x09
                        or (0x20 <= ord(c) <= 0x7e and c != '"' and c != "\\")
                        or (0x80 <= ord(c) <= 0xd7ff)
                        or (0xe000 <= ord(c) <= 0x10ffff))
                    r = self.rng.random()
                    if need_escape or r < self.PROB_ESCAPE_CHAR:
                        r = self.rng.random()
                        if ord(c) in self.ESCAPE_CHARS and r < 0.5:
                            key_chars.append("\\" + self.ESCAPE_CHARS[ord(c)])
                        elif ord(c) < 0x10000 and r < 0.9:
                            h = self._rand_format_hex(ord(c), 4)
                            key_chars.append("\\u" + h)
                        else:
                            h = self._rand_format_hex(ord(c), 8)
                            key_chars.append("\\U" + h)
                    else:
                        key_chars.append(c)
                return '"' + "".join(key_chars) + '"'
            else:
                return "'" + key + "'"
        else:
            return key

    def _format_key(self, key: _KeyType) -> str:
        key_str: list[str] = []
        for k in key:
            if key_str:
                key_str.append(self._gen_ws() + "." + self._gen_ws())
            key_str.append(self._format_simple_key(k))
        return "".join(key_str)

    def _gen_dotted_key(self, prefix: _KeyType) -> tuple[str, _KeyType]:
        """
        dotted-key = simple-key 1*( dot-sep simple-key )
        dot-sep = ws "." ws
        """
        key: list[str] = []
        key_str: list[str] = []
        for k in prefix:
            if key_str:
                key_str.append(self._gen_ws() + "." + self._gen_ws())
            key_str.append(self._format_simple_key(k))
            key.append(k)

        n = self.rng.randint(1, self.MAX_DOTTED_LEN)
        for i in range(n):
            if key_str:
                key_str.append(self._gen_ws() + "." + self._gen_ws())
            (s, k) = self._gen_simple_key()
            key_str.append(s)
            key.append(k)

        return ("".join(key_str), tuple(key))

    def _gen_table(self, ctx: Context) -> str:
        """
        table = std-table / array-table
        std-table = "[" ws key ws "]"
        array-table = "[[" ws key ws "]]"
        """
        if self.rng.randint(0, 1) > 0:
            # array table
            # Do not use an item or item prefix.
            # Do not use an existing table.
            # Encourage re-using an existing table array.
            # Encourage re-using an existing table or prefix as prefix.
            item_keys = ctx.get_item_keys()
            table_keys = ctx.get_table_keys(array=False)
            array_keys = ctx.get_table_keys(array=True)
            (key_str, key) = self._gen_key(
                exclude_prefix=item_keys,
                exclude_key=item_keys + table_keys,
                reuse_prefix=table_keys + array_keys,
                reuse_key=array_keys)
            ctx.open_table_array(key)
            return "[[" + self._gen_ws() + key_str + self._gen_ws() + "]]"
        else:
            # std table
            # Do not use an item or item prefix.
            # Do not redefine a previously defined table.
            # Encourage defining an existing implicit table.
            # Encourage using an existing table or prefix as prefix.
            item_keys = ctx.get_item_keys()
            implicit_table_keys = ctx.get_table_keys(defined=False, array=False)
            defined_table_keys = ctx.get_table_keys(defined=True, array=False)
            array_keys = ctx.get_table_keys(array=True)
            (key_str, key) = self._gen_key(
                exclude_prefix=item_keys,
                exclude_key=item_keys + defined_table_keys + array_keys,
                reuse_prefix=implicit_table_keys + defined_table_keys,
                reuse_key=implicit_table_keys)
            ctx.open_table(key)
            return "[" + self._gen_ws() + key_str + self._gen_ws() + "]"

    def _gen_val(self) -> tuple[str, _ValueType]:
        """
        val = string / boolean / array / inline-table / date-time / float / integer
        """
        funcs: list[Callable[[], tuple[str, _ValueType]]] = [
            self._gen_string,
            self._gen_boolean,
            self._gen_integer,
            self._gen_float,
            self._gen_array,
            self._gen_inline_table,
            self._gen_date_time]
        func = self.rng.choice(funcs)
        return func()

    def _gen_string(self) -> tuple[str, str]:
        """
        string = ml-basic-string / basic-string
               / ml-literal-string / literal-string
        """
        funcs = [
            self._gen_ml_basic_string,
            self._gen_basic_string,
            self._gen_ml_literal_string,
            self._gen_literal_string]
        func = self.rng.choice(funcs)
        return func()

    def _gen_basic_string(self) -> tuple[str, str]:
        """
        basic-string = %x22 *basic-char %x22
        """
        n = self._rand_exp(self.MEAN_STRING_LEN, 0, self.MAX_STRING_LEN)
        doc_chars = []
        val_chars = []
        for i in range(n):
            (doc_char, val_char) = self._gen_basic_char()
            doc_chars.append(doc_char)
            val_chars.append(val_char)
        str_doc = '"' + "".join(doc_chars) + '"'
        val = "".join(val_chars)
        return (str_doc, val)

    def _gen_basic_char(self) -> tuple[str, str]:
        """
        basic-char = basic-unescaped / escaped
        basic-unescaped = %x09 / %x20 / %x21 / %x23-5B / %x5D-7E
                          / %x80-D7FF / %xE000-10FFFF
        escaped = %x5C (
                    %x22 / %x5C / "b" / "f" / "n" / "r" / "t"
                    / "u" 4HEXDIG / "U" 8HEXDIG )
        """
        r = self.rng.random()
        if r < 0.5 * self.PROB_ESCAPE_CHAR:
            escapes = sorted(self.ESCAPE_CHARS.items())
            r = self.rng.randint(0, len(escapes) - 1)
            (c, escsym) = escapes[r]
            return ("\\" + escsym, chr(c))
        elif r < self.PROB_ESCAPE_CHAR:
            r = self.rng.random()
            if r < 0.5:
                c = self.rng.randint(0, 0xd7ff)
            else:
                c = self.rng.randint(0xe000, 0x10ffff)
            if c < 0x10000 and r < 0.9:
                h = self._rand_format_hex(c, 4)
                return ("\\u" + h, chr(c))
            else:
                h = self._rand_format_hex(c, 8)
                return ("\\U" + h, chr(c))
        else:
            r = self.rng.random()
            if r < 0.1:
                c = self.rng.randint(0x20, 0x2f)
                if c == 0x22:
                    c = 0x09
            elif r < 0.8:
                c = self.rng.randint(0x30, 0x7e)
                if c == 0x5c:
                    c = 0x41
            elif r < 0.9:
                c = self.rng.randint(0x80, 0xd7ff)
            else:
                c = self.rng.randint(0xe000, 0x10ffff)
            return (chr(c), chr(c))

    def _gen_literal_string(self) -> tuple[str, str]:
        """
        literal-string = %x27 *literal-char %x27
        """
        n = self._rand_exp(self.MEAN_STRING_LEN, 0, self.MAX_STRING_LEN)
        chars = []
        for i in range(n):
            chars.append(self._gen_literal_char())
        val = "".join(chars)
        return ("'" + val + "'", val)

    def _gen_literal_char(self) -> str:
        """
        literal-char = %x09 / %x20-26 / %x28-7E / %x80-D7FF / %xE000-10FFFF
        """
        r = self.rng.random()
        if r < 0.1:
            c = self.rng.randint(0x20, 0x2f)
            if c == 0x27:
                c = 0x09
        elif r < 0.8:
            c = self.rng.randint(0x30, 0x7e)
        elif r < 0.9:
            c = self.rng.randint(0x80, 0xd7ff)
        else:
            c = self.rng.randint(0xe000, 0x10ffff)
        return chr(c)

    def _gen_ml_basic_string(self) -> tuple[str, str]:
        n = self._rand_exp(self.MEAN_MLSTRING_LEN, 0, self.MAX_MLSTRING_LEN)
        doc_chars = []
        val_chars = []
        if self.rng.randint(0, 1) > 0:
            doc_chars.append(self._gen_newline())
        allow_quote = True
        allow_whitespace = True
        for i in range(n):
            r = self.rng.random()
            if allow_quote and r < self.PROB_ML_QUOTE:
                doc_chars.append('"')
                val_chars.append('"')
                if r < 0.5 * self.PROB_ML_QUOTE:
                    doc_chars.append('"')
                    val_chars.append('"')
                allow_quote = False
                allow_whitespace = True
                continue
            allow_quote = True
            r = self.rng.random()
            if r < self.PROB_ML_NEWLINE and val_chars and allow_whitespace:
                doc_chars.append(self._gen_newline())
                val_chars.append("\n")
            elif r < self.PROB_ML_NEWLINE + self.PROB_ML_ESCAPED_NEWLINE:
                doc_chars.append("\\" + self._gen_ws() + self._gen_newline())
                for k in range(self.rng.randint(0, 2)):
                    doc_chars.append(self._gen_ws() + self._gen_newline())
                doc_chars.append(self._gen_ws())
                allow_whitespace = False
            else:
                while True:
                    (doc_char, val_char) = self._gen_basic_char()
                    if allow_whitespace or (doc_char not in "\t "):
                        break
                doc_chars.append(doc_char)
                val_chars.append(val_char)
                allow_whitespace = True
        str_doc = '"""' + "".join(doc_chars) + '"""'
        val = "".join(val_chars)
        return (str_doc, val)

    def _gen_ml_literal_string(self) -> tuple[str, str]:
        n = self._rand_exp(self.MEAN_MLSTRING_LEN, 0, self.MAX_MLSTRING_LEN)
        doc_chars = []
        val_chars = []
        if self.rng.randint(0, 1) > 0:
            doc_chars.append(self._gen_newline())
        allow_quote = True
        for i in range(n):
            r = self.rng.random()
            if allow_quote and r < self.PROB_ML_QUOTE:
                doc_chars.append("'")
                val_chars.append("'")
                if r < 0.5 * self.PROB_ML_QUOTE:
                    doc_chars.append("'")
                    val_chars.append("'")
                allow_quote = False
                continue
            allow_quote = True
            r = self.rng.random()
            if r < self.PROB_ML_NEWLINE and val_chars:
                doc_chars.append(self._gen_newline())
                val_chars.append("\n")
            else:
                c = self._gen_literal_char()
                doc_chars.append(c)
                val_chars.append(c)
        str_doc = "'''" + "".join(doc_chars) + "'''"
        val = "".join(val_chars)
        return (str_doc, val)

    def _gen_boolean(self) -> tuple[str, bool]:
        return self.rng.choice([
            ("true", True),
            ("false", False)])

    def _splice_number(self, s: str) -> str:
        parts = []
        p = 0
        for i in range(1, len(s)):
            if self.rng.random() < 0.1:
                parts.append(s[p:i])
                p = i
        parts.append(s[p:])
        return "_".join(parts)

    def _gen_integer(self) -> tuple[str, int]:
        """
        integer = dec-int / hex-int / oct-int / bin-int
        dec-int = [ "-" / "+" ] unsigned-dec-int
        unsigned-dec-int = DIGIT / digit1-9 1*( DIGIT / "_" DIGIT )
        hex-int = "0x" HEXDIG *( HEXDIG / "_" HEXDIG )
        oct-int = "0o" digit0-7 *( digit0-7 / "_" digit0-7 )
        bin-int = "0b" digit0-1 *( digit0-1 / "_" digit0-1 )
        """
        r = self.rng.random()
        val = round(math.exp(r**2 * math.log(self.MAX_INT_VALUE + 1)) - 1)

        formats: list[tuple[str, Callable[[int], str], bool, int]] = [
            ("", str, False, 1),
            ("+", str, False, 1),
            ("-", str, False, -1),
            ("0x", self._rand_format_hex, True, 1),
            ("0o", "{:o}".format, True,  1),
            ("0b", "{:b}".format, True, 1)
        ]
        (prefix, fmtfunc, add_zeros, sign) = self.rng.choice(formats)

        s = fmtfunc(val)
        if add_zeros:
            n = self.rng.randint(0, 3)
            s = n * "0" + s
        s = self._splice_number(s)

        s = prefix + s
        val = sign * val

        return (s, val)

    def _gen_dec_int(self,
                     max_val: int,
                     signed: bool,
                     zero_prefixable: bool
                     ) -> tuple[str, int]:
        v = self.rng.randint(0, max_val)
        if signed:
            sign_str = self.rng.choice(["", "+", "-"])
        else:
            sign_str = ""
        if zero_prefixable:
            n = self.rng.randint(0, 3)
            prefix = n * "0"
        else:
            prefix = ""
        s = sign_str + self._splice_number(prefix + str(v))
        if sign_str == "-":
            v = -v
        return (s, v)

    def _gen_float(self) -> tuple[str, float]:
        """
        float = float-int-part ( exp / frac [ exp ] )
                / special-float
        float-int-part = dec-int
        frac = "." zero-prefixable-int
        zero-prefixable-int = DIGIT *( DIGIT / "_" DIGIT )
        exp = "e" float-exp-part
        float-exp-part = [ "+" / "-" ] zero-prefixable-int
        special-float = [ "+" / "-" ] ( "inf" / "nan" )
        """
        if self.rng.random() < self.PROB_SPECIAL_FLOAT:
            prefix = self.rng.choice(["", "+", "-"])
            sym = self.rng.choice(["inf", "nan"])
            s = prefix + sym
            val = float(s)
            return (s, val)

        (int_str, int_val) = self._gen_dec_int(
            max_val=999999, signed=True, zero_prefixable=False)

        r = self.rng.randint(0, 2)
        if r in (0, 2):
            (exp_str, exp_val) = self._gen_dec_int(
                max_val=100, signed=True, zero_prefixable=True)
            exp_str = self.rng.choice("eE") + exp_str
        else:
            exp_str = ""
        if r in (1, 2):
            (frac_str, frac_val) = self._gen_dec_int(
                max_val=99999, signed=False, zero_prefixable=True)
            frac_str = "." + frac_str
        else:
            frac_str = ""

        s = int_str + frac_str + exp_str
        val = float(s.replace("_", ""))
        return (s, val)

    def _gen_ws_comment_newline(self) -> str:
        """
        ws-comment-newline = *( wschar / [ comment ] newline )
        """
        n = self._rand_exp(2, 0, 5)
        parts = []
        for i in range(n):
            r = self.rng.randint(0, 5)
            if r < 4:
                parts.append(self._gen_ws())
            if r in (2, 4):
                parts.append(self._gen_comment())
            if r >= 2:
                parts.append(self._gen_newline())
        return "".join(parts)

    def _gen_array(self) -> tuple[str, list[_ValueType]]:
        """
        array = "[" [ array-values ] ws-comment-newline "]"
        array-values =  ws-comment-newline val ws-comment-newline "," array-values
                       / ws-comment-newline val ws-comment-newline [ "," ]
        """
        parts = []
        val = []
        n = self._rand_exp(self.MEAN_ARRAY_ELEMS, 0, self.MAX_ARRAY_ELEMS)
        for i in range(n):
            if i > 0:
                parts.append(self._gen_ws_comment_newline())
                parts.append(",")
            parts.append(self._gen_ws_comment_newline())
            (s, v) = self._gen_val()
            parts.append(s)
            val.append(v)
        if n > 0 and self.rng.random() < 0.5:
            parts.append(self._gen_ws_comment_newline())
            parts.append(",")
        parts.append(self._gen_ws_comment_newline())
        s = "[" + "".join(parts) + "]"
        return (s, val)

    def _gen_inline_table(self) -> tuple[str, _TableType]:
        """
        inline-table = "{" ws [ inline-table-keyvals ] ws "}"
        inline-table-keyvals = keyval [ ws "," ws inline-table-keyvals ]
        keyval = key ws "=" ws val
        """
        parts: list[str] = []
        tbl: _TableType = {}
        item_keys: list[_KeyType] = []
        item_prefixes: list[_KeyType] = []
        n = self._rand_exp(self.MEAN_ARRAY_ELEMS, 0, self.MAX_ARRAY_ELEMS)
        for i in range(n):
            (key_str, key) = self._gen_key(
                exclude_prefix=item_keys,
                exclude_key=item_keys + item_prefixes,
                reuse_prefix=item_prefixes,
                reuse_key=())

            (val_str, v) = self._gen_val()
            if i > 0:
                parts.append(self._gen_ws())
                parts.append(",")
            parts.append(self._gen_ws())
            parts.append(key_str)
            parts.append(self._gen_ws())
            parts.append("=")
            parts.append(self._gen_ws())
            parts.append(val_str)

            item_keys.append(key)
            for i in range(1, len(key)):
                if key[:i] not in item_prefixes:
                    item_prefixes.append(key[:i])
            subtbl = tbl

            for p in key[:-1]:
                if p not in subtbl:
                    subtbl[p] = {}
                subtbl = cast(dict[str, _ValueType], subtbl[p])
            p = key[-1]
            subtbl[p] = v

        parts.append(self._gen_ws())
        s = "{" + "".join(parts) + "}"
        return (s, tbl)

    def _gen_date_time(self) -> tuple[str, _DateTimeType]:
        """
        date-time = offset-date-time / local-date-time / local-date / local-time

        offset-date-time = full-date time-delim full-time
        local-date-time = full-date time-delim partial-time
        local-date = full-date
        local-time = partial-time

        full-date = 4DIGIT "-" 2DIGIT "-" 2DIGIT
        full-time = partial-time time-offset
        partial-time = 2DIGIT ":" 2DIGIT ":" 2DIGIT ["." 1*DIGIT]
        time-offset = "Z" / ( "+" / "-" ) 2DIGIT ":" 2DIGIT
        time-delim = "T" / %x20

        Values of month, day, hour, minute, second limited to valid dates/times.
        Second value "60" allowed in case of leap seconds.
        """
        funcs: list[Callable[[], tuple[str, _DateTimeType]]] = [
            self._gen_offset_date_time,
            self._gen_local_date_time,
            self._gen_local_date,
            self._gen_local_time]
        func = self.rng.choice(funcs)
        return func()

    def _gen_offset_date_time(self) -> tuple[str, datetime.datetime]:
        (date_str, date) = self._gen_local_date()
        (time_str, time) = self._gen_local_time()
        (tz_str, tz) = self._gen_timezone()
        val = datetime.datetime.combine(date, time).replace(tzinfo=tz)
        s = date_str + self.rng.choice("Tt ") + time_str + tz_str
        return (s, val)

    def _gen_local_date_time(self) -> tuple[str, datetime.datetime]:
        (date_str, date) = self._gen_local_date()
        (time_str, time) = self._gen_local_time()
        val = datetime.datetime.combine(date, time)
        s = date_str + self.rng.choice("Tt ") + time_str
        return (s, val)

    def _gen_local_date(self) -> tuple[str, datetime.date]:
        year = self.rng.randint(1000, 9999)
        month = self.rng.randint(1, 12)
        if month == 2:
            if (year % 400 == 0) or (year % 4 == 0 and year % 100 != 0):
                maxday = 29
            else:
                maxday = 28
        elif month in (4, 6, 9, 11):
            maxday = 30
        else:
            maxday = 31
        day = self.rng.randint(1, maxday)
        val = datetime.date(year, month, day)
        s = val.isoformat()
        return (s, val)

    def _gen_local_time(self) -> tuple[str, datetime.time]:
        hour = self.rng.randint(0, 23)
        minute = self.rng.randint(0, 59)
        second = self.rng.randint(0, 59)
        if self.rng.random() < 0.5:
            r = self.rng.randint(1, 6)
            usec = 0
            usec_suffix = "." + r * "0"
        else:
            r = self.rng.randint(0, 6)
            usec = self.rng.randint(0, 999999)
            usec -= usec % (10**r)
            usec_suffix = ""
        val = datetime.time(hour, minute, second, usec)
        s = val.isoformat() + usec_suffix
        return (s, val)

    def _gen_timezone(self) -> tuple[str, datetime.timezone]:
        if self.rng.random() < 0.2:
            return ("Z", datetime.timezone.utc)
        else:
            delta = self.rng.randint(1 - 24 * 60, 24 * 60 - 1)
            val = datetime.timezone(datetime.timedelta(minutes=delta))
            s = "{}{:02d}:{:02d}".format(
                "-" if delta < 0 else "+",
                abs(delta) // 60,
                abs(delta) % 60)
            return (s, val)


def main() -> None:
    """Generate a random TOML file and send it to stdout."""

    parser = argparse.ArgumentParser()
    parser.description = "Generate a random TOML file and send it to stdout."""
    parser.add_argument("--seed", action="store", type=int,
                        help="set random generator seed")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    gen = TomlGenerator(rng)
    (toml_doc, toml_data) = gen.gen_toml()

    sys.stdout.buffer.write(toml_doc.encode("utf-8"))


if __name__ == "__main__":
    main()

