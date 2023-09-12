#!/usr/bin/env python
# coding=utf-8
# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        qsch_editor.py
# Purpose:     Class made to update directly the QSPICE Schematic files
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
from pathlib import Path
from typing import Union, Tuple, List
import re
import logging
from spicelib.editor.base_editor import (
    BaseEditor, format_eng, ComponentNotFoundError, ParameterNotFoundError,
    PARAM_REGEX, UNIQUE_SIMULATION_DOT_INSTRUCTIONS
)
__all__ = ('QschEditor', )

_logger = logging.getLogger("qspice.QschEditor")

TEXT_REGEX = re.compile(r"TEXT (-?\d+)\s+(-?\d+)\s+(Left|Right|Top|Bottom)\s\d+\s*(?P<type>[!;])(?P<text>.*)",
                        re.IGNORECASE)
TEXT_REGEX_X = 1
TEXT_REGEX_Y = 2
TEXT_REGEX_ALIGN = 3
TEXT_REGEX_TYPE = 4
TEXT_REGEX_TEXT = 5

END_LINE_TERM = "\n"
QSCH_HEADER = (255, 216, 255, 219)

class QschReadingError(IOError):
    ...


class QschTag:
    def __init__(self, stream, start):
        assert stream[start] == '«'
        self.start = start
        self.children = []
        self.tokens = []
        i = start + 1
        i0 = i
        while i < len(stream):
            if stream[i] == '«':
                child = QschTag(stream, i)
                i = child.stop
                i0 = i + 1
                self.children.append(child)
            elif stream[i] == '»':
                self.stop = i + 1
                if i > i0:
                    self.tokens.append(stream[i0:i])
                break
            elif stream[i] == ' ' or stream[i] == '\n':
                if i > i0:
                    self.tokens.append(stream[i0:i])
                i0 = i + 1
            elif stream[i] == '"':
                # get all characters until the next " sign
                i += 1
                while stream[i] != '"':
                    i += 1
            i += 1
        else:
            raise IOError("Missing » when reading file")

    def __str__(self):
        """Returns only the first line"""
        return ' '.join(self.tokens)

    def out(self, level):
        spaces = '  ' * level
        if len(self.children):
            return (f"{spaces}«{' '.join(self.tokens)}\n"
                    f"{''.join(tag.out(level+1) for tag in self.children)}"
                    f"{spaces}»\n")
        else:
            return f"{'  ' * level}«{' '.join(self.tokens)}»\n"

    @property
    def tag(self) -> str:
        return self.tokens[0]

    def get_items(self, item) -> List['QschTag']:
        answer = [tag for tag in self.children if tag.tag == item]
        return answer

    def get_attr(self, index: int):
        a = self.tokens[index]
        if a.startswith('(') and a.endswith(')'):
            return tuple(int(x) for x in a[1:-1].split(','))
        elif a.startswith('0x'):
            return int(a[2:], 16)
        elif a.startswith('"') and a.endswith('"'):
            return a[1:-1]
        else:
            return int(a)

    def get_text(self, label) -> str:
        a = self.get_items(label+':')
        if len(a) != 1:
            raise IndexError(f"Label {label}: not found")
        return a[0].tokens[1]


class QschEditor(BaseEditor):
    """Class made to update directly the LTspice ASC files"""

    def __init__(self, asc_file: str):
        self._qsch_file_path = Path(asc_file)
        self._qsch_stream = ""
        self.schematic = None

        self._symbols = {}
        self._texts = []  # This is only here to avoid cycling over the netlist everytime we need to retrieve the texts
        if not self._qsch_file_path.exists():
            raise FileNotFoundError(f"File {asc_file} not found")
        # read the file into memory
        self.reset_netlist()

    @property
    def circuit_file(self) -> Path:
        return self._qsch_file_path

    def write_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        if isinstance(run_netlist_file, str):
            run_netlist_file = Path(run_netlist_file)
        run_netlist_file = run_netlist_file.with_suffix(".qsch")
        if self.schematic is None:
            _logger.error("Empty Schematic information")
            return
        with open(run_netlist_file, 'w') as qsch_file:
            _logger.info(f"Writing ASC file {run_netlist_file}")
            for c in QSCH_HEADER:
                qsch_file.write(chr(c))
            qsch_file.write(self.schematic.out(0))


    def reset_netlist(self):
        with open(self._qsch_file_path, 'r') as asc_file:
            _logger.info(f"Reading QSCH file {self._qsch_file_path}")
            self._qsch_stream = asc_file.read()
        self._parse_asc_file()

    def _parse_asc_file(self):

        self._symbols.clear()
        self._texts.clear()
        _logger.debug("Parsing ASC file")
        header = tuple(ord(c) for c in self._qsch_stream[:4])

        if header != QSCH_HEADER:
            raise QschReadingError("Missing header. The QSCH file should start with: " +
                                   f"{' '.join(f'{c:02X}' for c in QSCH_HEADER)}")

        schematic = QschTag(self._qsch_stream, 4)
        self.schematic = schematic

        components = self.schematic.get_items('component')
        for component in components:
            symbol: QschTag = component.get_items('symbol')[0]
            typ = symbol.get_text('type')
            desc = symbol.get_text('description')
            texts = symbol.get_items('text')
            if len(texts) < 2:
                raise RuntimeError(f"Missing texts in component at coordinates {component.get_attr(1)}")
            refdes = texts[0].get_attr(8)
            value = texts[1].get_attr(8)
            self._symbols[refdes] = {
                'type': typ,
                'description': desc,
                'model': value,
                'tag': component
            }

        for text_tag in self.schematic.get_items('text'):
            text = text_tag.get_attr(8)
            self._texts.append(text)

    def get_component_info(self, component) -> dict:
        """Returns the component information as a dictionary"""
        if component not in self._symbols:
            _logger.error(f"Component {component} not found in ASC file")
            raise ComponentNotFoundError(f"Component {component} not found in ASC file")
        return self._symbols[component]

    def _get_text_matching(self, command, search_expression: re.Pattern):
        command_upped = command.upper()
        text_tags = self.schematic.get_items('text')
        for tag in text_tags:
            line = tag.get_attr(8)
            if line.upper().startswith(command_upped):
                match = search_expression.search(line)
                if match:
                    return tag, match
        else:
            return None, None

    def get_parameter(self, param: str) -> str:
        param_regex = re.compile(PARAM_REGEX % param, re.IGNORECASE)
        tag, match = self._get_text_matching(".PARAM", param_regex)
        if match:
            return match.group('value')
        else:
            raise ParameterNotFoundError(f"Parameter {param} not found in ASC file")

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        param_regex = re.compile(PARAM_REGEX % param, re.IGNORECASE)
        tag, match = self._get_text_matching(".PARAM", param_regex)
        if match:
            _logger.debug(f"Parameter {param} found in ASC file, updating it")
            if isinstance(value, (int, float)):
                value_str = format_eng(value)
            else:
                value_str = value
            line: str = tag.get_attr(8)
            match = param_regex.search(line)  # repeating the search, so we update the correct start/stop parameter
            start, stop = match.span(param_regex.groupindex['replace'])
            tag.token[8] = "{}={}".format(param, value_str) + line[stop:]
            _logger.info(f"Parameter {param} updated to {value_str}")
            _logger.debug(f"Text at {tag.get_attr(1)} Updated")
        else:
            # Was not found so we need to add it,
            _logger.debug(f"Parameter {param} not found in ASC file, adding it")
            x, y = self._get_text_space()
            tag = QschTag(f'«text ({x},{y}) 1 0 0 0x1000000 -1 -1 ".param {param}={value}"»', 0)
            self.schematic.children(tag)
            _logger.info(f"Parameter {param} added with value {value}")
            _logger.debug(f"Text added to {tag.get_attr(1)} Added: {tag.get_attr(8)}")
        self._parse_asc_file()

    def set_component_value(self, device: str, value: Union[str, int, float]) -> None:
        if isinstance(value, str):
            value_str = value
        else:
            value_str = format_eng(value)
        self.set_element_model(device, value_str)

    def set_element_model(self, device: str, model: str) -> None:
        comp_info = self.get_component_info(device)
        component: QschTag = comp_info['tag']
        symbol: QschTag = component.get_items('symbol')[0]
        texts = symbol.get_items('text')
        assert texts[0].get_attr(8) == device
        texts[1].tokens[8] = model
        _logger.info(f"Component {device} updated to {model}")
        _logger.debug(f"Component at :{component.get_attr(1)} Updated")

    def get_component_value(self, element: str) -> str:
        comp_info = self.get_component_info(element)
        if "model" not in comp_info:
            _logger.error(f"Component {element} does not have a Value attribute")
            raise ComponentNotFoundError(f"Component {element} does not have a Value attribute")
        return comp_info["model"]

    def get_components(self, prefixes='*') -> list:
        if prefixes == '*':
            return list(self._symbols.keys())
        return [k for k in self._symbols.keys() if k[0] in prefixes]

    def remove_component(self, designator: str):
        comp_info = self.get_component_info(designator)
        component: QschTag = comp_info['tag']
        self.schematic.children.remove(component)

    def _get_text_space(self):
        """
        Returns the coordinate on the Schematic File canvas where a text can be appended.
        """
        min_x = 100000   # High enough to be sure it will be replaced
        max_x = -100000  # Low enough to be sure it will be replaced
        min_y = 100000   # High enough to be sure it will be replaced
        max_y = -100000  # Low enough to be sure it will be replaced
        for tag in self.schematic:
            if tag.tag == 'component':
                x1, y1 = tag.get_attr(1)
                x2, y2 = x1, y1  # todo: the whole component primitives
            elif tag.tag == 'wire':
                x1, y1 = tag.get_attr(1)
                x2, y2 = tag.get_attr(2)
            elif tag.tag == 'net':
                x1, y1 = tag.get_attr(1)
                x2, y2 = x1, y1

            min_x = min(min_x, x1, x2)
            max_x = max(max_x, x1, x2)
            min_y = min(min_y, y1, y2)
            max_y = max(max_y, y1, y2)

        return min_x, max_y + 24  # Setting the text in the bottom left corner of the canvas

    def add_instruction(self, instruction: str) -> None:
        instruction = instruction.strip()  # Clean any end of line terminators
        command = instruction.split()[0].upper()

        if command in UNIQUE_SIMULATION_DOT_INSTRUCTIONS:
            # Before adding new instruction, if it is a unique instruction, we just replace it
            i = 0
            while i < len(self._texts):
                line = self._texts[i]
                command = line.split()[0].upper()
                if command in UNIQUE_SIMULATION_DOT_INSTRUCTIONS:
                    line_tag = self.schematic.get_items('text')[i]
                    line_tag.token[8] = f'"{instruction}"'
                    return  # Job done, can exit this method
                i += 1
        elif command.startswith('.PARAM'):
            raise RuntimeError('The .PARAM instruction should be added using the "set_parameter" method')
        # If we get here, then the instruction was not found, so we need to add it
        x, y = self._get_text_space()
        tag = QschTag(f'«text ({x},{y}) 1 0 0 0x1000000 -1 -1 "{instruction}"»', 0)
        self.schematic.children(tag)

    def remove_instruction(self, instruction: str) -> None:
        i = 0
        while i < len(self._texts):
            line_no, line = self._texts[i]
            if instruction in line:
                del self._asc_file_lines[line_no]
                self._parse_asc_file()
                return  # Job done, can exit this method
            i += 1

        msg = f'Instruction "{instruction}" not found'
        _logger.error(msg)
        raise RuntimeError(msg)
